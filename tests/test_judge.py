import unittest

import _bootstrap  # noqa: F401

from canonify.config import load_schema
from canonify.models import CellTransform, ColumnMapping, MatchType, Verdict
from canonify.agents.judge import JudgeAgent


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.schema = load_schema()
        self.judge = JudgeAgent(self.schema)

    def test_high_confidence_mapping_accepted(self):
        m = [ColumnMapping("email", ["Email"], MatchType.DIRECT, 0.97, "")]
        decisions, queue = self.judge.judge(m, [])
        self.assertEqual(decisions[0].verdict, Verdict.ACCEPT)
        self.assertEqual(queue, [])

    def test_sensitive_field_needs_higher_bar(self):
        # 0.88 would accept a normal field but not a sensitive one (accept+bonus).
        m = [ColumnMapping("date_of_birth", ["dt"], MatchType.INFERRED, 0.88, "", sensitive=True)]
        decisions, queue = self.judge.judge(m, [])
        self.assertEqual(decisions[0].verdict, Verdict.REVIEW)
        self.assertEqual(len(queue), 1)

    def test_low_confidence_mapping_rejected(self):
        m = [ColumnMapping("email", ["zzz"], MatchType.INFERRED, 0.2, "")]
        decisions, _ = self.judge.judge(m, [])
        self.assertEqual(decisions[0].verdict, Verdict.REVIEW if 0.2 >= self.schema.thresholds["review"] else Verdict.REJECT)

    def test_flagged_transform_blocks_silent_acceptance(self):
        t = [CellTransform("gender", "X", None, 0.3, "ambiguous", needs_review=True)]
        decisions, queue = self.judge.judge([], t)
        transform_decisions = [d for d in decisions if d.kind == "transform"]
        self.assertNotEqual(transform_decisions[0].verdict, Verdict.ACCEPT)
        self.assertTrue(any(q["type"] == "transform" for q in queue))


if __name__ == "__main__":
    unittest.main()
