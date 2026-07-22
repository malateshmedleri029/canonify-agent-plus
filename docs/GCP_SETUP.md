# GCP Setup & Execution Guide

This guide takes Canonify Agent+ from a laptop demo to a running, event-driven pipeline on GCP.
It maps 1:1 to the physical architecture in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## What gets created

| Resource | Purpose |
|---|---|
| Cloud Storage `…-canonify-raw` | Drop raw messy files here (triggers a run). |
| Cloud Storage `…-canonify-outputs` | Canonical artifacts land here. |
| BigQuery dataset `canonify` | Canonical data, audit logs, `learned_dictionary`. |
| Cloud Run service `canonify-pipeline` | Runs the agentic pipeline (image you build). |
| Eventarc trigger `canonify-on-upload` | `object.finalized` on raw bucket → Cloud Run. |
| Vertex AI (Gemini) | Mapper semantic assist + Judge review of edge cases. |
| Service accounts + least-privilege IAM | Runner + Eventarc identities. |

## Prerequisites

- `gcloud`, `terraform` (>= 1.5), and Docker/Cloud Build access.
- A GCP project with billing enabled, and `roles/owner` (or equivalent) to bootstrap.
- Authenticated: `gcloud auth login && gcloud auth application-default login`.

## Option A — one command (recommended)

```bash
export PROJECT_ID=your-gcp-project
export REGION=us-central1
./infra/scripts/gcp_bootstrap.sh
```

This enables APIs, creates an Artifact Registry repo, builds & pushes the container, then runs
`terraform apply`.

## Option B — step by step

```bash
# 1. Enable APIs
gcloud services enable run.googleapis.com eventarc.googleapis.com aiplatform.googleapis.com \
  bigquery.googleapis.com storage.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com pubsub.googleapis.com

# 2. Artifact Registry + build image
gcloud artifacts repositories create canonify --repository-format=docker --location=$REGION
IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/canonify/app:latest
gcloud builds submit --tag $IMAGE .

# 3. Provision infra
cd infra/terraform
terraform init
terraform apply -var="project_id=$PROJECT_ID" -var="region=$REGION" -var="image=$IMAGE"
```

## Run it

Upload a file — tenant is the first path segment (`gs://<raw>/<tenant>/<file>.csv`):

```bash
RAW=$(cd infra/terraform && terraform output -raw raw_bucket)
gsutil cp data/samples/new_to_old_bad.csv gs://$RAW/acme/roster.csv
```

Within seconds the Cloud Run service runs the pipeline in `gcp` mode and writes:

- `canonify.canonical_employee_benefits` — mapped tabular data
- `canonify.mapping_audit_report`, `canonify.judge_decision_log`, `canonify.review_queue`
- `canonify.learned_dictionary` — promoted mappings (accuracy compounds per tenant)

Inspect results:

```bash
bq query --use_legacy_sql=false \
  'SELECT * FROM canonify.judge_decision_log ORDER BY confidence LIMIT 20'
```

## The human-review loop (governance)

Low-confidence and sensitive items land in `canonify.review_queue`. An SME approves a mapping by
inserting it into `learned_dictionary` (or via a Looker Studio / lightweight UI). The next run for
that tenant retrieves it via RAG and auto-accepts — the marginal cost of each new file falls.

## Cost & safety notes

- Gemini calls only fire on *ambiguous* headers (below the accept threshold), keeping cost low.
- The deterministic core still runs if Vertex AI is unavailable — no single point of failure.
- Buckets use uniform access; the runner SA is least-privilege (see `main.tf` `runner_roles`).

## Teardown

```bash
cd infra/terraform && terraform destroy -var="project_id=$PROJECT_ID" -var="region=$REGION" -var="image=$IMAGE"
```
