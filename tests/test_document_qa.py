"""Fresh document-QA generation feeds the same answer judge, without chunk scoring."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import yaml

import evaluate_document_qa as evaluation


def record():
    return dict(id="sample",question="Question",reference_answer="Reference",atomic_required_facts=[],
                evidence_records=[],allowed_sources=["book.pdf"],answerability={"label":"answerable"},
                review_status="reviewed_and_verified",review_method="codex_source_audit",evaluation_eligibility="eligible")


class PredictionTests(unittest.TestCase):
    def test_collects_original_answers_and_context_without_chunk_metrics(self):
        pipeline=Mock()
        pipeline.run.return_value=dict(generated_answer="Answer",final_context="Exact supplied context",
            selected_sources=["book.pdf"],final_chunks=[{"text":"Unused chunk"}],metrics={"evidence_text_precision":0})
        result=evaluation.collect_predictions([record()],pipeline)[0]
        self.assertEqual(result["generated_answer"],"Answer")
        self.assertEqual(result["final_context"],"Exact supplied context")
        self.assertNotIn("metrics",result)
        self.assertNotIn("final_chunks",result)
        pipeline.run.assert_called_once_with("Question")

    def test_generation_failure_is_retained_without_sensitive_exception_text(self):
        pipeline=Mock();pipeline.run.side_effect=RuntimeError("sensitive request data")
        result=evaluation.collect_predictions([record()],pipeline)[0]
        self.assertEqual(result["generated_answer"],"")
        self.assertEqual(result["errors"],["Pipeline call failed: RuntimeError"])
        self.assertNotIn("sensitive",json.dumps(result))

    def test_review_eligibility_is_preserved(self):
        item=record()
        self.assertTrue(evaluation.record_is_eligible(item))
        self.assertFalse(evaluation.record_is_eligible({**item,"review_method":"human"}))
        self.assertFalse(evaluation.record_is_eligible({**item,"evaluation_eligibility":"quarantined"}))

    def test_duplicate_question_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"data.jsonl"
            path.write_text(json.dumps(record())+"\n"+json.dumps(record())+"\n")
            with self.assertRaisesRegex(ValueError,"Duplicate dataset ID"):
                evaluation.load_dataset(path)

    def test_invalid_prediction_path_stops_before_generation(self):
        config=yaml.safe_load(evaluation.CONFIG_PATH.read_text())
        config["qa_answer_evaluation"]["input_path"]=config["document_qa_evaluation"]["results_dir"]+"/details.json"
        with patch.object(evaluation.yaml,"safe_load",return_value=config), patch.object(evaluation,"load_dataset") as load:
            with self.assertRaisesRegex(ValueError,"separate input file"):
                evaluation.main(["--limit","1"])
        load.assert_not_called()

    def exercise_main(self,mode):
        config=yaml.safe_load(evaluation.CONFIG_PATH.read_text())
        config=copy.deepcopy(config);config["indexing"]["mode"]=mode
        pipeline=Mock();pipeline.run.return_value=dict(generated_answer="Answer",final_context="Context")
        pipeline.persisted_index_settings.return_value={"text_normalization":{"enabled":True,"version":1}}
        factory=Mock(return_value=pipeline)
        pdfs=[Path("a.pdf"),Path("b.pdf")]
        with patch.object(evaluation.yaml,"safe_load",return_value=config), \
             patch.object(evaluation,"load_dataset",return_value=[record()]), \
             patch.object(evaluation.Path,"glob",return_value=iter(pdfs)) as glob, \
             patch.object(evaluation,"atomic_json") as save, \
             patch.object(evaluation,"judge_answers") as judge, \
             patch.dict(sys.modules,{"main":SimpleNamespace(RAGPipeline=factory)}):
            evaluation.main(["--limit","1"])
        factory.assert_called_once_with(config,pdfs if mode=="build" else [])
        if mode=="load":
            glob.assert_not_called()
        predictions=save.call_args.args[1]
        self.assertEqual(len(predictions["questions"]),1)
        self.assertNotIn("metric_summaries",predictions)
        self.assertEqual(predictions["questions"][0]["generated_answer"],"Answer")
        judge.assert_called_once_with(["--limit","1"])

    def test_build_indexes_full_corpus_then_judges_generated_subset(self):
        self.exercise_main("build")

    def test_load_reuses_indexes_then_judges_generated_subset(self):
        self.exercise_main("load")


if __name__=="__main__":
    unittest.main()
