"""Pipeline orchestrator: mapper -> transformer -> judge -> persister.

This is the in-process ADK-style loop. The same function is what a Cloud Run Job executes in GCP
mode; only the injected backends (LLM, dictionary, sink) change.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config, load_schema
from .models import PipelineResult
from .rag.dictionary import get_dictionary
from .rag.sop import SopRetriever
from .llm.gemini import GeminiClient
from .agents.mapper import MapperAgent
from .agents.transformer import TransformerAgent
from .agents.judge import JudgeAgent
from .agents.persister import PersisterAgent


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with Path(path).open(newline="") as fh:
        reader = csv.DictReader(fh)
        headers = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return headers, rows


def run_pipeline(input_path: Path, config: Optional[Config] = None,
                 schema_path: Optional[Path] = None, write: bool = True) -> Tuple[PipelineResult, Dict[str, str]]:
    config = config or Config.from_env()
    schema = load_schema(schema_path or config.schema_path)

    dictionary = get_dictionary(config)
    sop = SopRetriever(config.sop_dir, schema.schema_name)
    gemini = GeminiClient(config)

    mapper = MapperAgent(schema, dictionary, sop, gemini, config)
    transformer = TransformerAgent(schema)
    judge = JudgeAgent(schema)
    persister = PersisterAgent(config, dictionary)

    headers, rows = read_csv(input_path)

    mappings = mapper.map_columns(headers)
    canonical_rows, transforms = transformer.transform(headers, rows, mappings)
    decisions, review_queue = judge.judge(mappings, transforms)
    promoted = persister.promote(mappings, decisions)

    result = PipelineResult(
        tenant_id=config.tenant_id,
        schema_name=schema.schema_name,
        mappings=mappings,
        transforms=transforms,
        decisions=decisions,
        canonical_rows=canonical_rows,
        promoted_entries=promoted,
        review_queue=review_queue,
    )

    paths = persister.write(result) if write else {}
    return result, paths
