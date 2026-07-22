import unittest

import _bootstrap  # noqa: F401

from canonify.preprocess import clean_cell, detect_header_row, to_table


class PreprocessTests(unittest.TestCase):
    def test_clean_cell_null_tokens(self):
        for tok in ["", " ", "N/A", "null", "-", "#REF!", "  n/a "]:
            self.assertEqual(clean_cell(tok), "")
        self.assertEqual(clean_cell("  John\u00a0 Smith "), "John Smith")

    def test_detect_header_below_junk_rows(self):
        grid = [
            ["Company Report", "", ""],
            ["generated 2026", "", ""],
            ["", "", ""],
            ["First Name", "Last Name", "DoB"],
            ["John", "Smith", "1985-03-14"],
        ]
        # after removing empties the header is index 2 (0-based) within the compacted grid
        headers, rows, report = to_table(grid)
        self.assertEqual(headers, ["First Name", "Last Name", "DoB"])
        self.assertEqual(len(rows), 1)
        self.assertGreaterEqual(report.junk_rows_above_header, 1)

    def test_drops_empty_columns_and_dedupes_headers(self):
        grid = [
            ["Name", "", "Name", "DoB"],
            ["John", "", "Smith", "1985-03-14"],
        ]
        headers, rows, report = to_table(grid)
        # blank-header empty column removed; duplicate "Name" de-duplicated
        self.assertNotIn("", headers)
        self.assertEqual(len(set(headers)), len(headers))
        self.assertIn("Name", headers[0])

    def test_trailing_total_row_removed(self):
        grid = [
            ["First", "Last"],
            ["John", "Smith"],
            ["Total", ""],
        ]
        headers, rows, report = to_table(grid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(report.trailing_junk_rows_removed, 1)


if __name__ == "__main__":
    unittest.main()
