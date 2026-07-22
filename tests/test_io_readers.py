import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from canonify.io_readers import read_grid
from canonify.config import DATA_DIR

SAMPLES = DATA_DIR / "samples"


class CsvReaderTests(unittest.TestCase):
    def test_semicolon_delimiter_sniffed(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
            fh.write("a;b;c\n1;2;3\n")
            path = fh.name
        grid = read_grid(path)
        Path(path).unlink()
        self.assertEqual(grid[0], ["a", "b", "c"])
        self.assertEqual(grid[1], ["1", "2", "3"])

    def test_bom_stripped(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as fh:
            fh.write("\ufeffname,dob\nJohn,1985\n".encode("utf-8"))
            path = fh.name
        grid = read_grid(path)
        Path(path).unlink()
        self.assertEqual(grid[0][0], "name")  # BOM removed


class XlsxReaderTests(unittest.TestCase):
    def test_reads_bundled_messy_xlsx(self):
        grid = read_grid(SAMPLES / "messy_roster.xlsx")
        flat = [c for row in grid for c in row]
        self.assertIn("Full Name", flat)
        # Excel-serial date converted to ISO by the reader (styles-based detection)
        self.assertIn("1985-03-14", flat)

    def test_unsupported_extension_raises(self):
        with self.assertRaises(ValueError):
            read_grid("foo.parquet")


if __name__ == "__main__":
    unittest.main()
