# Canonify Agent+ — MVP Plan

This plan is written from a **ruthless MVP point of view**: ship the smallest thing that proves the
core loop — *messy file in → governed, auditable canonical data out, with a learning loop that
compounds* — then layer GCP power onto it.

## 0. The one guiding design decision

> **The core canonicalization engine is 100% standard-library Python and runs offline.
> GCP (Gemini, Vertex AI Feature Store, BigQuery, Cloud Run) are pluggable "power-ups", not hard
> dependencies.**

Why this is the smart MVP move:

- **Demo & test anywhere** — runs on a laptop, in CI, and inside **GitHub Copilot** with zero cloud
  cost or credentials.
- **Deterministic baseline** — a stdlib fuzzy matcher (`difflib`) + alias dictionary gives a
  reproducible, explainable result. Gemini is an *accuracy amplifier* layered on top, not a
  single point of failure.
- **Same interfaces, two backends** — `LOCAL` mode uses JSON files + rule-based matching;
  `GCP` mode swaps in Gemini, Feature Store, and BigQuery behind identical Python interfaces.

## 1. MVP scope — what's IN

| # | Capability | MVP behavior |
|---|---|---|
| 1 | **Ingest** a messy CSV | Read headers + rows from a raw file. |
| 2 | **Map** columns → canonical schema | Alias dict + learned dict + fuzzy match (+ Gemini in GCP mode). Emits match type & confidence. |
| 3 | **Transform** cells | Split full name, standardize gender, parse dates → ISO. Each with confidence. |
| 4 | **Judge** gate | Confidence thresholds; accept / review / reject; stricter gate for sensitive fields. |
| 5 | **Persist** outputs | Canonical CSV + 4 audit artifacts (JSON). LOCAL=files, GCP=BigQuery + Feature Store. |
| 6 | **Learn** | Approved mappings promoted to the dictionary so the next file scores higher. |
| 7 | **Explain** | Every decision carries a chain-of-thought rationale. |

## 2. MVP scope — what's OUT (deliberately deferred)

- Human-review **UI** (MVP: review queue is a JSON/BigQuery table; approval is a CLI command).
- Real-time streaming ingestion (MVP: batch, file-triggered).
- Full IAM/VPC hardening (MVP: least-privilege service account + docs).
- The second use case's bespoke schema logic (MVP: schema-driven, so Use Case 2 = new YAML schema).

## 3. The agentic loop (MVP)

```
raw file ─▶ Mapper ─▶ Transformer ─▶ Judge ─▶ Persister
              ▲           ▲            │
              └──── RAG grounding ─────┘   (SOP + learned dictionary)
                                          │
                    low-confidence ──────▶ Human Review Queue ──▶ (approve) ──▶ Learn
```

- **Mapper agent** — proposes `source column → canonical column` with match type + confidence,
  grounded by RAG over the SOP and the learned dictionary.
- **Transformer agent** — applies cell-level transforms to hit target types/formats.
- **Judge agent** — the governance gate; blocks low-confidence and sensitive inferences.
- **Persister agent** — writes canonical data + the 4 audit artifacts and promotes learned mappings.

## 4. Milestones (build order)

| Milestone | Deliverable | Done when |
|---|---|---|
| **M0 — Skeleton** | Repo, config, data models, canonical schema, sample data | `python -m canonify --help` works |
| **M1 — Local pipeline** | Mapper→Transformer→Judge→Persister end-to-end in LOCAL mode | Sample messy CSV → canonical CSV + 4 artifacts |
| **M2 — Tests** | Unit + integration tests (stdlib `unittest`) | `python -m unittest` green, zero installs |
| **M3 — Learning loop** | Promote approved mappings; re-run scores higher | 2nd run confidence ↑, fewer review items |
| **M4 — GCP power-ups** | Gemini mapper/judge, Feature Store dict, BigQuery sink | Same CLI, `--mode gcp` writes to BigQuery |
| **M5 — Infra + deploy** | Terraform + Cloud Run job + Eventarc trigger | `terraform apply` + upload file → run fires |

## 5. Success metrics (MVP evaluation)

- **Auto-map rate** — % of columns mapped without human review (target ≥ 80% on sample).
- **Mapping accuracy** — % correct vs. a labeled gold set (target ≥ 95% on accepted mappings).
- **Zero silent sensitive inferences** — 100% of sensitive-field inferences below threshold go to review.
- **Learning gain** — measurable confidence increase on a re-run after promotion.
- **Full auditability** — every accepted column has a source, match type, confidence, and rationale.

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinated mapping | Judge gate + confidence threshold + deterministic fallback + audit trail. |
| Sensitive mis-inference (e.g. gender) | Higher threshold + mandatory human confirmation. |
| Cloud cost / lock-in | Offline stdlib core; GCP is optional and behind interfaces. |
| Non-reproducible results | Deterministic baseline; LLM temperature pinned low; decisions logged. |

## 7. Team split (maps to the brief's two workstreams)

- **DS**: `mapper` scoring, RAG retrieval, evaluation harness (`tests/` + metrics).
- **SWE**: `judge`/`persister` governance, orchestration (`pipeline.py`, ADK), `infra/` (Terraform, Cloud Run).
