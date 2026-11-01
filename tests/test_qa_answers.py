"""Offline validation and scoring checks for the saved-answer judge."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import yaml

import evaluate_qa_answers as evaluation


def fact(label="covered", quote="Items expire after ten seconds."):
    return dict(label=label, answer_quote=quote, reason="Reason.")


def claim(label="supported", quote="Items expire after ten seconds.", context=None):
    return dict(label=label, answer_quote=quote, context_quotes=[quote] if context is None else context, reason="Reason.")


def valid(result):
    return dict(status="valid", result=result)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.payload = dict(generated_answer="Items expire after ten seconds.",
                            retrieved_context="Items expire after ten seconds.", required_facts=[{"text": "Expiration is ten seconds."}])

    def test_valid_reference_and_context_quotes(self):
        evaluation.validate_judgment("coverage", {"facts": [fact()]}, self.payload)
        evaluation.validate_judgment("grounding", {"claims": [claim()], "no_claims_reason": ""}, self.payload)

    def test_harmless_normalization(self):
        payload = {**self.payload, "generated_answer": "Items expire after\nten seconds."}
        evaluation.validate_judgment("coverage", {"facts": [fact()]}, payload)

    def test_missing_fact_can_have_no_answer_quote(self):
        evaluation.validate_judgment("coverage", {"facts": [fact("missing_or_incomplete", "")]}, self.payload)

    def test_invalid_and_missing_quotes_fail(self):
        for quote in ("Items expire immediately.", "", None):
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                evaluation.validate_judgment("coverage", {"facts": [fact(quote=quote)]}, self.payload)
        for quote in ("Different text.", ""):
            with self.subTest(context=quote), self.assertRaises(ValueError):
                evaluation.validate_judgment("grounding", {"claims": [claim(context=[quote])], "no_claims_reason": ""}, self.payload)

    def test_wrong_count_label_and_duplicate_claims_fail(self):
        with self.assertRaises(ValueError):
            evaluation.validate_judgment("coverage", {"facts": []}, self.payload)
        with self.assertRaises(ValueError):
            evaluation.validate_judgment("coverage", {"facts": [fact("wrong")]}, self.payload)
        with self.assertRaises(ValueError):
            evaluation.validate_judgment("grounding", {"claims": [claim(), claim()], "no_claims_reason": ""}, self.payload)

    def test_empty_claim_list_needs_a_reason(self):
        evaluation.validate_judgment("grounding", {"claims": [], "no_claims_reason": "Pure abstention."}, self.payload)
        with self.assertRaises(ValueError):
            evaluation.validate_judgment("grounding", {"claims": [], "no_claims_reason": ""}, self.payload)

    def test_exclusions_require_literal_quotes_and_cannot_duplicate_claims(self):
        entry = dict(answer_quote=self.payload["generated_answer"], kind="context_insufficiency", reason="Reason")
        for excluded in ([{**entry, "answer_quote":"Invented"}], [entry]):
            with self.subTest(excluded=excluded), self.assertRaises(ValueError):
                evaluation.validate_judgment("grounding", dict(claims=[claim()], excluded_statements=excluded, no_claims_reason=""), self.payload)

    def test_abstention_label_must_agree_with_behavior_flags(self):
        value = {**fact("mixed"), "acknowledges_insufficiency":True, "provides_substantive_answer":True}
        evaluation.validate_judgment("abstention", value, self.payload)
        with self.assertRaisesRegex(ValueError, "require label mixed"):
            evaluation.validate_judgment("abstention", {**value, "label":"unsupported_answer"}, self.payload)


class GroundingPreprocessingTests(unittest.TestCase):
    def test_only_complete_citation_rows_are_removed_with_original_offsets(self):
        answer="An actual claim.\n- SOURCE: A Book.pdf, PAGE: 12\nSOURCE: A Book.pdf, PAGES: 12–13\nAnother claim."
        text,removed=evaluation.grounding_text(answer)
        self.assertEqual(len(removed),2)
        for row in removed:
            self.assertEqual(answer[row["start"]:row["end_exclusive"]],row["text"])
        self.assertEqual(text,"An actual claim.\n\n\nAnother claim.")

    def test_inline_citations_and_negated_or_unsupported_claims_survive(self):
        answer="It never expires (SOURCE: A Book.pdf, PAGE: 12).\nSOURCE: A Book.pdf, PAGE: 12 guarantees encryption.\nI cannot verify this, but capacity is 100."
        text,removed=evaluation.grounding_text(answer)
        self.assertEqual(text,answer)
        self.assertEqual(removed,[])


class ScoringTests(unittest.TestCase):
    def sample(self):
        return dict(judgments=dict(coverage=valid({"facts": [fact(), fact("missing_or_incomplete", ""), fact("contradicted")]}),
            grounding=valid({"claims": [claim(), claim("unsupported", context=[])]}),
            abstention=dict(status="not_applicable", result=None)))

    def test_fact_and_claim_denominators_are_independent(self):
        scores = evaluation.question_scores(self.sample())
        self.assertAlmostEqual(scores["fact_coverage"]["score"], 1 / 3)
        self.assertAlmostEqual(scores["reference_contradiction_rate"]["score"], 1 / 3)
        self.assertEqual(scores["grounding_rate"]["score"], .5)
        self.assertEqual(scores["context_contradiction_rate"]["score"], 0)

    def test_uncertain_stage_does_not_destroy_other_stage(self):
        sample = self.sample()
        sample["judgments"]["coverage"]["status"] = "unscored"
        scores = evaluation.question_scores(sample)
        self.assertIsNone(scores["fact_coverage"]["score"])
        self.assertEqual(scores["grounding_rate"]["score"], .5)

    def test_no_claims_not_perfect_grounding(self):
        sample = self.sample()
        sample["judgments"]["grounding"] = valid({"claims": []})
        scores = evaluation.question_scores(sample)
        self.assertEqual(scores["grounding_rate"]["status"], "not_applicable")
        self.assertIsNone(scores["grounding_rate"]["score"])

    def test_abstention_and_macro_average(self):
        first, second = self.sample(), self.sample()
        second["judgments"]["coverage"] = valid({"facts": [fact()]})
        second["judgments"]["abstention"] = valid({"label": "mixed"})
        result = evaluation.summarize([first, second])
        self.assertAlmostEqual(result["fact_coverage"]["average"], (1 / 3 + 1) / 2)
        self.assertEqual(result["abstention_accuracy"]["average"], 0)
        self.assertEqual(result["abstention_accuracy"]["not_applicable"], 1)


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((evaluation.ROOT / "config.yml").read_text())
        self.payload = dict(generated_answer="Items expire after ten seconds.", required_facts=[{}])

    def response(self, result):
        return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            model="judge-snapshot", choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(result)))])

    def test_one_corrective_retry_and_python_scores(self):
        client = Mock()
        client.chat.completions.create.side_effect = [self.response({"facts": [fact(quote="Invented quote.")]}),
                                                     self.response({"facts": [fact()]})]
        judge = evaluation.AnswerJudge(self.config, client)
        result = judge.ask("coverage", self.payload)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(judge.calls, 2)
        self.assertEqual(judge.tokens["total_tokens"], 60)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(client.chat.completions.create.call_args.kwargs["response_format"]["type"], "json_schema")

    def test_exhausted_retry_and_uncertainty_are_unscored(self):
        client = Mock()
        client.chat.completions.create.return_value = self.response({"facts": [fact(quote="Invented.")]})
        self.assertEqual(evaluation.AnswerJudge(self.config, client).ask("coverage", self.payload)["status"], "unscored")
        self.assertEqual(client.chat.completions.create.call_count, 2)
        client.chat.completions.create.return_value = self.response({"facts": [fact("uncertain", "")]})
        self.assertEqual(evaluation.AnswerJudge(self.config, client).ask("coverage", self.payload)["status"], "unscored")

    def test_sdk_error_does_not_expose_exception_text(self):
        client = Mock()
        client.chat.completions.create.side_effect = RuntimeError("sensitive request data")
        result = evaluation.AnswerJudge(self.config, client).ask("coverage", self.payload)
        self.assertEqual(result["errors"], ["RuntimeError"])
        self.assertNotIn("sensitive", json.dumps(result))

    def test_protocol_fingerprint_ignores_paths_but_detects_prompt_changes(self):
        config=copy.deepcopy(self.config)
        original=evaluation.judge_protocol(config)
        config["qa_answer_evaluation"]["results_dir"]="different/report/folder"
        self.assertEqual(evaluation.judge_protocol(config),original)
        config["qa_answer_evaluation"]["coverage_prompt"]+=" Different instruction."
        self.assertNotEqual(evaluation.judge_protocol(config),original)

    def test_citation_only_grounding_needs_no_model_call(self):
        client=Mock();judge=evaluation.AnswerJudge(self.config,client)
        result=judge.ask("grounding",dict(generated_answer="- SOURCE: A Book.pdf, PAGE: 12",retrieved_context="Context"))
        self.assertEqual(result["status"],"valid")
        self.assertEqual(result["result"]["claims"],[])
        self.assertEqual(judge.calls,0)
        client.chat.completions.create.assert_not_called()

    def test_citation_preprocessing_is_grounding_only_and_keeps_input(self):
        client=Mock();client.chat.completions.create.side_effect=[
            self.response(dict(statements=[dict(kind="substantive",answer_quote="Items expire after ten seconds.",reason="Technical assertion")])),
            self.response(dict(claims=[claim()],no_claims_reason=""))]
        judge=evaluation.AnswerJudge(self.config,client)
        payload=dict(question="Policy?",generated_answer="Items expire after ten seconds.\n- SOURCE: A Book.pdf, PAGE: 12",retrieved_context="Items expire after ten seconds.")
        before=copy.deepcopy(payload);result=judge.ask("grounding",payload)
        sent=client.chat.completions.create.call_args.kwargs["messages"][-1]["content"]
        self.assertNotIn("- SOURCE: A Book.pdf, PAGE: 12",sent)
        self.assertEqual(result["status"],"valid")
        self.assertEqual(payload,before)
        self.assertEqual(len(result["preprocessing"]["removed_citation_rows"]),1)

    def test_quote_created_by_removing_citations_is_rejected(self):
        client=Mock();grounded=self.response(dict(claims=[claim(quote="Alpha. Beta.",context=["Alpha. Beta."])],no_claims_reason=""))
        client.chat.completions.create.side_effect=[self.response(dict(statements=[dict(kind="substantive",answer_quote="Alpha. Beta.",reason="Assertion")])),grounded,grounded]
        result=evaluation.AnswerJudge(self.config,client).ask("grounding",dict(
            question="Question",generated_answer="Alpha.\nSOURCE: A Book.pdf, PAGE: 12\nBeta.",retrieved_context="Alpha. Beta."))
        self.assertEqual(result["status"],"unscored")
        self.assertEqual(client.chat.completions.create.call_count,3)

    def test_extraction_sees_no_context_and_grounding_sees_no_excluded_statement(self):
        client=Mock();excluded="The excerpt does not provide the requested number."
        client.chat.completions.create.side_effect=[self.response(dict(statements=[
            dict(kind="context_insufficiency",answer_quote=excluded,reason="Declines"),
            dict(kind="substantive",answer_quote="Items expire after ten seconds.",reason="Assertion")])),
            self.response(dict(claims=[claim()],no_claims_reason=""))]
        result=evaluation.AnswerJudge(self.config,client).ask("grounding",dict(question="Policy?",
            generated_answer=excluded+" Items expire after ten seconds.",retrieved_context="Items expire after ten seconds."))
        sent=[json.loads(c.kwargs["messages"][-1]["content"].split("INPUT DATA:\n")[1]) for c in client.chat.completions.create.call_args_list]
        self.assertEqual(set(sent[0]),{"question","generated_answer"})
        self.assertNotIn(excluded,sent[1]["generated_answer"])
        self.assertEqual(result["result"]["excluded_statements"][0]["answer_quote"],excluded)
        self.assertEqual(result["status"],"valid")

    def test_pure_abstention_stops_after_extraction_and_empty_claims_are_not_scored(self):
        client=Mock();text="The excerpt does not state a capacity."
        client.chat.completions.create.return_value=self.response(dict(statements=[dict(kind="context_insufficiency",answer_quote=text,reason="Declines")]))
        judge=evaluation.AnswerJudge(self.config,client)
        result=judge.ask("grounding",dict(question="Capacity?",generated_answer=text,retrieved_context="Context"))
        self.assertEqual(result["status"],"valid")
        self.assertEqual(result["result"]["claims"],[])
        self.assertEqual(judge.calls,1)

    def test_grounding_cannot_omit_an_extracted_claim(self):
        client=Mock();empty=self.response(dict(claims=[],no_claims_reason="No claims"))
        client.chat.completions.create.side_effect=[self.response(dict(statements=[dict(kind="substantive",answer_quote="Items expire after ten seconds.",reason="Assertion")])),empty,empty]
        result=evaluation.AnswerJudge(self.config,client).ask("grounding",dict(question="Policy?",generated_answer="Items expire after ten seconds.",retrieved_context="Context"))
        self.assertEqual(result["status"],"unscored")
        self.assertEqual(client.chat.completions.create.call_count,3)

    def test_mixed_flag_inconsistency_gets_one_corrective_retry(self):
        client=Mock()
        value={**fact("mixed"),"acknowledges_insufficiency":True,"provides_substantive_answer":True}
        client.chat.completions.create.side_effect=[self.response({**value,"label":"unsupported_answer"}),self.response(value)]
        result=evaluation.AnswerJudge(self.config,client).ask("abstention",self.payload)
        self.assertEqual(result["status"],"valid")
        self.assertEqual(result["result"]["label"],"mixed")
        self.assertEqual(len(result["errors"]),1)

    def test_grounding_does_not_receive_reference_material(self):
        question = dict(id="sample", question="What is the expiration policy?",
            generated_answer="Items expire after ten seconds.", reference_answer="The lifetime is ten seconds.",
            required_facts=[dict(fact_id="f1", text="Lifetime is ten seconds.", evidence_ids=["e1"])],
            reference_evidence=[dict(evidence_id="e1", exact_quote="The lifetime is ten seconds.")],
            final_context="Items expire after ten seconds.", allowed_sources=["sample.pdf"],
            answerability=dict(label="answerable"), errors=[])
        original = copy.deepcopy(question)
        judge = evaluation.AnswerJudge(self.config, Mock())
        judge.ask = Mock(side_effect=[valid({"facts": [fact()]}), valid({"claims": [claim()]})])
        result = evaluation.evaluate_saved_answer(question, judge)
        coverage_payload = judge.ask.call_args_list[0].args[1]
        grounding_payload = judge.ask.call_args_list[1].args[1]
        self.assertIn("reference_answer", coverage_payload)
        self.assertEqual(set(grounding_payload), {"question", "generated_answer", "retrieved_context"})
        self.assertEqual(result["judgments"]["coverage"]["result"]["facts"][0]["fact_id"], "f1")
        self.assertEqual(question, original)

    def test_failed_pipeline_is_not_a_zero_score_or_successful_abstention(self):
        question = dict(id="failed", question="Question", generated_answer="", reference_answer="Reference", errors=["failed"])
        judge = evaluation.AnswerJudge(self.config, Mock())
        judge.ask = Mock()
        result = evaluation.evaluate_saved_answer(question, judge)
        self.assertFalse(judge.ask.called)
        self.assertTrue(all(metric["status"] == "unscored" for metric in evaluation.question_scores(result).values()))

    def test_report_exports_all_metrics(self):
        question = dict(id="sample", question="Question", generated_answer="Answer", reference_answer="Reference",
                        seconds=1, llm_calls=2, token_usage={}, judgments=ScoringTests().sample()["judgments"])
        run = dict(judge_settings=self.config["qa_answer_evaluation"],
                   source_run=dict(timestamp_utc="saved", model_id="gpt-5.1", answer_max_new_tokens=400),
                   input_path="saved.json", input_sha256="fingerprint")
        calibration = dict(cases=[dict(passed=True)], llm_calls=5, token_usage={})
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "answers"
            metrics = evaluation.write_reports(directory, run, [question], calibration)
            details = json.loads((directory / "details.json").read_text())
            self.assertEqual(details["metric_summaries"], metrics)
            self.assertEqual(details["questions"][0]["metrics"], evaluation.question_scores(question))
            self.assertIn("Fact coverage", (directory / "summary.md").read_text())
            self.assertIn("grounding_rate_score", (directory / "per_question.csv").read_text())


if __name__ == "__main__":
    unittest.main()
