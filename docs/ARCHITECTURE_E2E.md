# Canonify Agent+ — Complete End-to-End Architecture

This is the full picture: from a user dropping the worst file imaginable, through robust ingestion,
the Model-Armor-protected agentic loop, to governed canonical data + a compounding learning loop.
All diagrams are Mermaid (render in VS Code with the *Markdown Preview Mermaid* extension, or on GitHub).

---

## 1. System context (who/what touches the system)

```mermaid
flowchart TB
    subgraph Users
      AN["Analyst / SME"]
      UP["Client / Vendor / Legacy export"]
    end

    subgraph Canonify["Canonify Agent+"]
      UI["Web UI (upload + review)"]
      ENG["Agentic engine<br/>Mapper→Transformer→Judge→Persister"]
      LEARN[("Learned dictionary")]
    end

    subgraph GCP["Google Cloud (mode=gcp)"]
      GEM["Vertex AI Gemini"]
      ARM["Model Armor"]
      BQ[("BigQuery")]
      FS[("Vertex AI Feature Store")]
    end

    UP -->|messy CSV/XLSX| UI
    AN -->|upload, review, approve| UI
    UI --> ENG
    ENG <-->|semantic assist| GEM
    ENG <-->|screen prompts/responses/input| ARM
    ENG -->|canonical + audit| BQ
    ENG <-->|promote / retrieve| FS
    LEARN -. local mode .- ENG
```

---

## 2. The complete request flow (worst-file → canonical)

```mermaid
flowchart TD
    A["Raw file<br/>CSV / TSV / XLSX / XLS"] --> B{io_readers}
    B -->|encoding + delimiter sniff| C1[CSV/TSV grid]
    B -->|zip + XML, serial-date decode| C2[XLSX grid]
    B -->|xlrd/pandas optional| C3[XLS grid]

    C1 & C2 & C3 --> D["preprocess.to_table<br/>• detect real header row (skips junk/titles)<br/>• drop empty rows/cols<br/>• null-token cleanup (N/A,#REF!,-)<br/>• dedupe/rename headers<br/>• strip trailing totals"]

    D --> SEC["🛡️ Model Armor pre-flight<br/>scan headers+cells for prompt-injection"]
    SEC -->|flags| RQ[["Human Review Queue"]]

    D --> M["Mapper Agent<br/>learned-dict → alias → fuzzy → Gemini"]
    RAGD[("Learned dictionary (RAG)")] -. retrieve .-> M
    SOP[("SOP (RAG)")] -. retrieve .-> M
    M -->|ambiguous only| GEM2["Gemini (Model-Armor-gated)"]

    M --> T["Transformer Agent<br/>name split · gender enum · date→ISO · Excel serials"]
    T --> J["Judge Agent<br/>confidence gate + sensitive-field rules"]
    J -->|accept| P["Persister Agent"]
    J -->|review/reject| RQ

    P --> O1["Mapped canonical data (CSV / BigQuery)"]
    P --> O2["Mapping Audit Report"]
    P --> O3["Judge Decision Log"]
    P --> O4["Preprocess + Security reports"]
    P -->|promote accepted| RAGD
    RQ -->|SME approves| RAGD
```

---

## 3. "Worst-of-worst" data-robustness stages

What each stage defends against (all in `io_readers.py` + `preprocess.py`):

```mermaid
flowchart LR
    R1["Wrong encoding / BOM"] --> S1[utf-8-sig→cp1252→latin-1 fallback]
    R2["Odd delimiter ; tab |"] --> S2[csv.Sniffer]
    R3["Title/logo rows on top"] --> S3[header-row scoring]
    R4["Blank rows & columns"] --> S4[drop empties]
    R5["Merged/sparse cells"] --> S5[pad to header width]
    R6["N/A · null · #REF! · -"] --> S6[null-token normalization]
    R7["Dup / blank headers"] --> S7[rename + dedupe]
    R8["Excel serial dates 44197"] --> S8[styles.xml date decode + serial parse]
    R9["Totals / footnotes at bottom"] --> S9[trailing-junk removal]
    R10["Full Name / Emp Full Name"] --> S10[semantic full-name split]
```

---

## 4. Security: Model Armor placement (defense in depth)

Untrusted file content reaches an LLM — so it is screened at **three** points.

```mermaid
sequenceDiagram
    participant F as Raw file (untrusted)
    participant PRE as Pre-flight scan
    participant MAP as Mapper/Transformer
    participant ARM as Model Armor
    participant GEM as Gemini
    F->>PRE: headers + cell values
    PRE->>ARM: scan_records() (injection/PII)
    ARM-->>PRE: flags → Review Queue
    MAP->>ARM: screen_prompt(prompt w/ untrusted data)
    ARM-->>MAP: blocked? → fall back to deterministic engine
    MAP->>GEM: (only if clean) generate mapping
    GEM-->>ARM: screen_response(model output)
    ARM-->>MAP: blocked? → discard, fall back
```

---

## 5. Deployment (mode=gcp)

```mermaid
flowchart TB
    DEV["Developer / VS Code"] -->|gcloud builds submit| AR[("Artifact Registry")]
    AR --> RUN

    U["Upload"] --> GCS[("Cloud Storage raw")]
    GCS -->|Eventarc object.finalized| RUN["Cloud Run service<br/>canonify.server"]
    RUN --> GEM["Vertex AI Gemini"]
    RUN --> ARM["Model Armor template"]
    RUN --> BQ[("BigQuery: canonical + audit + dictionary")]
    RUN --> OUT[("Cloud Storage outputs")]
    SME["SME"] --> BQ
    LOG["Cloud Logging / Monitoring"] -.-> RUN

    subgraph IAM["Least privilege"]
      SA["runner SA: aiplatform.user, bigquery.dataEditor, storage.objectAdmin(scoped)"]
    end
    SA -.-> RUN
```

---

## 6. Local vs GCP — same code, swapped backends

| Concern | LOCAL (default) | GCP (`--mode gcp`) |
|---|---|---|
| File UI | `python -m canonify.webapp` (stdlib) | Same UI, or Eventarc-triggered `canonify.server` |
| Column intelligence | dict + alias + fuzzy | + Vertex AI Gemini |
| Security screening | regex heuristic (`model_armor.py`) | **GCP Model Armor** template |
| Learned dictionary | JSON on disk | BigQuery / Vertex AI Feature Store |
| Canonical + audit sink | CSV + JSON files | BigQuery tables + GCS |
| Trigger | CLI / web upload | Eventarc on GCS `object.finalized` |

The engine module boundary guarantees the local path never imports a cloud library.
