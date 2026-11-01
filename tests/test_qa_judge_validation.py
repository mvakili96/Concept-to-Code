"""Judge validation checks need no API calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import evaluate_qa_judge as validation


def case(stage="coverage", expected=None):
    labels=["covered"] if expected is None else expected
    value=dict(id="case",stage=stage,partition="development",expected_labels=labels,
               question="Question",generated_answer="Alpha is enabled. Beta is disabled.")
    if stage=="grounding":
        value["expected_claims"]=[dict(claim_id=f"c{i}",answer_quote=text,label=label)
            for i,(text,label) in enumerate(zip(("Alpha is enabled.","Beta is disabled."),labels),start=1)]
    return value


def judgment(stage, labels, quotes=None):
    if stage=="coverage":
        result={"facts":[{"label":label} for label in labels]}
    elif stage=="abstention":
        result={"label":labels[0]}
    else:
        result={"claims":[dict(label=label,answer_quote=quote)
                           for label,quote in zip(labels,quotes or [])],"no_claims_reason":""}
    return dict(status="valid",result=result)


def assessed(c,j,trial=1):
    return dict(id=c["id"],stage=c["stage"],partition=c["partition"],expected_labels=c["expected_labels"],
                trial=trial,judgment=j,assessment=validation.assess_case(c,j),
                llm_calls=1,token_usage={},judge_models={"snapshot":1})


class AssessmentTests(unittest.TestCase):
    def test_fact_order_matters(self):
        c=case(expected=["covered","missing_or_incomplete"])
        self.assertTrue(validation.assess_case(c,judgment("coverage",c["expected_labels"]))["exact_match"])
        self.assertFalse(validation.assess_case(c,judgment("coverage",list(reversed(c["expected_labels"]))))["exact_match"])

    def test_claim_order_can_change_but_identity_must_match(self):
        c=case("grounding",["supported","contradicted"])
        j=judgment("grounding",["contradicted","supported"],["Beta is disabled.","Alpha is enabled."])
        self.assertTrue(validation.assess_case(c,j)["exact_match"])

    def test_extra_and_missing_claims_fail_inventory(self):
        c=case("grounding",["supported","contradicted"])
        for j in [judgment("grounding",["supported"],["Alpha is enabled."]),
                  judgment("grounding",["supported","contradicted","supported"],
                           ["Alpha is enabled.","Beta is disabled.","Unrelated citation."])]:
            with self.subTest(j=j):
                result=validation.assess_case(c,j)
                self.assertFalse(result["inventory_ok"])
                self.assertFalse(result["exact_match"])

    def test_ambiguous_quote_is_not_guessed(self):
        c=case("grounding",["supported","contradicted"])
        result=validation.assess_case(c,judgment("grounding",["supported"],["is"]))
        self.assertFalse(result["inventory_ok"])
        self.assertEqual(result["comparisons"][0]["expected"],"<extra_claim>")

    def test_no_claim_controls_reject_citation_and_abstention_claims(self):
        c=case("grounding",[])
        self.assertTrue(validation.assess_case(c,judgment("grounding",[],[]))["exact_match"])
        self.assertFalse(validation.assess_case(c,judgment("grounding",["supported"],["SOURCE: sample.pdf"]))["exact_match"])

    def test_unscored_is_a_failure_in_the_primary_denominator(self):
        c=case()
        result=assessed(c,dict(status="unscored",result=None))
        metrics=validation.summarize([result])
        self.assertEqual(metrics["exact_case_accuracy"],dict(correct=0,total=1,score=0))
        self.assertEqual(metrics["usable_judgment_rate"],0)
        self.assertEqual(metrics["stages"]["coverage"]["per_label"]["covered"]["recall"],0)

    def test_repeating_wrong_labels_is_consistent_but_not_correct(self):
        c=case()
        a=assessed(c,judgment("coverage",["contradicted"]),1)
        b=assessed(c,judgment("coverage",["contradicted"]),2)
        metrics=validation.trial_summaries([a,b],1)
        self.assertEqual(metrics["repeatability"]["conditional_agreement"],1)
        self.assertEqual(metrics["combined"]["exact_case_accuracy"]["score"],0)

    def test_invalid_pairs_are_not_called_repeatable(self):
        c=case()
        records=[assessed(c,dict(status="unscored",result=None),t) for t in (1,2)]
        repeat=validation.trial_summaries(records,1)["repeatability"]
        self.assertEqual(repeat["paired_cases"],1)
        self.assertEqual(repeat["both_usable"],0)
        self.assertIsNone(repeat["conditional_agreement"])
        self.assertEqual(repeat["usable_and_consistent_rate"],0)

    def test_subset_retains_full_benchmark_size_without_a_gate(self):
        c=case();record=assessed(c,judgment("coverage",["covered"]))
        metrics=validation.trial_summaries([record],48)
        self.assertEqual(metrics["case_count"],48)
        self.assertEqual(metrics["combined"]["exact_case_accuracy"]["total"],1)
        self.assertNotIn("smoke_gate_passed",metrics)

    def test_combined_runs_keep_partition_and_failure_denominators(self):
        a=case();a["id"]="development"
        b=case();b.update(id="reserved",partition="reserved")
        rows=[assessed(a,judgment("coverage",["covered"]),t) for t in (1,2)]
        rows += [assessed(b,judgment("coverage",["contradicted"]),1),
                 assessed(b,dict(status="unscored",result=None),2)]
        metrics=validation.trial_summaries(rows,2)
        self.assertEqual(metrics["combined"]["exact_case_accuracy"],dict(correct=2,total=4,score=.5))
        self.assertEqual(metrics["combined"]["partitions"]["development"]["score"],1)
        self.assertEqual(metrics["combined"]["partitions"]["reserved"]["score"],0)
        self.assertEqual(metrics["trials"]["2"]["unscored_judgments"],1)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.root=validation.ROOT/"evaluation-data/qa-judge-validation"
        self.path=self.root/"cases.jsonl"
        self.manifest=json.loads((self.root/"manifest.json").read_text())
        self.cases=[json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def test_frozen_data_and_partitions(self):
        self.assertEqual(validation.digest(self.path),self.manifest["dataset_sha256"])
        self.assertEqual(len(self.cases),48)
        self.assertEqual(sum(c["partition"]=="development" for c in self.cases),30)
        self.assertEqual(sum(c["partition"]=="reserved" for c in self.cases),18)
        self.assertFalse(self.manifest["human_reviewed"])

    def test_reserved_cases_have_disjoint_stable_ids(self):
        reserved={c["id"] for c in self.cases if c["partition"]=="reserved"}
        development={c["id"] for c in self.cases if c["partition"]=="development"}
        self.assertFalse(reserved&development)
        self.assertEqual(len(reserved|development),48)
        for c in self.cases:
            self.assertFalse(c["human_reviewed"])
            self.assertNotIn("expected_labels",validation.payload_for_case(c))

    def test_expected_labels_are_never_sent_to_the_judge(self):
        for c in self.cases:
            payload=validation.payload_for_case(c)
            for key in ("expected_labels","expected_claims","expected_rationale","partition","tags","source_anchor_ids"):
                self.assertNotIn(key,payload)
            if c["stage"]=="grounding":
                self.assertEqual(set(payload),{"question","generated_answer","retrieved_context"})

    def test_offset_tampering_fails_source_verification(self):
        broken=copy.deepcopy(self.manifest)
        broken["dataset_sha256"]="wrong"
        with self.assertRaisesRegex(ValueError,"Dataset bytes"):
            validation.verify_inputs(self.cases,broken,self.path)

    def test_report_keeps_both_runs_combined_metrics_and_repeatability(self):
        c=self.cases[0]
        records=[assessed(c,judgment("coverage",c["expected_labels"]),t) for t in (1,2)]
        run=dict(judge_settings={"model_id":"test"},returned_models=["snapshot"],
                 source_verification={},dataset_path="frozen.jsonl",
                 dataset_sha256="frozen",judge_protocol_sha256="protocol",repetitions=2)
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/"report"
            metrics=validation.write_reports(directory,run,self.cases,records,self.manifest)
            self.assertEqual(metrics["combined"]["exact_case_accuracy"]["total"],2)
            self.assertEqual(set(metrics["trials"]),{"1","2"})
            self.assertEqual(metrics["repeatability"]["paired_cases"],1)
            self.assertIn("repetitions",(directory/"details.json").read_text())
            self.assertNotIn("gate",(directory/"details.json").read_text())


if __name__=="__main__":
    unittest.main()
