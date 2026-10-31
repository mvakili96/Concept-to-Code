"""Offline checks for budget-aware LeetCode recall and report consistency."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

import evaluate_leetcode_recommendation as evaluation


def record(labels, total_targets, target_indexes=None):
    items = [dict(problem_id=f"problem-{i}", pair_id=f"pair-{i}", label=label, status="verified")
             for i, label in enumerate(labels)]
    if target_indexes is None:
        target_indexes = [i for i, label in enumerate(labels) if label in evaluation.USEFUL]
    return dict(status="completed", kind="ordinary", assessment=dict(
        items=items, label_counts=dict(evaluation.Counter(labels)), stage_coverage=dict(recommendations=dict(
            status="scored", total_targets=total_targets,
            matched_target_ids=[f"pair-{i}" for i in target_indexes]))))


class CappedRecallTests(unittest.TestCase):
    def test_all_three_positive_grades_receive_equal_credit(self):
        result = evaluation.capped_recall(record(
            ["direct_match", "related_practice", "stretch_connection"], 71), 3)
        self.assertEqual((result["matched_targets"], result["denominator"], result["score"]), (3, 3, 1))

    def test_fewer_targets_than_budget(self):
        result = evaluation.capped_recall(record(["direct_match", "related_practice"], 2), 3)
        self.assertEqual((result["denominator"], result["score"]), (2, 1))

    def test_cutoff_uses_returned_order_and_configured_budget(self):
        sample = record(["unrelated", "related_practice", "stretch_connection"], 20)
        self.assertEqual(evaluation.capped_recall(sample, 1)["score"], 0)
        self.assertEqual(evaluation.capped_recall(sample, 2)["score"], .5)
        self.assertAlmostEqual(evaluation.capped_recall(sample, 3)["score"], 2 / 3)
        self.assertEqual(evaluation.capped_recall(sample, 5)["score"], .4)

    def test_duplicate_identities_use_one_output_slot(self):
        sample = record(["direct_match", "related_practice"], 12)
        sample["assessment"]["items"].insert(1, copy.deepcopy(sample["assessment"]["items"][0]))
        result = evaluation.capped_recall(sample, 3)
        self.assertEqual((result["matched_targets"], result["denominator"]), (2, 3))

    def test_uncertain_unassessed_and_unrelated_get_no_hit_credit(self):
        sample = record(["uncertain", "unassessed", "unrelated"], 12)
        result = evaluation.capped_recall(sample, 3)
        self.assertEqual((result["status"], result["score"]), ("scored", 0))

    def test_only_explicit_targets_count_for_historical_target_policy(self):
        sample = record(["direct_match", "related_practice", "stretch_connection"], 6, target_indexes=[1])
        self.assertAlmostEqual(evaluation.capped_recall(sample, 3)["score"], 1 / 3)

    def test_completed_abstention_is_zero(self):
        self.assertEqual(evaluation.capped_recall(record([], 12), 3)["score"], 0)

    def test_controls_and_empty_target_sets_are_not_applicable(self):
        sample = record([], 0)
        self.assertEqual(evaluation.capped_recall(sample, 3)["status"], "not_applicable")
        sample["kind"] = "explicit_naming_control"
        self.assertEqual(evaluation.capped_recall(sample, 3)["status"], "not_applicable")

    def test_failed_execution_and_invalid_mappings_are_unscored(self):
        sample = record(["direct_match"], 12)
        for failure in ("execution", "stage", "item", "target_records", "missing_hit"):
            with self.subTest(failure=failure):
                broken = copy.deepcopy(sample)
                if failure == "execution":
                    broken["status"] = "failed"
                elif failure == "stage":
                    broken["assessment"]["stage_coverage"]["recommendations"]["status"] = "unscored"
                elif failure == "item":
                    broken["assessment"]["label_counts"]["unscored"] = 1
                elif failure == "target_records":
                    broken["assessment"]["stage_coverage"]["recommendations"]["matched_target_ids"] = [None]
                else:
                    broken["assessment"]["stage_coverage"]["recommendations"]["matched_target_ids"] = ["missing"]
                result = evaluation.capped_recall(broken, 3)
                self.assertEqual((result["status"], result["score"]), ("unscored", None))

    def test_invalid_cutoff_is_rejected(self):
        for cutoff in (0, -1, True, 1.5, "3", None):
            with self.subTest(cutoff=cutoff), self.assertRaises(ValueError):
                evaluation.capped_recall(record([], 12), cutoff)


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = evaluation.json_read(evaluation.ROOT / (
            "evaluation-results/leetcode-recommendation/v2/experiments/"
            "title-selection-full-source-fixed/details.json"))

    def completed_record(self, labels, total_targets):
        sample = copy.deepcopy(self.saved["questions"][0])
        new = record(labels, total_targets)
        sample["assessment"]["items"] = new["assessment"]["items"]
        sample["assessment"]["label_counts"] = new["assessment"]["label_counts"]
        sample["assessment"]["stage_coverage"]["recommendations"] = new["assessment"]["stage_coverage"]["recommendations"]
        return sample

    def test_macro_average_and_excluded_records(self):
        first = self.completed_record(["direct_match", "related_practice"], 2)
        second = self.completed_record(["stretch_connection"], 5)
        control = {**copy.deepcopy(first), "kind": "explicit_naming_control"}
        control["assessment"]["control_conformant"] = False
        failed = {**copy.deepcopy(first), "status": "failed"}
        result = evaluation.summarize([first, second, control, failed], 3)["capped_recall"]
        self.assertAlmostEqual(result["score"], (1 + 1 / 3) / 2)
        self.assertNotEqual(result["score"], 3 / 5)
        self.assertEqual((result["scored_questions"], result["not_applicable_questions"],
                          result["unscored_questions"]), (2, 1, 1))

    def test_no_eligible_questions(self):
        self.assertIsNone(evaluation.summarize([], 3)["capped_recall"]["score"])

    def test_saved_baseline_and_existing_metrics_are_preserved(self):
        result = evaluation.summarize(self.saved["questions"], 3)
        self.assertAlmostEqual(result["capped_recall"]["score"], 0.5462962962962963)
        self.assertEqual(result["capped_recall"]["scored_questions"], 36)
        for key, value in self.saved["metrics"].items():
            if key != "capped_recall":
                self.assertEqual(result[key], value, key)

    def test_writer_uses_saved_cutoff_and_preserves_inference_records(self):
        run = copy.deepcopy(self.saved["run"])
        run["config"]["related_problem"]["recommendation_validation"]["max_recommendations"] = 2
        sample = self.completed_record(["unrelated", "related_practice", "stretch_connection"], 20)
        original = copy.deepcopy(sample)
        with tempfile.TemporaryDirectory() as directory:
            evaluation.write_reports(directory, run, [sample])
            details = json.loads((Path(directory) / "details.json").read_text())
            self.assertEqual(details["metrics"]["capped_recall"]["score"], .5)
            self.assertEqual(details["capped_recall_by_question"][sample["id"]]["denominator"], 2)
            self.assertEqual(details["questions"], [original])
            self.assertEqual(details["run"], run)
            with (Path(directory) / "per_question.csv").open(newline="") as file:
                row = next(csv.DictReader(file))
            self.assertEqual((row["capped_recall_cutoff"], row["capped_recall"],
                              row["capped_recall_matched_targets"]), ("2", "0.5", "1"))
            summary = (Path(directory) / "summary.md").read_text()
            self.assertIn("| Capped recall@2 (macro) | 50.0% |", summary)
            self.assertIn("| Full annotated-target recall (micro) | 2/20 (10.0%) |", summary)
        self.assertEqual(sample, original)


if __name__ == "__main__":
    unittest.main()
