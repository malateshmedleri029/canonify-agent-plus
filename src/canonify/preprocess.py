"""Worst-of-worst preprocessing: turn a raw, ugly grid into a clean (headers, rows) table.

Real-world files (especially exported Excel) routinely have:
  * title / logo / "Report generated on ..." junk rows ABOVE the real header,
  * blank separator rows and blank columns,
  * merged cells leaving sparse values,
  * duplicate or blank column names ("", "Unnamed: 3"),
  * null-ish tokens: "", "N/A", "null", "-", "#REF!", "#N/A",
  * trailing totals / footnote rows,
  * non-breaking spaces and stray whitespace.

This module fixes all of the above and emits a `PreprocessReport` so the cleanup is observable and
auditable (surfaced in the UI and the audit report).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

Grid = List[List[str]]

NULL_TOKENS = {
    "", "-", "--", "n/a", "na", "null", "none", "nil", "nan", ".",
    "#ref!", "#n/a", "#value!", "#name?", "#div/0!", "(blank)", "unknown",
}

_MAX_HEADER_SEARCH_ROWS = 25


@dataclass
class PreprocessReport:
    header_row_index: int = 0
    total_raw_rows: int = 0
    data_rows: int = 0
    dropped_empty_rows: int = 0
    dropped_empty_columns: int = 0
    renamed_headers: Dict[str, str] = field(default_factory=dict)
    junk_rows_above_header: int = 0
    trailing_junk_rows_removed: int = 0

    def to_dict(self) -> Dict:
        return {
            "header_row_index": self.header_row_index,
            "total_raw_rows": self.total_raw_rows,
            "data_rows": self.data_rows,
            "dropped_empty_rows": self.dropped_empty_rows,
            "dropped_empty_columns": self.dropped_empty_columns,
            "junk_rows_above_header": self.junk_rows_above_header,
            "trailing_junk_rows_removed": self.trailing_junk_rows_removed,
            "renamed_headers": self.renamed_headers,
        }


def clean_cell(value) -> str:
    if value is None:
        return ""
    s = str(value).replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    if s.lower() in NULL_TOKENS:
        return ""
    return s


def _row_is_empty(row: List[str]) -> bool:
    return all(not c for c in row)


def _score_header_row(row: List[str], below: List[List[str]]) -> float:
    non_empty = [c for c in row if c]
    if len(non_empty) < 2:  # a lone title cell is not a header
        return -1.0
    width = max(1, len(row))
    frac_filled = len(non_empty) / width
    labelish = sum(1 for c in non_empty if re.search(r"[A-Za-z]", c) and len(c) <= 40)
    frac_label = labelish / len(non_empty)
    uniq = len({c.lower() for c in non_empty}) / len(non_empty)
    # Data rows below a real header should be reasonably filled.
    below_fill = 0.0
    sample = below[:3]
    for r in sample:
        ne = [c for c in r if c]
        below_fill += len(ne) / max(1, len(r))
    below_fill = below_fill / max(1, len(sample)) if sample else 0.0
    return frac_filled * 1.0 + frac_label * 1.5 + uniq * 0.5 + below_fill * 1.0


def detect_header_row(grid: Grid) -> int:
    best_idx, best_score = 0, -2.0
    limit = min(len(grid), _MAX_HEADER_SEARCH_ROWS)
    for i in range(limit):
        score = _score_header_row(grid[i], grid[i + 1:])
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx


def _dedupe_headers(headers: List[str], report: PreprocessReport) -> List[str]:
    out: List[str] = []
    seen: Dict[str, int] = {}
    for i, h in enumerate(headers):
        name = h if h else f"column_{i + 1}"
        if not h:
            report.renamed_headers[f"<blank #{i + 1}>"] = name
        key = name.lower()
        if key in seen:
            seen[key] += 1
            new_name = f"{name}_{seen[key]}"
            report.renamed_headers[name] = new_name
            name = new_name
        else:
            seen[key] = 1
        out.append(name)
    return out


def to_table(grid: Grid) -> Tuple[List[str], List[Dict[str, str]], PreprocessReport]:
    report = PreprocessReport(total_raw_rows=len(grid))

    # 1. Clean every cell.
    cleaned: Grid = [[clean_cell(c) for c in row] for row in grid]

    # 2. Drop fully-empty rows.
    non_empty_rows = [r for r in cleaned if not _row_is_empty(r)]
    report.dropped_empty_rows = len(cleaned) - len(non_empty_rows)
    if not non_empty_rows:
        return [], [], report

    # 3. Detect the real header row.
    header_idx = detect_header_row(non_empty_rows)
    report.header_row_index = header_idx
    report.junk_rows_above_header = header_idx

    header_row = non_empty_rows[header_idx]
    body = non_empty_rows[header_idx + 1:]

    # 4. Normalize header width and pad body rows to it.
    width = len(header_row)
    body = [r + [""] * (width - len(r)) if len(r) < width else r[:width] for r in body]

    # 5. Drop columns that are empty in BOTH header and all data.
    keep_cols = []
    for c in range(width):
        header_blank = not header_row[c]
        col_blank = all(not (r[c] if c < len(r) else "") for r in body)
        if not (header_blank and col_blank):
            keep_cols.append(c)
    report.dropped_empty_columns = width - len(keep_cols)

    headers_raw = [header_row[c] for c in keep_cols]
    headers = _dedupe_headers(headers_raw, report)

    # 6. Build dict rows; drop rows that became fully empty after column pruning
    #    and obvious trailing junk (single-cell footnote/total rows).
    rows: List[Dict[str, str]] = []
    trailing_junk = 0
    for r in body:
        values = [r[c] for c in keep_cols]
        filled = [v for v in values if v]
        if not filled:
            continue
        if len(filled) == 1 and re.match(r"(?i)^(total|totals|grand total|note|notes)\b", filled[0]):
            trailing_junk += 1
            continue
        rows.append({headers[i]: values[i] for i in range(len(headers))})

    report.trailing_junk_rows_removed = trailing_junk
    report.data_rows = len(rows)
    return headers, rows, report
