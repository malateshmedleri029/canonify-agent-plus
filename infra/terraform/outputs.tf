output "raw_bucket" {
  value       = google_storage_bucket.raw.name
  description = "Upload raw files here to trigger the pipeline."
}

output "outputs_bucket" {
  value       = google_storage_bucket.outputs.name
  description = "Canonical artifacts land here."
}

output "bq_dataset" {
  value       = google_bigquery_dataset.canonify.dataset_id
  description = "BigQuery dataset for canonical data + audit logs."
}

output "pipeline_service" {
  value       = google_cloud_run_v2_service.pipeline.name
  description = "Cloud Run service running the pipeline."
}

output "runner_service_account" {
  value       = google_service_account.runner.email
  description = "Least-privilege SA used by the pipeline."
}
