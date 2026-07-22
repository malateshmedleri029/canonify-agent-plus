# Canonify Agent+

> Governed, multi-agent **data-canonicalization** platform on GCP.
> Messy file in → strict canonical data out, **auditable**, **confidence-gated**, and **self-learning**.

Capstone Edition — Joint SWE + DS Agentic Data-Canonicalization Platform.
Contacts: Balathasan Giritharan, Adrian Cartier.

---

## The problem (in one line)

AI agents and legacy systems need clean, predictable data — but real files arrive with missing
columns, cryptic headers (`FN`, `DoB`, `Sex`), and concatenated fields. Today an analyst hand-maps
them with **no audit trail, no confidence signal, and no reusable learning**. Canonify Agent+
automates that, with governance built in. See [`docs/PROBLEM_STATEMENT.md`](docs/PROBLEM_STATEMENT.md).

## How it works

```
raw file ─▶ Mapper ─▶ Transformer ─▶ Judge ─▶ Persister ─▶ canonical data + 4 audit artifacts
              ▲            ▲            │
              └── RAG (SOP + learned dictionary) ┘   low-confidence ─▶ Human Review ─▶ Learn
```

- **Mapper** — maps source columns → canonical columns (learned dict → alias → fuzzy → Gemini), with
  match type + confidence + chain-of-thought.
- **Transformer** — standardizes cells: `Full Name`→`first/last`, `M/F/1/0`→`Male/Female`, dates→ISO.
- **Judge** — confidence-threshold governance gate; blocks low-confidence & sensitive inferences.
- **Persister** — writes the 4 artifacts and promotes accepted mappings so accuracy compounds.

Full design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · MVP plan: [`docs/MVP_PLAN.md`](docs/MVP_PLAN.md).

## Key design decision

**The core engine is 100% Python standard library and runs offline.** GCP (Gemini, BigQuery, Vertex
AI Feature Store, Cloud Run) are pluggable power-ups behind interfaces — so you can demo and test
anywhere (laptop, CI, GitHub Copilot) with zero cloud cost, then flip `--mode gcp` to scale.

## Quickstart (no install, no cloud)

```bash
# Canonicalize the messy sample roster
PYTHONPATH=src python -m canonify run data/samples/new_to_old_bad.csv --tenant acme

# Inspect the review queue and the learned dictionary
PYTHONPATH=src python -m canonify review --tenant acme
PYTHONPATH=src python -m canonify dict   --tenant acme

# Run the tests (stdlib unittest — zero installs)
python -m unittest discover -s tests -v
```

Outputs land in `outputs/<tenant>/`:

| Artifact | What |
|---|---|
| `mapped_data.csv` | The canonical tabular data. |
| `mapping_audit_report.json` | Per column: source, match type, confidence, rationale. |
| `judge_decision_log.json` | Accept/review/reject verdicts + thresholds + reasons. |
| `promoted_dictionary_entries.json` | Newly learned mappings. |
| `review_queue.json` | Items routed to a human. |

## Install (optional)

```bash
pip install -e .            # gives you the `canonify` command
pip install -e ".[dev]"     # + pyyaml + pytest
pip install -e ".[gcp]"     # + Vertex AI / BigQuery / Storage for --mode gcp
```

## Run on GCP

One command provisions everything and deploys the event-driven pipeline:

```bash
export PROJECT_ID=your-gcp-project REGION=us-central1
./infra/scripts/gcp_bootstrap.sh
```

Then drop a file and watch it canonicalize into BigQuery. Full guide:
[`docs/GCP_SETUP.md`](docs/GCP_SETUP.md).

## Adding a new use case

The target schema is **data, not code**. To support Use Case 2 (Insurance Claims), add a new
`data/<name>_schema.json` and a matching SOP in `data/sop/` — no engine changes.

## Repo layout

```
src/canonify/      # engine: agents/, rag/, llm/, pipeline.py, cli.py, server.py
data/              # canonical_schema.{json,yaml}, sop/, samples/
tests/             # stdlib unittest suite
infra/             # Terraform + bootstrap for GCP
docs/              # problem statement, MVP plan, architecture, GCP setup
.github/           # Copilot instructions + CI
```

## For GitHub Copilot users

See [`.github/copilot-instructions.md`](.github/copilot-instructions.md) — it encodes the golden
rules (keep the core stdlib-only; never silently infer sensitive fields; every decision carries
confidence + explanation).
