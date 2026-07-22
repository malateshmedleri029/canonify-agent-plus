# Canonify Agent+ — Architecture

## 1. Design principles

1. **Interface-first, backend-swappable.** Every external capability (LLM, dictionary store, data
   sink) is behind a small Python interface with a **LOCAL** and a **GCP** implementation.
2. **Deterministic core, intelligent edges.** Rule-based matching is the reproducible baseline;
   Gemini adds semantic lift; the Judge guarantees governance regardless of backend.
3. **Everything is explainable and logged.** No decision without a rationale and a confidence score.
4. **Multi-tenant by construction.** The learned dictionary is namespaced by `tenant_id`, layered
   over a shared `global` namespace.

## 2. Logical architecture (agentic loop)

```mermaid
flowchart LR
    RAW["Raw messy file<br/>(CSV/XLSX)"] --> ING[Ingestion]
    ING --> MAP

    subgraph AGENTS["ADK multi-agent pipeline"]
      MAP["Mapper Agent<br/>column → canonical<br/>match type + confidence"]
      TRN["Transformer Agent<br/>cell-level standardize"]
      JDG["Judge Agent (Gemini)<br/>confidence gate + governance"]
      PER["Persister Agent<br/>write outputs + promote"]
      MAP --> TRN --> JDG --> PER
    end

    subgraph RAG["RAG grounding"]
      SOP[("Use-case SOP")]
      DICT[("Learned Mapping Dictionary<br/>tenant + global")]
    end
    RAG -. retrieve .-> MAP
    RAG -. retrieve .-> TRN

    JDG -->|low confidence| HRQ[["Human Review Queue"]]
    HRQ -->|SME approves| DICT

    PER --> OUT1["Mapped Tabular Data"]
    PER --> OUT2["Mapping Audit Report"]
    PER --> OUT3["Judge Decision Log"]
    PER --> OUT4["Promoted Dictionary Entries"]
    PER --> DICT
```

## 3. Physical architecture on GCP

```mermaid
flowchart TB
    U[Client / Vendor upload] --> GCS[("Cloud Storage<br/>raw bucket")]
    GCS -->|Eventarc: object.finalized| RUN["Cloud Run Job<br/>canonify pipeline"]
    RUN -->|prompt| GEM["Vertex AI<br/>Gemini (mapper + judge)"]
    RUN -->|retrieve/write| FS[("Vertex AI Feature Store<br/>learned dictionary")]
    RUN -->|write canonical + logs| BQ[("BigQuery<br/>canonical + audit datasets")]
    RUN -->|review items| RVW[("BigQuery review_queue<br/>/ Firestore")]
    RUN --> ART[("Cloud Storage<br/>outputs bucket")]
    SME[SME / Analyst] -->|approve via CLI/Looker| RVW
    RVW -->|promote| FS
    OBS[Cloud Logging + Monitoring] -.-> RUN
```

## 4. Component responsibilities

| Component | LOCAL mode | GCP mode |
|---|---|---|
| **LLM** (`llm/gemini.py`) | Deterministic rule/fuzzy fallback | Vertex AI Gemini |
| **Dictionary** (`rag/dictionary.py`) | JSON file on disk | Vertex AI Feature Store |
| **SOP retrieval** (`rag/sop.py`) | Local markdown + keyword match | Vertex AI Vector Search over SOP docs |
| **Data sink** (`agents/persister.py`) | CSV + JSON files | BigQuery tables + GCS artifacts |
| **Orchestration** (`pipeline.py`) | In-process function calls | Cloud Run Job (same code) |
| **Trigger** | CLI invocation | Eventarc on GCS `object.finalized` |

## 5. Canonical data contract

The target schema is **data, not code** (`data/canonical_schema.yaml`). Adding Use Case 2 = adding a
new schema file — no engine changes. Each canonical field declares: `name`, `type`
(`string|date|categorical|number`), `required`, `sensitive`, `aliases`, and `enum` (for categoricals).

## 6. Confidence & governance model

```
score ≥ accept_threshold ............ AUTO-ACCEPT  (logged)
review_threshold ≤ score < accept ... REVIEW       (queued for SME)
score < review_threshold ............ REJECT       (queued, flagged)
sensitive field ..................... accept_threshold raised; inference always needs human confirm
```

Thresholds live in `data/canonical_schema.yaml` / `config.py`, so governance is tunable per tenant.

## 7. The four output artifacts (the contract with downstream)

1. `mapped_data.csv` — canonical tabular data.
2. `mapping_audit_report.json` — per-column: source(s), canonical, match type, confidence, rationale.
3. `judge_decision_log.json` — accept/review/reject verdicts + thresholds + reasons.
4. `promoted_dictionary_entries.json` — SME-approved mappings written back to the dictionary.

## 8. Data flow of a single file (sequence)

```mermaid
sequenceDiagram
    participant F as Raw file
    participant M as Mapper
    participant D as Dictionary (RAG)
    participant T as Transformer
    participant J as Judge
    participant P as Persister
    F->>M: headers + sample rows
    M->>D: retrieve aliases / learned mappings
    D-->>M: candidates + prior confidence
    M->>T: proposed column mappings (+match type, confidence)
    T->>T: cell transforms (name split, gender, dates)
    T->>J: mapped columns + transformed cells + scores
    J->>J: apply thresholds + sensitive-field rules
    J-->>P: accepted set + review/reject queue
    P->>P: write 4 artifacts + canonical CSV
    P->>D: promote accepted mappings (learning)
```
