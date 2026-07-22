terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------------------------------
# APIs
# ---------------------------------------------------------------------------------------------------
locals {
  services = [
    "run.googleapis.com",
    "eventarc.googleapis.com",
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "pubsub.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)
  service  = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------------------------------
# Storage: raw input + outputs buckets
# ---------------------------------------------------------------------------------------------------
resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-${var.name_prefix}-raw"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

resource "google_storage_bucket" "outputs" {
  name                        = "${var.project_id}-${var.name_prefix}-outputs"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

# ---------------------------------------------------------------------------------------------------
# BigQuery: canonical data + audit logs + learned dictionary
# ---------------------------------------------------------------------------------------------------
resource "google_bigquery_dataset" "canonify" {
  dataset_id                 = replace(var.name_prefix, "-", "_")
  location                   = var.region
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "learned_dictionary" {
  dataset_id          = google_bigquery_dataset.canonify.dataset_id
  table_id            = "learned_dictionary"
  deletion_protection = false
  schema = jsonencode([
    { name = "namespace", type = "STRING" },
    { name = "source_header", type = "STRING" },
    { name = "canonical_column", type = "STRING" },
    { name = "confidence", type = "FLOAT64" },
    { name = "votes", type = "INT64" },
    { name = "updated_at", type = "TIMESTAMP" },
  ])
}

# ---------------------------------------------------------------------------------------------------
# Service account for the pipeline (least privilege)
# ---------------------------------------------------------------------------------------------------
resource "google_service_account" "runner" {
  account_id   = "${var.name_prefix}-runner"
  display_name = "Canonify pipeline runner"
}

locals {
  runner_roles = [
    "roles/aiplatform.user",        # Gemini
    "roles/bigquery.dataEditor",    # write canonical + logs
    "roles/bigquery.jobUser",       # run queries
    "roles/storage.objectViewer",   # read raw
    "roles/storage.objectCreator",  # write outputs
  ]
}

resource "google_project_iam_member" "runner" {
  for_each = toset(local.runner_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.runner.email}"
}

# ---------------------------------------------------------------------------------------------------
# Cloud Run service (runs the pipeline; invoked by Eventarc on new files)
# ---------------------------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "pipeline" {
  name     = "${var.name_prefix}-pipeline"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.runner.email
    containers {
      image = var.image
      env {
        name  = "CANONIFY_MODE"
        value = "gcp"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "CANONIFY_LOCATION"
        value = var.region
      }
      env {
        name  = "CANONIFY_GEMINI_MODEL"
        value = var.gemini_model
      }
    }
  }
  depends_on = [google_project_service.enabled]
}

# ---------------------------------------------------------------------------------------------------
# Eventarc: new object in raw bucket -> Cloud Run service
# ---------------------------------------------------------------------------------------------------
resource "google_service_account" "eventarc" {
  account_id   = "${var.name_prefix}-eventarc"
  display_name = "Canonify Eventarc trigger"
}

resource "google_project_iam_member" "eventarc_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.eventarc.email}"
}

resource "google_eventarc_trigger" "on_upload" {
  name            = "${var.name_prefix}-on-upload"
  location        = var.region
  service_account = google_service_account.eventarc.email

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.raw.name
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.pipeline.name
      region  = var.region
      path    = "/"
    }
  }
  depends_on = [google_project_iam_member.eventarc_invoker]
}
