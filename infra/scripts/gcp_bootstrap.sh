#!/usr/bin/env bash
# Bootstrap Canonify Agent+ on GCP: enable APIs, create Artifact Registry, build & push the image,
# then hand off to Terraform. Idempotent-ish; safe to re-run.
#
# Usage:
#   export PROJECT_ID=my-gcp-project
#   export REGION=us-central1
#   ./infra/scripts/gcp_bootstrap.sh
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
REPO="canonify"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/app:latest"

echo ">> Using project=${PROJECT_ID} region=${REGION}"
gcloud config set project "${PROJECT_ID}"

echo ">> Enabling APIs"
gcloud services enable \
  run.googleapis.com eventarc.googleapis.com aiplatform.googleapis.com \
  bigquery.googleapis.com storage.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com pubsub.googleapis.com

echo ">> Ensuring Artifact Registry repo '${REPO}' exists"
gcloud artifacts repositories describe "${REPO}" --location="${REGION}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker --location="${REGION}" \
    --description="Canonify Agent+ images"

echo ">> Building & pushing image with Cloud Build: ${IMAGE}"
gcloud builds submit --tag "${IMAGE}" .

echo ">> Applying Terraform"
pushd infra/terraform >/dev/null
terraform init
terraform apply -auto-approve \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="image=${IMAGE}"
popd >/dev/null

echo ">> Done. Upload a CSV to the raw bucket to trigger the pipeline:"
echo "   gsutil cp data/samples/new_to_old_bad.csv gs://${PROJECT_ID}-canonify-raw/acme/roster.csv"
