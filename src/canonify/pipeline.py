"""Pipeline orchestrator: mapper -> transformer -> judge -> persister.

This is the in-process ADK-style loop. The same function is what a Cloud Run Job executes in GCP
mode; only the injected backends (LLM, dictionary, sink) change.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config, load_schema
from .io_readers import read_grid
from .models import PipelineResult
from .preprocess import PreprocessReport, to_table
from .rag.dictionary import get_dictionary
from .rag.sop import SopRetriever
from .llm.gemini import GeminiClient
from .agents.mapper import MapperAgent
from .agents.transformer import TransformerAgent
from .agents.judge import JudgeAgent
from .agents.persister import PersisterAgent


def load_table(path: Path) -> Tuple[List[str], List[Dict[str, str]], PreprocessReport]:
    """Read ANY supported file (csv/tsv/xlsx/xls) and clean it into (headers, rows, report)."""
    grid = read_grid(path)
    return to_table(grid)


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

    headers, rows, preprocess_report = load_table(input_path)

    # Model Armor pre-flight: screen untrusted input for prompt-injection before any agent runs.
    security_flags = gemini.armor.scan_records(headers, rows)

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
        preprocess=preprocess_report.to_dict(),
        security_flags=security_flags,
    )
    # Security incidents also enter the human-review queue.
    review_queue.extend(security_flags)

    paths = persister.write(result) if write else {}
    return result, paths
