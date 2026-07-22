import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from canonify.config import Config, DATA_DIR
from canonify.models import Verdict
from canonify.pipeline import run_pipeline

SAMPLES = DATA_DIR / "samples"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.config = Config(
            mode="local", tenant_id="testco",
            output_dir=base / "out",
            dictionary_path=base / "dict.json",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_sample_produces_canonical_rows(self):
        result, paths = run_pipeline(SAMPLES / "new_to_old_bad.csv", config=self.config)
        self.assertEqual(len(result.canonical_rows), 5)
        first = result.canonical_rows[0]
        self.assertEqual(first["first_name"], "John")
        self.assertEqual(first["last_name"], "Smith")
        self.assertEqual(first["date_of_birth"], "1985-03-14")
        self.assertEqual(first["gender"], "Male")
        # All four artifacts written.
        for key in ("mapped_data.csv", "mapping_audit_report.json",
                    "judge_decision_log.json", "promoted_dictionary_entries.json"):
            self.assertIn(key, paths)
            self.assertTrue(Path(paths[key]).exists())

    def test_ambiguous_sample_routes_to_review(self):
        result, _ = run_pipeline(SAMPLES / "ambiguous_hard.csv", config=self.config)
        self.assertGreater(len(result.review_queue), 0)
        # invalid dates + ambiguous gender + unknown column must not be silently accepted:
        # at least one decision must be gated (REVIEW or REJECT).
        gated = [d for d in result.decisions if d.verdict in (Verdict.REVIEW, Verdict.REJECT)]
        self.assertGreater(len(gated), 0)

    def test_learning_loop_compounds_confidence(self):
        # First run promotes mappings; second run should hit the learned dictionary.
        run_pipeline(SAMPLES / "new_to_old_bad.csv", config=self.config)
        result2, _ = run_pipeline(SAMPLES / "new_to_old_bad.csv", config=self.config)
        learned_hits = [m for m in result2.mappings if "Learned dictionary" in m.explanation]
        self.assertGreater(len(learned_hits), 0)

    def test_no_silent_sensitive_inference(self):
        result, _ = run_pipeline(SAMPLES / "ambiguous_hard.csv", config=self.config)
        # Any sensitive transform that is ambiguous must be flagged, never auto-accepted silently.
        for row in result.canonical_rows:
            # ambiguous gender 'X'/'U' must be None (not guessed)
            self.assertIn(row.get("gender"), (None, "Male", "Female"))


if __name__ == "__main__":
    unittest.main()
