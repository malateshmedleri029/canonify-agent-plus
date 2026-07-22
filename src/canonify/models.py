"""Core data models (stdlib dataclasses — no third-party deps).

These are the contracts shared by every agent. Keeping them as plain dataclasses means the core
runs anywhere and serializes cleanly to the four required output artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class MatchType(str, Enum):
    """How a source column was matched to a canonical column."""
    DIRECT = "Direct Match"
    PARTIAL = "Partial Match"
    DERIVED = "Derived/Split"
    INFERRED = "Inferred"
    UNMATCHED = "Unmatched"


class Verdict(str, Enum):
    """Judge gate outcome."""
    ACCEPT = "ACCEPT"
    REVIEW = "REVIEW"
    REJECT = "REJECT"


@dataclass
class ColumnMapping:
    """A proposed mapping from source column(s) to a canonical column."""
    canonical_column: str
    source_columns: List[str]
    match_type: MatchType
    confidence: float
    explanation: str
    sensitive: bool = False
    derive_part: Optional[str] = None  # "first" | "last" for split mappings

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["match_type"] = self.match_type.value
        return d


@dataclass
class CellTransform:
    """Record of a single cell-value transformation."""
    canonical_column: str
    raw_value: str
    transformed_value: Optional[str]
    confidence: float
    explanation: str
    needs_review: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JudgeDecision:
    """A verdict emitted by the Judge for a mapping or a transform."""
    target: str            # canonical column name
    kind: str              # "mapping" | "transform"
    verdict: Verdict
    confidence: float
    threshold_used: float
    reason: str
    sensitive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        return d


@dataclass
class PipelineResult:
    """Everything produced by one run — the four artifacts + the canonical rows."""
    tenant_id: str
    schema_name: str
    mappings: List[ColumnMapping] = field(default_factory=list)
    transforms: List[CellTransform] = field(default_factory=list)
    decisions: List[JudgeDecision] = field(default_factory=list)
    canonical_rows: List[Dict[str, Any]] = field(default_factory=list)
    promoted_entries: List[Dict[str, Any]] = field(default_factory=list)
    review_queue: List[Dict[str, Any]] = field(default_factory=list)
    preprocess: Dict[str, Any] = field(default_factory=dict)
    security_flags: List[Dict[str, Any]] = field(default_factory=list)

    # --- the four required output artifacts ------------------------------------------------
    def mapping_audit_report(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self.mappings]

    def judge_decision_log(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.decisions]

    def promoted_dictionary_entries(self) -> List[Dict[str, Any]]:
        return self.promoted_entries

    def summary(self) -> Dict[str, Any]:
        accepted = sum(1 for d in self.decisions if d.verdict == Verdict.ACCEPT)
        review = sum(1 for d in self.decisions if d.verdict == Verdict.REVIEW)
        reject = sum(1 for d in self.decisions if d.verdict == Verdict.REJECT)
        return {
            "tenant_id": self.tenant_id,
            "schema_name": self.schema_name,
            "rows": len(self.canonical_rows),
            "columns_mapped": len(self.mappings),
            "decisions": {"accept": accepted, "review": review, "reject": reject},
            "review_queue_size": len(self.review_queue),
            "promoted": len(self.promoted_entries),
            "security_flags": len(self.security_flags),
            "preprocess": self.preprocess,
        }
