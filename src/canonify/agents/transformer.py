"""Transformer agent: standardize cell values to the target types/formats.

Handles the three core cell transforms from the brief:
  * String manipulation   — Full Name -> first_name / last_name.
  * Categorical standard.  — e.g. M/F/1/0 -> Male/Female; Employee -> Self.
  * Date formatting        — varied formats -> strict ISO (YYYY-MM-DD).

Every transform carries a confidence + explanation. Ambiguous or sensitive edge cases are flagged
`needs_review` so the Judge routes them to a human instead of silently inferring.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..config import CanonicalSchema, SchemaField
from ..models import CellTransform, ColumnMapping

_DATE_FORMATS = [
    "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%Y/%m/%d",
    "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y", "%b %d, %Y", "%d.%m.%Y", "%Y.%m.%d",
]
_EXCEL_EPOCH = datetime(1899, 12, 30)


def _split_full_name(raw: str) -> Tuple[str, str]:
    raw = (raw or "").strip()
    if "," in raw:                       # "Last, First"
        last, _, first = raw.partition(",")
        return first.strip(), last.strip()
    parts = raw.split()
    if len(parts) >= 2:                  # "First ... Last"
        return parts[0], parts[-1]
    return raw, ""


def _parse_date(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Last resort: a bare Excel serial that slipped through as a number on a DATE column.
    # Constrained to a plausible range (~1955-2079) so we never mangle IDs/zip codes.
    if re.fullmatch(r"\d{5}", raw):
        serial = int(raw)
        if 20000 <= serial <= 60000:
            return (_EXCEL_EPOCH + timedelta(days=serial)).strftime("%Y-%m-%d")
    return None


class TransformerAgent:
    def __init__(self, schema: CanonicalSchema):
        self.schema = schema

    def _standardize_categorical(self, field: SchemaField, raw: str) -> Tuple[Optional[str], float, str]:
        token = (raw or "").strip().lower()
        if not token:
            return None, 0.0, f"Empty value for '{field.name}'."
        for canonical_value, tokens in (field.enum or {}).items():
            if token in [t.lower() for t in tokens]:
                return canonical_value, 0.95, f"'{raw}' -> '{canonical_value}' via enum."
        return None, 0.30, (f"'{raw}' is not a known {field.name} token; ambiguous — needs review "
                            f"(no silent inference).")

    def transform(self, headers: List[str], rows: List[Dict[str, str]],
                  mappings: List[ColumnMapping]) -> Tuple[List[Dict[str, Any]], List[CellTransform]]:
        canonical_rows: List[Dict[str, Any]] = []
        transforms: List[CellTransform] = []
        # Only mapped (non-unmatched) columns feed the output.
        active = [m for m in mappings if m.canonical_column != "UNMATCHED"]

        for row in rows:
            out: Dict[str, Any] = {}
            for m in active:
                field = self.schema.field_by_name(m.canonical_column)
                if field is None:
                    continue
                src = m.source_columns[0]
                raw = row.get(src, "")

                if m.derive_part:  # full-name split
                    first, last = _split_full_name(raw)
                    value = first if m.derive_part == "first" else last
                    conf, needs_review = (0.9, False) if value else (0.4, True)
                    out[field.name] = value
                    transforms.append(CellTransform(
                        field.name, raw, value, conf,
                        f"Split full name '{raw}' -> {m.derive_part}='{value}'.", needs_review))

                elif field.type == "categorical":
                    value, conf, why = self._standardize_categorical(field, raw)
                    out[field.name] = value
                    transforms.append(CellTransform(
                        field.name, raw, value, conf, why,
                        needs_review=(value is None)))

                elif field.type == "date":
                    value = _parse_date(raw)
                    conf, needs_review = (0.97, False) if value else (0.2, True)
                    why = (f"Parsed '{raw}' -> ISO '{value}'." if value
                           else f"Unparseable/invalid date '{raw}' — needs review.")
                    out[field.name] = value
                    transforms.append(CellTransform(field.name, raw, value, conf, why, needs_review))

                else:  # plain string passthrough (email, ssn, ...)
                    value = (raw or "").strip() or None
                    out[field.name] = value
                    if field.required and value is None:
                        transforms.append(CellTransform(
                            field.name, raw, None, 0.3,
                            f"Required field '{field.name}' empty.", needs_review=True))

            canonical_rows.append(out)
        return canonical_rows, transforms
