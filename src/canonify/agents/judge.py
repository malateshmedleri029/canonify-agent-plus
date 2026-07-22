"""Judge agent: the governance gate.

Applies confidence thresholds to every mapping and to each column's transforms:
    score >= accept(+sensitive_bonus)  -> ACCEPT
    score >= review                    -> REVIEW  (queued for a human)
    score <  review                    -> REJECT  (queued, flagged)

Sensitive fields (DoB, gender, SSN) get a raised bar and any ambiguous inference is forced to a
human — the platform never silently guesses a sensitive value.
"""
from __future__ import annotations

from typing import Dict, List

from ..config import CanonicalSchema
from ..models import CellTransform, ColumnMapping, JudgeDecision, Verdict


class JudgeAgent:
    def __init__(self, schema: CanonicalSchema):
        self.schema = schema
        self.accept = schema.thresholds["accept"]
        self.review = schema.thresholds["review"]
        self.sensitive_bonus = schema.thresholds.get("sensitive_bonus", 0.0)

    def _threshold_for(self, sensitive: bool) -> float:
        return min(1.0, self.accept + self.sensitive_bonus) if sensitive else self.accept

    def _verdict(self, confidence: float, sensitive: bool) -> tuple:
        threshold = self._threshold_for(sensitive)
        if confidence >= threshold:
            return Verdict.ACCEPT, threshold
        if confidence >= self.review:
            return Verdict.REVIEW, threshold
        return Verdict.REJECT, threshold

    def judge(self, mappings: List[ColumnMapping],
              transforms: List[CellTransform]) -> tuple:
        decisions: List[JudgeDecision] = []
        review_queue: List[Dict] = []

        # --- mapping verdicts ---------------------------------------------------------------
        for m in mappings:
            if m.canonical_column == "UNMATCHED":
                decisions.append(JudgeDecision(
                    target="/".join(m.source_columns), kind="mapping", verdict=Verdict.REJECT,
                    confidence=m.confidence, threshold_used=self.review,
                    reason="No canonical column matched.", sensitive=False))
                review_queue.append({"type": "mapping", "source": m.source_columns,
                                     "issue": "unmatched column", "confidence": m.confidence})
                continue
            verdict, threshold = self._verdict(m.confidence, m.sensitive)
            decisions.append(JudgeDecision(
                target=m.canonical_column, kind="mapping", verdict=verdict,
                confidence=m.confidence, threshold_used=threshold,
                reason=m.explanation, sensitive=m.sensitive))
            if verdict != Verdict.ACCEPT:
                review_queue.append({"type": "mapping", "canonical": m.canonical_column,
                                     "source": m.source_columns, "confidence": m.confidence,
                                     "verdict": verdict.value, "sensitive": m.sensitive})

        # --- transform verdicts (aggregated per canonical column) ---------------------------
        by_col: Dict[str, List[CellTransform]] = {}
        for t in transforms:
            by_col.setdefault(t.canonical_column, []).append(t)

        for col, items in by_col.items():
            field = self.schema.field_by_name(col)
            sensitive = bool(field and field.sensitive)
            min_conf = min(t.confidence for t in items)
            flagged = [t for t in items if t.needs_review]
            verdict, threshold = self._verdict(min_conf, sensitive)
            if flagged and verdict == Verdict.ACCEPT:
                verdict = Verdict.REVIEW  # any flagged cell blocks silent acceptance
            decisions.append(JudgeDecision(
                target=col, kind="transform", verdict=verdict, confidence=round(min_conf, 4),
                threshold_used=threshold,
                reason=f"{len(items)} cells; {len(flagged)} need review; min_conf={min_conf:.2f}.",
                sensitive=sensitive))
            for t in flagged:
                review_queue.append({"type": "transform", "canonical": col,
                                     "raw_value": t.raw_value, "confidence": t.confidence,
                                     "reason": t.explanation, "sensitive": sensitive})

        return decisions, review_queue
