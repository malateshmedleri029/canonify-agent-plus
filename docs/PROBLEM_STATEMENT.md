# Canonify Agent+ — Problem Statement (Reiterated)

> Capstone Edition — Joint SWE + DS Agentic Data-Canonicalization Platform on GCP.

## 1. The problem in one sentence

**AI agents and legacy systems need clean, predictable ("canonical") data to work reliably — but the
real-world data they receive is messy, inconsistent, and today gets normalized by hand with no audit
trail, no confidence signal, and no reusable learning.**

## 2. What "messy" actually means here

Raw tabular files arrive from clients, vendors, and internal legacy systems and routinely contain:

- **Missing columns** — expected fields simply are not present.
- **Unexpected / cryptic headers** — `FN`, `Last Nm`, `DoB`, `Sex`, `Rel`, `Gndr`.
- **Concatenated fields** — one `Full Name` column that must become `first_name` + `last_name`.
- **Inconsistent cell values** — gender as `M / F / 1 / 0 / male / f`, dates as `MM/DD/YY`,
  `YYYY-MM-DD`, `03-Jan-1990`, etc.

## 3. Why the status quo is broken

Today the normalization is:

- **Manual** — an analyst hand-maps every column, file after file.
- **Tribal** — the mapping knowledge ("`FN` means First Name") lives in one person's head.
- **Unrepeatable** — no audit trail, no confidence score, no governed learning loop.
- **Risky** — silent, unverified inferences (e.g. guessing gender from an ambiguous token) can be
  wrong with no human in the loop.

## 4. What "solved" looks like (definition of done)

A payload (messy file) goes in; the platform produces, **automatically and auditably**:

1. **Mapped Tabular Data** — the finalized dataset in the strict canonical schema.
2. **Mapping Audit Report** — per column: source column(s), canonical column, match type
   (Direct / Partial / Derived-Split / Inferred), confidence score, and a chain-of-thought
   explanation for SME review.
3. **Judge Decision Log** — accept/reject verdicts with confidence thresholds and reasons; the
   governance trail and the queue for human review.
4. **Promoted Dictionary Entries** — newly learned, SME-approved mappings persisted so accuracy
   compounds file-over-file and the marginal cost of each new file falls.

## 5. Non-negotiable properties

| Property | Requirement |
|---|---|
| **Deterministic & repeatable** | Same input → same canonical output. |
| **Auditable** | Every mapping and cell transform is explained and logged. |
| **Confidence-gated** | Low-confidence work is *blocked* and routed to a human, never silently applied. |
| **Governed learning** | Approved mappings are promoted to a versioned, tenant-namespaced store. |
| **Sensitive-field safety** | Inferences on sensitive fields (e.g. gender) require higher confidence + human confirmation. |
| **Multi-tenant** | Learning is namespaced per tenant; a shared global dictionary underlies all tenants. |

## 6. Target use cases (from the brief)

1. **Employee Benefits Administration** — process a raw roster of family members and update
   demographic information for benefits.
2. **Insurance Claims Processing** — ingest a list of damaged assets and transform into a
   standardized claims-severity schema.

## 7. Two paired workstreams (joint SWE + DS)

| Workstream | Owns |
|---|---|
| **Data Science** | Mapping intelligence (RAG + semantic matching), confidence modeling, evaluation harness. |
| **Software Engineering** | Agent orchestration (ADK), governance/judge gate, delivery (Cloud Run, BigQuery, Feature Store, IaC). |

Joined by a **shared BigQuery dataset** (canonical output + logs) and a **Vertex AI Feature Store**
(learned dictionary).
