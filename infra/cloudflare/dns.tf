# =============================================================================
# Cloudflare DNS Configuration
# =============================================================================
# This is a reference configuration for Cloudflare DNS.
# Apply this after deploying Cloud Run and Vercel.
#
# Note: This requires the Cloudflare Terraform provider and API token.
# For initial setup, manual DNS configuration via the Cloudflare dashboard
# is recommended (see docs/DEPLOYMENT.md).

# terraform {
#   required_providers {
#     cloudflare = {
#       source  = "cloudflare/cloudflare"
#       version = "~> 4.20"
#     }
#   }
# }
#
# provider "cloudflare" {
#   api_token = var.cloudflare_api_token
# }
#
# variable "cloudflare_zone_id" {
#   type        = string
#   description = "Cloudflare zone ID for infracents.dev"
# }
#
# variable "cloudflare_api_token" {
#   type        = string
#   sensitive   = true
#   description = "Cloudflare API token"
# }
#
# # Frontend (Vercel)
# resource "cloudflare_record" "frontend" {
#   zone_id = var.cloudflare_zone_id
#   name    = "@"
#   value   = "cname.vercel-dns.com"
#   type    = "CNAME"
#   proxied = false  # Vercel manages SSL
# }
#
# # API (Cloud Run)
# resource "cloudflare_record" "api" {
#   zone_id = var.cloudflare_zone_id
#   name    = "api"
#   value   = "infracents-api-xxxxx-uc.a.run.app"  # Replace with actual Cloud Run URL
#   type    = "CNAME"
#   proxied = true  # Cloudflare proxy for DDoS protection
# }
#
# # SSL configuration
# resource "cloudflare_zone_settings_override" "ssl" {
#   zone_id = var.cloudflare_zone_id
#
#   settings {
#     ssl              = "strict"
#     always_use_https = "on"
#     min_tls_version  = "1.2"
#   }
# }
