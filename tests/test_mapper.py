import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from canonify.config import Config, load_schema
from canonify.llm.gemini import GeminiClient
from canonify.models import MatchType
from canonify.rag.dictionary import LocalJsonDictionary
from canonify.rag.sop import SopRetriever
from canonify.agents.mapper import MapperAgent


class MapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.schema = load_schema()
        self.config = Config(mode="local", tenant_id="t1",
                             dictionary_path=Path(self.tmp.name) / "dict.json")
        self.dict = LocalJsonDictionary(self.config.dictionary_path)
        self.sop = SopRetriever(self.config.sop_dir, self.schema.schema_name)
        self.gemini = GeminiClient(self.config)
        self.mapper = MapperAgent(self.schema, self.dict, self.sop, self.gemini, self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def _by_col(self, mappings):
        out = {}
        for m in mappings:
            out.setdefault(m.canonical_column, []).append(m)
        return out

    def test_full_name_splits_into_first_and_last(self):
        mappings = self.mapper.map_columns(["Full Name"])
        cols = self._by_col(mappings)
        self.assertIn("first_name", cols)
        self.assertIn("last_name", cols)
        self.assertEqual(cols["first_name"][0].match_type, MatchType.DERIVED)

    def test_exact_alias_is_direct_match(self):
        mappings = self.mapper.map_columns(["DoB"])
        self.assertEqual(mappings[0].canonical_column, "date_of_birth")
        self.assertEqual(mappings[0].match_type, MatchType.DIRECT)
        self.assertTrue(mappings[0].sensitive)  # DoB is sensitive

    def test_learned_dictionary_hit_wins(self):
        self.dict.promote("weird_dob_header", "date_of_birth", "t1", 0.9)
        mappings = self.mapper.map_columns(["weird_dob_header"])
        self.assertEqual(mappings[0].canonical_column, "date_of_birth")
        self.assertIn("Learned dictionary", mappings[0].explanation)

    def test_unknown_header_is_low_confidence(self):
        mappings = self.mapper.map_columns(["Mystery Col"])
        self.assertLess(mappings[0].confidence, self.schema.thresholds["accept"])


if __name__ == "__main__":
    unittest.main()
