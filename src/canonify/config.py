"""Runtime configuration + canonical-schema loading (stdlib only).

Mode selection:
  LOCAL  -> deterministic fuzzy matching, JSON dictionary on disk, CSV/JSON outputs (no cloud).
  GCP    -> Vertex AI Gemini, Feature Store dictionary, BigQuery sink (requires extras + creds).

Config is resolved from (in order): explicit args -> environment variables -> defaults.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Repo root = two levels up from this file (src/canonify/config.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


@dataclass
class SchemaField:
    name: str
    type: str
    required: bool = False
    sensitive: bool = False
    aliases: List[str] = field(default_factory=list)
    enum: Optional[Dict[str, List[str]]] = None
    derive_from: Optional[str] = None
    derive_part: Optional[str] = None


@dataclass
class CanonicalSchema:
    schema_name: str
    version: int
    thresholds: Dict[str, float]
    fields: List[SchemaField]
    full_name_aliases: List[str] = field(default_factory=list)

    def field_by_name(self, name: str) -> Optional[SchemaField]:
        for f in self.fields:
            if f.name == name:
                return f
        return None


@dataclass
class Config:
    mode: str = "local"                       # "local" | "gcp"
    tenant_id: str = "global"
    schema_path: Optional[Path] = None
    output_dir: Path = REPO_ROOT / "outputs"
    dictionary_path: Path = DATA_DIR / "dictionary" / "learned.json"
    sop_dir: Path = DATA_DIR / "sop"
    # GCP settings (only used in gcp mode)
    gcp_project: Optional[str] = None
    gcp_location: str = "us-central1"
    gemini_model: str = "gemini-2.0-flash"
    bq_dataset: str = "canonify"
    featurestore_id: str = "canonify_dictionary"
    # GCP Model Armor template resource name, e.g.
    # projects/<p>/locations/<l>/templates/canonify-armor
    model_armor_template: Optional[str] = None

    @classmethod
    def from_env(cls, **overrides: Any) -> "Config":
        cfg = cls(
            mode=os.getenv("CANONIFY_MODE", "local"),
            tenant_id=os.getenv("CANONIFY_TENANT", "global"),
            gcp_project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            gcp_location=os.getenv("CANONIFY_LOCATION", "us-central1"),
            gemini_model=os.getenv("CANONIFY_GEMINI_MODEL", "gemini-2.0-flash"),
            model_armor_template=os.getenv("CANONIFY_MODEL_ARMOR_TEMPLATE"),
        )
        for k, v in overrides.items():
            if v is not None:
                setattr(cfg, k, v)
        return cfg


def load_schema(path: Optional[Path] = None) -> CanonicalSchema:
    """Load the canonical schema.

    Prefers a .yaml file when PyYAML is installed (nicer to author); otherwise falls back to the
    .json copy so the core stays dependency-free.
    """
    if path is None:
        path = DATA_DIR / "canonical_schema.json"
    path = Path(path)

    raw: Dict[str, Any]
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
            raw = yaml.safe_load(path.read_text())
        except ImportError:
            json_path = path.with_suffix(".json")
            raw = json.loads(json_path.read_text())
    else:
        raw = json.loads(path.read_text())

    fields = [SchemaField(**f) for f in raw["fields"]]
    return CanonicalSchema(
        schema_name=raw["schema_name"],
        version=raw.get("version", 1),
        thresholds=raw["thresholds"],
        fields=fields,
        full_name_aliases=raw.get("full_name_aliases", []),
    )
