"""Generate a deliberately messy .xlsx sample using ONLY the stdlib (zipfile + xml).

Mirrors the horrors of real Excel exports: a title row, a blank row, a real header row, a blank
column, Excel-serial DATE cells (date-styled), an ambiguous gender, and a trailing total row.

Run:  python data/samples/_make_xlsx_sample.py
"""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

EPOCH = datetime(1899, 12, 30)
OUT = Path(__file__.replace("_make_xlsx_sample.py", "messy_roster.xlsx"))


def serial(d: str) -> int:
    return (datetime.strptime(d, "%Y-%m-%d") - EPOCH).days


# (value, kind) where kind in {"s": string, "d": date-serial, "": empty}
ROWS = [
    [("XYZ - ABC Benefits Export Q3 (CONFIDENTIAL)", "s")],
    [],
    [("Full Name", "s"), ("Date Of Birth", "s"), ("Sex", "s"),
     ("", ""), ("Relationship", "s"), ("Email Address", "s")],
    [("Smith, John", "s"), (serial("1985-03-14"), "d"), ("M", "s"),
     ("", ""), ("Employee", "s"), ("john.smith@example.com", "s")],
    [("Doe, Jane", "s"), (serial("1990-07-22"), "d"), ("F", "s"),
     ("", ""), ("Spouse", "s"), ("jane.doe@example.com", "s")],
    [("Lee, Sam", "s"), (serial("2015-12-01"), "d"), ("1", "s"),
     ("", ""), ("Child", "s"), ("sam.lee@example.com", "s")],
    [("Park, Dana", "s"), (serial("1979-11-03"), "d"), ("X", "s"),
     ("", ""), ("Cousin", "s"), ("dana@example.com", "s")],
    [("Total", "s")],
]


def col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


def cell_xml(r: int, c: int, value, kind: str) -> str:
    ref = f"{col_letter(c)}{r}"
    if kind == "s":
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'
    if kind == "d":
        return f'<c r="{ref}" s="1"><v>{value}</v></c>'
    return f'<c r="{ref}"/>'


def sheet_xml() -> str:
    rows_xml = []
    for ri, row in enumerate(ROWS, start=1):
        cells = "".join(cell_xml(ri, ci, v, k) for ci, (v, k) in
                        [(ci, cell) for ci, cell in enumerate(row)]) if row else ""
        rows_xml.append(f'<row r="{ri}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rows_xml)}</sheetData></worksheet>'
    )


CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    '</Types>'
)
RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    '</Relationships>'
)
WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="Roster" sheetId="1" r:id="rId1"/></sheets></workbook>'
)
WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '</Relationships>'
)
STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="2">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '</cellXfs>'
    '</styleSheet>'
)


def main() -> None:
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("xl/workbook.xml", WORKBOOK)
        zf.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS)
        zf.writestr("xl/styles.xml", STYLES)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml())
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
