# =============================================================================
# Database Configuration
# =============================================================================
# Note: We use Supabase for PostgreSQL (managed externally).
# This file documents the expected database setup and could be used
# for Cloud SQL if you prefer a fully Google-managed database.

# If using Cloud SQL instead of Supabase, uncomment:
#
# resource "google_sql_database_instance" "main" {
#   name             = "infracents-db"
#   database_version = "POSTGRES_16"
#   region           = var.region
#
#   settings {
#     tier              = "db-f1-micro"  # Start small, scale as needed
#     availability_type = "ZONAL"        # REGIONAL for production HA
#
#     disk_size         = 10
#     disk_autoresize   = true
#     disk_type         = "PD_SSD"
#
#     backup_configuration {
#       enabled                        = true
#       point_in_time_recovery_enabled = true
#       start_time                     = "03:00"
#     }
#
#     ip_configuration {
#       ipv4_enabled = true
#       authorized_networks {
#         name  = "cloud-run"
#         value = "0.0.0.0/0"  # In production, use VPC connector
#       }
#     }
#
#     database_flags {
#       name  = "max_connections"
#       value = "100"
#     }
#   }
#
#   deletion_protection = true
# }
#
# resource "google_sql_database" "infracents" {
#   name     = "infracents"
#   instance = google_sql_database_instance.main.name
# }
#
# resource "google_sql_user" "infracents" {
#   name     = "infracents"
#   instance = google_sql_database_instance.main.name
#   password = random_password.db_password.result
# }
#
# resource "random_password" "db_password" {
#   length  = 32
#   special = true
# }
