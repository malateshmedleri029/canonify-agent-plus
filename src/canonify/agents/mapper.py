"""Mapper agent: propose source-column -> canonical-column mappings.

Resolution order (highest trust first), each producing a confidence + explanation:
  1. Learned dictionary hit (RAG)         -> Direct, compounding confidence.
  2. Exact canonical name / alias match   -> Direct.
  3. Full-name column                      -> Derived/Split into first_name + last_name.
  4. Fuzzy string similarity (difflib)     -> Partial (close) / Inferred (weaker).
  5. Gemini semantic match (GCP only)      -> Inferred, on ambiguous headers.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from ..config import CanonicalSchema, Config
from ..models import ColumnMapping, MatchType
from ..rag.dictionary import LearnedDictionary, normalize_header
from ..rag.sop import SopRetriever
from ..llm.gemini import GeminiClient


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


class MapperAgent:
    def __init__(self, schema: CanonicalSchema, dictionary: LearnedDictionary,
                 sop: SopRetriever, gemini: GeminiClient, config: Config):
        self.schema = schema
        self.dictionary = dictionary
        self.sop = sop
        self.gemini = gemini
        self.config = config

    # -- alias index ---------------------------------------------------------------------------
    def _alias_index(self) -> Dict[str, str]:
        """normalized alias/name -> canonical column."""
        idx: Dict[str, str] = {}
        for f in self.schema.fields:
            idx[normalize_header(f.name)] = f.name
            for a in f.aliases:
                idx[normalize_header(a)] = f.name
        return idx

    def _is_full_name(self, norm_header: str, full_name_norms: set) -> bool:
        """Robustly recognize a full-name column even with prefixes (e.g. 'Emp Full Name')."""
        if norm_header in full_name_norms:
            return True
        tokens = set(norm_header.split())
        excluders = {"first", "last", "fname", "lname", "given", "sur", "surname",
                     "user", "file", "company", "nick", "middle", "maiden"}
        return "name" in tokens and not (tokens & excluders)

    def _best_fuzzy(self, norm_header: str) -> Tuple[Optional[str], float]:
        best_col, best_score = None, 0.0
        for f in self.schema.fields:
            for cand in [f.name, *f.aliases]:
                score = _similarity(norm_header, normalize_header(cand))
                if score > best_score:
                    best_col, best_score = f.name, score
        return best_col, best_score

    def map_columns(self, headers: List[str]) -> List[ColumnMapping]:
        mappings: List[ColumnMapping] = []
        alias_idx = self._alias_index()
        full_name_norms = {normalize_header(a) for a in self.schema.full_name_aliases}

        for header in headers:
            norm = normalize_header(header)
            field = None

            # 3. Full-name column -> derived split into first/last.
            if self._is_full_name(norm, full_name_norms):
                for part, col in (("first", "first_name"), ("last", "last_name")):
                    f = self.schema.field_by_name(col)
                    mappings.append(ColumnMapping(
                        canonical_column=col,
                        source_columns=[header],
                        match_type=MatchType.DERIVED,
                        confidence=0.95,
                        explanation=f"'{header}' recognized as a full-name column (SOP); "
                                    f"split to derive {col}.",
                        sensitive=bool(f and f.sensitive),
                        derive_part=part,
                    ))
                continue

            # 1. Learned dictionary (RAG) hit.
            hit = self.dictionary.lookup(header, self.config.tenant_id)
            if hit:
                field = self.schema.field_by_name(hit["canonical_column"])
                mappings.append(ColumnMapping(
                    canonical_column=hit["canonical_column"],
                    source_columns=[header],
                    match_type=MatchType.DIRECT,
                    confidence=float(hit["confidence"]),
                    explanation=f"Learned dictionary ({hit['namespace']}): '{header}' -> "
                                f"{hit['canonical_column']} (votes={hit.get('votes', 1)}).",
                    sensitive=bool(field and field.sensitive),
                ))
                continue

            # 2. Exact canonical/alias match.
            if norm in alias_idx:
                col = alias_idx[norm]
                field = self.schema.field_by_name(col)
                mappings.append(ColumnMapping(
                    canonical_column=col,
                    source_columns=[header],
                    match_type=MatchType.DIRECT,
                    confidence=0.97,
                    explanation=f"'{header}' is a known alias of canonical '{col}'.",
                    sensitive=bool(field and field.sensitive),
                ))
                continue

            # 4. Fuzzy similarity.
            col, score = self._best_fuzzy(norm)
            field = self.schema.field_by_name(col) if col else None
            match_type = MatchType.PARTIAL if score >= 0.85 else MatchType.INFERRED
            explanation = f"Fuzzy match '{header}' ~ canonical '{col}' (similarity={score:.2f})."

            # 5. Gemini semantic assist on ambiguous headers (GCP mode only).
            if score < self.schema.thresholds["accept"] and self.gemini.enabled:
                sop_ctx = self.sop.retrieve(header)
                candidates = [f.name for f in self.schema.fields]
                proposal = self.gemini.propose_mapping(header, candidates, sop_ctx)
                if proposal and proposal.get("canonical_column"):
                    col = proposal["canonical_column"]
                    field = self.schema.field_by_name(col)
                    score = float(proposal.get("confidence", score))
                    match_type = MatchType.INFERRED
                    explanation = "Gemini semantic match: " + proposal.get("explanation", "")

            mappings.append(ColumnMapping(
                canonical_column=col or "UNMATCHED",
                source_columns=[header],
                match_type=match_type if col else MatchType.UNMATCHED,
                confidence=round(score, 4),
                explanation=explanation,
                sensitive=bool(field and field.sensitive),
            ))

        return mappings
