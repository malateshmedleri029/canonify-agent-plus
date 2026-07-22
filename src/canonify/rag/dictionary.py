"""Learned mapping dictionary — the continuous-learning store.

Interface with two backends:
  * LocalJsonDictionary   — JSON file on disk (default; zero deps).
  * FeatureStoreDictionary — Vertex AI Feature Store (GCP mode; see rag/featurestore.py).

Entries are namespaced by tenant, layered over a shared "global" namespace. Each entry maps a
normalized source header -> canonical column, with a running confidence and vote count so accuracy
compounds file-over-file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Protocol


def normalize_header(h: str) -> str:
    return " ".join(h.strip().lower().replace("_", " ").replace("-", " ").split())


class LearnedDictionary(Protocol):
    def lookup(self, source_header: str, tenant_id: str) -> Optional[Dict]:
        ...

    def promote(self, source_header: str, canonical_column: str, tenant_id: str,
                confidence: float) -> Dict:
        ...

    def all_entries(self, tenant_id: str) -> List[Dict]:
        ...


class LocalJsonDictionary:
    """File-backed learned dictionary. Structure: {namespace: {norm_header: entry}}."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: Dict[str, Dict[str, Dict]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            self._data = json.loads(self.path.read_text() or "{}")
        else:
            self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))

    def lookup(self, source_header: str, tenant_id: str) -> Optional[Dict]:
        key = normalize_header(source_header)
        # Tenant namespace wins over global.
        for ns in (tenant_id, "global"):
            entry = self._data.get(ns, {}).get(key)
            if entry:
                return {**entry, "namespace": ns}
        return None

    def promote(self, source_header: str, canonical_column: str, tenant_id: str,
                confidence: float) -> Dict:
        key = normalize_header(source_header)
        ns = self._data.setdefault(tenant_id, {})
        existing = ns.get(key)
        if existing and existing["canonical_column"] == canonical_column:
            # Reinforce: increment votes, move confidence toward 1.0.
            existing["votes"] += 1
            existing["confidence"] = round(min(1.0, (existing["confidence"] + confidence) / 2 + 0.05), 4)
            entry = existing
        else:
            entry = {
                "source_header": key,
                "canonical_column": canonical_column,
                "confidence": round(confidence, 4),
                "votes": 1,
            }
            ns[key] = entry
        self._save()
        return {**entry, "namespace": tenant_id}

    def all_entries(self, tenant_id: str) -> List[Dict]:
        out: List[Dict] = []
        for ns in ("global", tenant_id):
            for entry in self._data.get(ns, {}).values():
                out.append({**entry, "namespace": ns})
        return out


def get_dictionary(config) -> LearnedDictionary:
    """Factory: pick a backend from config.mode."""
    if config.mode == "gcp":
        try:
            from .featurestore import FeatureStoreDictionary
            return FeatureStoreDictionary(config)
        except Exception as exc:  # pragma: no cover - requires GCP libs/creds
            raise RuntimeError(
                "GCP mode requested but Feature Store backend unavailable. "
                "Install extras (`pip install -e .[gcp]`) and set GOOGLE_CLOUD_PROJECT."
            ) from exc
    return LocalJsonDictionary(config.dictionary_path)
