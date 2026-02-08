# =============================================================================
# Outputs
# =============================================================================

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.api.uri
  description = "Cloud Run service URL"
}

output "cloud_run_service_name" {
  value       = google_cloud_run_v2_service.api.name
  description = "Cloud Run service name"
}

output "artifact_registry_repo" {
  value       = google_artifact_registry_repository.infracents.name
  description = "Artifact Registry repository name"
}

output "service_account_email" {
  value       = google_service_account.cloud_run.email
  description = "Cloud Run service account email"
}
