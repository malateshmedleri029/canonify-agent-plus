"""Persister agent: write the four output artifacts + canonical data, and promote learning.

LOCAL mode  -> writes CSV + JSON files under config.output_dir.
GCP mode    -> writes BigQuery tables + GCS artifacts (see agents/persister_gcp.py); promotion goes
               to the Vertex AI Feature Store dictionary.

Promotion policy: only mappings the Judge ACCEPTED are written back to the learned dictionary, so
accuracy compounds without letting low-confidence guesses pollute the store.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

from ..config import Config
from ..models import ColumnMapping, JudgeDecision, PipelineResult, Verdict
from ..rag.dictionary import LearnedDictionary


class PersisterAgent:
    def __init__(self, config: Config, dictionary: LearnedDictionary):
        self.config = config
        self.dictionary = dictionary

    def _accepted_mapping_columns(self, decisions: List[JudgeDecision]) -> set:
        return {d.target for d in decisions
                if d.kind == "mapping" and d.verdict == Verdict.ACCEPT}

    def promote(self, mappings: List[ColumnMapping],
                decisions: List[JudgeDecision]) -> List[Dict]:
        """Write SME-accepted mappings back to the learned dictionary."""
        accepted = self._accepted_mapping_columns(decisions)
        promoted: List[Dict] = []
        for m in mappings:
            if m.canonical_column in accepted and m.match_type.value != "Derived/Split":
                for src in m.source_columns:
                    entry = self.dictionary.promote(
                        src, m.canonical_column, self.config.tenant_id, m.confidence)
                    promoted.append(entry)
        return promoted

    def write(self, result: PipelineResult) -> Dict[str, str]:
        if self.config.mode == "gcp":
            try:
                from .persister_gcp import write_to_gcp
                return write_to_gcp(result, self.config)
            except Exception as exc:  # pragma: no cover - requires GCP libs/creds
                raise RuntimeError(
                    "GCP mode requested but BigQuery sink unavailable. Install extras and set "
                    "GOOGLE_CLOUD_PROJECT."
                ) from exc
        return self._write_local(result)

    def _write_local(self, result: PipelineResult) -> Dict[str, str]:
        out = Path(self.config.output_dir) / result.tenant_id
        out.mkdir(parents=True, exist_ok=True)

        # 1. Mapped tabular data (canonical CSV).
        data_path = out / "mapped_data.csv"
        columns = [m.canonical_column for m in result.mappings
                   if m.canonical_column != "UNMATCHED"]
        # de-dupe preserving order
        seen, ordered = set(), []
        for c in columns:
            if c not in seen:
                seen.add(c); ordered.append(c)
        with data_path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=ordered)
            writer.writeheader()
            for row in result.canonical_rows:
                writer.writerow({c: row.get(c, "") for c in ordered})

        # 2-4. Audit artifacts.
        artifacts = {
            "mapping_audit_report.json": result.mapping_audit_report(),
            "judge_decision_log.json": result.judge_decision_log(),
            "promoted_dictionary_entries.json": result.promoted_dictionary_entries(),
            "review_queue.json": result.review_queue,
            "run_summary.json": result.summary(),
        }
        paths = {"mapped_data.csv": str(data_path)}
        for name, payload in artifacts.items():
            p = out / name
            p.write_text(json.dumps(payload, indent=2))
            paths[name] = str(p)
        return paths
