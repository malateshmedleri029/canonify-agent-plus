import unittest

import _bootstrap  # noqa: F401

from canonify.config import load_schema
from canonify.agents.transformer import TransformerAgent, _parse_date, _split_full_name


class TransformerUnitTests(unittest.TestCase):
    def test_split_full_name_last_comma_first(self):
        self.assertEqual(_split_full_name("Smith, John"), ("John", "Smith"))

    def test_split_full_name_space(self):
        self.assertEqual(_split_full_name("John Smith"), ("John", "Smith"))

    def test_parse_various_date_formats(self):
        self.assertEqual(_parse_date("03/14/1985"), "1985-03-14")
        self.assertEqual(_parse_date("1990-07-22"), "1990-07-22")
        self.assertEqual(_parse_date("22-Aug-1978"), "1978-08-22")

    def test_parse_invalid_date_returns_none(self):
        self.assertIsNone(_parse_date("02/30/1991"))
        self.assertIsNone(_parse_date("not-a-date"))


class TransformerAgentTests(unittest.TestCase):
    def setUp(self):
        self.schema = load_schema()
        self.agent = TransformerAgent(self.schema)

    def _run(self, headers, rows, mappings):
        return self.agent.transform(headers, rows, mappings)

    def test_gender_standardization(self):
        from canonify.models import ColumnMapping, MatchType
        m = [ColumnMapping("gender", ["Sex"], MatchType.DIRECT, 0.97, "", sensitive=True)]
        rows = [{"Sex": "M"}, {"Sex": "0"}, {"Sex": "female"}]
        canon, _ = self._run(["Sex"], rows, m)
        self.assertEqual([r["gender"] for r in canon], ["Male", "Female", "Female"])

    def test_ambiguous_gender_flagged_for_review(self):
        from canonify.models import ColumnMapping, MatchType
        m = [ColumnMapping("gender", ["Gndr"], MatchType.DIRECT, 0.97, "", sensitive=True)]
        canon, transforms = self._run(["Gndr"], [{"Gndr": "X"}], m)
        self.assertIsNone(canon[0]["gender"])
        self.assertTrue(transforms[0].needs_review)


if __name__ == "__main__":
    unittest.main()
