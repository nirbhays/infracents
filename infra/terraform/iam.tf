# =============================================================================
# IAM Configuration
# =============================================================================

# Service account for Cloud Run
resource "google_service_account" "cloud_run" {
  account_id   = "infracents-api"
  display_name = "InfraCents API Service Account"
  description  = "Service account for the InfraCents Cloud Run API service"
}

# Allow the service account to access Secret Manager
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Allow the service account to write logs
resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Allow the service account to write metrics
resource "google_project_iam_member" "metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Allow the service account to report errors
resource "google_project_iam_member" "error_reporter" {
  project = var.project_id
  role    = "roles/errorreporting.writer"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}
