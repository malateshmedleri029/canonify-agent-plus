"""Robust table readers that return a RAW 2-D grid (list of rows of strings).

Header detection and cleaning happen later in `preprocess.py`, because in the real world the header
is frequently NOT the first row. These readers only job: get the raw cells out reliably.

Supported with ZERO dependencies:
  * .csv / .tsv / .txt  — encoding + delimiter sniffing (comma/semicolon/tab/pipe).
  * .xlsx               — pure-stdlib reader (zipfile + xml.etree), incl. shared strings, inline
                          strings, and Excel-serial DATE detection via styles.xml.

Optional (needs extras):
  * .xls (legacy binary) — uses `xlrd`/`pandas` if installed, else a clear error.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from xml.etree import ElementTree as ET

Grid = List[List[str]]

# Excel's epoch is 1899-12-30 (accounts for the legacy 1900 leap-year bug for dates >= 1900-03-01).
_EXCEL_EPOCH = datetime(1899, 12, 30)
# Built-in number-format ids that denote dates/times.
_BUILTIN_DATE_FMT_IDS = set(range(14, 23)) | {27, 30, 36, 45, 46, 47, 50, 57, 58}


# ---------------------------------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------------------------------
def read_grid(path) -> Grid:
    """Read any supported file into a raw list-of-rows grid of strings."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv", ".txt"):
        return _read_csv_grid(path)
    if suffix == ".xlsx":
        return _read_xlsx_grid(path)
    if suffix == ".xls":
        return _read_xls_grid(path)
    raise ValueError(f"Unsupported file type '{suffix}'. Use .csv, .tsv, .txt, .xlsx, or .xls.")


# ---------------------------------------------------------------------------------------------------
# CSV / delimited
# ---------------------------------------------------------------------------------------------------
def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _read_csv_grid(path: Path) -> Grid:
    text = _decode(path.read_bytes())
    # Normalize exotic newlines and non-breaking spaces early.
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel  # default to comma
    reader = csv.reader(io.StringIO(text), dialect)
    return [list(row) for row in reader]


# ---------------------------------------------------------------------------------------------------
# XLSX (pure stdlib)
# ---------------------------------------------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _col_to_idx(cell_ref: str) -> int:
    letters = re.match(r"[A-Za-z]+", cell_ref or "")
    if not letters:
        return 0
    idx = 0
    for ch in letters.group(0).upper():
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def _serial_to_iso(serial: float) -> str:
    return (_EXCEL_EPOCH + timedelta(days=float(serial))).strftime("%Y-%m-%d")


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings: List[str] = []
    for _, si in ET.iterparse(io.BytesIO(data)):
        if _local(si.tag) != "si":
            continue
        # Concatenate all <t> descendants (handles rich-text runs).
        text = "".join(t.text or "" for t in si.iter() if _local(t.tag) == "t")
        strings.append(text)
        si.clear()
    return strings


def _xlsx_date_style_ids(zf: zipfile.ZipFile) -> set:
    """Return the set of cellXfs indices that render as dates."""
    try:
        data = zf.read("xl/styles.xml")
    except KeyError:
        return set()
    root = ET.fromstring(data)
    custom_date_fmt_ids = set()
    for numfmts in root:
        if _local(numfmts.tag) != "numFmts":
            continue
        for nf in numfmts:
            fmt_id = nf.get("numFmtId")
            code = (nf.get("formatCode") or "").lower()
            if fmt_id and re.search(r"[dmy]", code) and "[" not in code.replace("[$-", ""):
                # crude but effective: format code mentions d/m/y
                if any(k in code for k in ("y", "d")) or "mmm" in code:
                    custom_date_fmt_ids.add(fmt_id)
    date_style_ids = set()
    cell_xfs = None
    for child in root:
        if _local(child.tag) == "cellXfs":
            cell_xfs = child
            break
    if cell_xfs is not None:
        for i, xf in enumerate(cell_xfs):
            fmt_id = xf.get("numFmtId")
            if fmt_id is None:
                continue
            if (fmt_id in custom_date_fmt_ids) or (fmt_id.isdigit() and int(fmt_id) in _BUILTIN_DATE_FMT_IDS):
                date_style_ids.add(str(i))
    return date_style_ids


def _first_sheet_path(zf: zipfile.ZipFile) -> str:
    names = zf.namelist()
    # Resolve the first sheet via workbook rels; fall back to sheet1.xml.
    try:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
        for sheets in wb:
            if _local(sheets.tag) != "sheets":
                continue
            for sheet in sheets:
                rid = None
                for k, v in sheet.attrib.items():
                    if _local(k) == "id":
                        rid = v
                target = rid_to_target.get(rid)
                if target:
                    target = target.lstrip("/")
                    return target if target.startswith("xl/") else f"xl/{target}"
    except (KeyError, ET.ParseError):
        pass
    for candidate in ("xl/worksheets/sheet1.xml",):
        if candidate in names:
            return candidate
    sheets = [n for n in names if n.startswith("xl/worksheets/") and n.endswith(".xml")]
    if not sheets:
        raise ValueError("No worksheet found in xlsx.")
    return sorted(sheets)[0]


def _read_xlsx_grid(path: Path) -> Grid:
    with zipfile.ZipFile(path) as zf:
        shared = _xlsx_shared_strings(zf)
        date_styles = _xlsx_date_style_ids(zf)
        sheet_path = _first_sheet_path(zf)
        data = zf.read(sheet_path)

    grid: Grid = []
    for _, row in ET.iterparse(io.BytesIO(data)):
        if _local(row.tag) != "row":
            continue
        cells: Dict[int, str] = {}
        for c in row:
            if _local(c.tag) != "c":
                continue
            ref = c.get("r", "")
            col = _col_to_idx(ref)
            ctype = c.get("t")
            style = c.get("s")
            value = ""
            v_el = None
            is_el = None
            for child in c:
                lt = _local(child.tag)
                if lt == "v":
                    v_el = child
                elif lt == "is":
                    is_el = child
            if ctype == "s" and v_el is not None and v_el.text is not None:
                idx = int(v_el.text)
                value = shared[idx] if 0 <= idx < len(shared) else ""
            elif ctype == "inlineStr" and is_el is not None:
                value = "".join(t.text or "" for t in is_el.iter() if _local(t.tag) == "t")
            elif ctype == "b" and v_el is not None:
                value = "TRUE" if v_el.text == "1" else "FALSE"
            elif v_el is not None and v_el.text is not None:
                raw = v_el.text
                if style is not None and style in date_styles:
                    try:
                        value = _serial_to_iso(float(raw))
                    except ValueError:
                        value = raw
                else:
                    value = raw
            cells[col] = value
        if cells:
            width = max(cells) + 1
            grid.append([cells.get(i, "") for i in range(width)])
        else:
            grid.append([])
    return grid


# ---------------------------------------------------------------------------------------------------
# XLS (legacy) — optional
# ---------------------------------------------------------------------------------------------------
def _read_xls_grid(path: Path) -> Grid:  # pragma: no cover - needs optional dep
    try:
        import xlrd  # type: ignore
    except ImportError:
        try:
            import pandas as pd  # type: ignore
            df = pd.read_excel(path, header=None, dtype=str).fillna("")
            return df.values.tolist()
        except ImportError as exc:
            raise ValueError(
                "Reading legacy .xls needs an optional dependency. Install `xlrd` or `pandas`, "
                "or convert the file to .xlsx / .csv."
            ) from exc
    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_index(0)
    return [[str(sheet.cell_value(r, cidx)) for cidx in range(sheet.ncols)]
            for r in range(sheet.nrows)]
