variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "GCP region for all regional resources."
}

variable "name_prefix" {
  type        = string
  default     = "canonify"
  description = "Prefix for resource names."
}

variable "image" {
  type        = string
  description = "Fully-qualified container image, e.g. us-central1-docker.pkg.dev/PROJECT/canonify/app:latest"
}

variable "gemini_model" {
  type        = string
  default     = "gemini-2.0-flash"
}
