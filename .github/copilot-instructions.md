# GitHub Copilot — Repository Instructions

These instructions tell Copilot (chat, code completion, and the coding agent) how to work in this
repo. Follow them for every suggestion.

## What this project is

**Canonify Agent+** — a governed, multi-agent platform that turns messy tabular files into strict
**canonical** data, with a full audit trail, confidence-gated governance, and a learning loop.
Pipeline: **Mapper → Transformer → Judge → Persister**, grounded by RAG (SOP + learned dictionary).

Read `docs/PROBLEM_STATEMENT.md`, `docs/MVP_PLAN.md`, and `docs/ARCHITECTURE.md` for full context.

## The golden rule: keep the core dependency-free

- The engine under `src/canonify/` (except `*_gcp.py`, `featurestore.py`, `server.py`, `gemini.py`
  GCP branches) MUST use only the **Python standard library**. This is what lets it run offline, in
  CI, and inside Copilot with zero setup.
- GCP features (Vertex AI Gemini, BigQuery, Feature Store, Cloud Storage) are **optional power-ups**
  behind interfaces. Import GCP libraries lazily, inside functions/methods, never at module top
  level, and always guard them so `--mode local` never needs them.

## How to run & test (no install required)

```bash
# Run the pipeline locally (stdlib only)
PYTHONPATH=src python -m canonify run data/samples/new_to_old_bad.csv --tenant acme

# Run the full test suite (stdlib unittest, zero installs)
python -m unittest discover -s tests

# Or, if extras are installed: pytest
pip install -e ".[dev]" && pytest
```

Always keep `python -m unittest discover -s tests` green before finishing a change.

## Architecture map (where things live)

| Path | Responsibility |
|---|---|
| `src/canonify/models.py` | Dataclass contracts (ColumnMapping, CellTransform, JudgeDecision, PipelineResult). |
| `src/canonify/config.py` | Config + canonical-schema loading (JSON default; YAML if PyYAML present). |
| `src/canonify/io_readers.py` | Robust CSV + pure-stdlib `.xlsx` readers → raw grid. |
| `src/canonify/preprocess.py` | Worst-of-worst cleanup + real-header detection → (headers, rows, report). |
| `src/canonify/llm/model_armor.py` | GCP Model Armor screening (+ local injection/PII heuristic). |
| `src/canonify/webapp.py` + `web/index.html` | Stdlib web UI + JSON API (upload CSV/Excel). |
| `src/canonify/agents/mapper.py` | Column → canonical mapping (dict/alias/fuzzy/Gemini). |
| `src/canonify/agents/transformer.py` | Cell transforms (name split, gender, dates). |
| `src/canonify/agents/judge.py` | Confidence-threshold governance gate. |
| `src/canonify/agents/persister.py` | Writes 4 artifacts + promotes learned mappings. |
| `src/canonify/rag/` | Learned dictionary + SOP retrieval. |
| `src/canonify/llm/gemini.py` | Vertex AI wrapper; `enabled=False` in local mode → callers fall back. |
| `src/canonify/pipeline.py` | Orchestrates the loop. |
| `data/canonical_schema.{json,yaml}` | The target schema — DATA, not code. |
| `infra/` | Terraform + bootstrap for GCP. |

## Conventions

- Python 3.9-compatible. Use `from __future__ import annotations`.
- Prefer pure functions and small dataclasses; keep agents stateless where possible.
- Every mapping/transform must carry a **confidence score** and a human-readable **explanation**.
- **Never silently infer sensitive fields** (gender, DoB, SSN). Below threshold → route to review.
- Adding a new use case = add a new `data/*_schema.json`; do NOT hardcode field logic in agents.
- When adding a capability, add both a LOCAL implementation and (if relevant) the GCP branch, behind
  the existing factory/interface.

## What to optimize for

Auditability, reproducibility, and governance over cleverness. A correct, explained, gated result
beats an unexplained "smart" one.
