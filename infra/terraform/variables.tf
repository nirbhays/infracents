# =============================================================================
# Input Variables
# =============================================================================

variable "project_id" {
  type        = string
  description = "Google Cloud project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Primary deployment region"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Environment name (production, staging)"
}

variable "domain" {
  type        = string
  default     = "infracents.dev"
  description = "Primary domain name"
}

variable "api_domain" {
  type        = string
  default     = "api.infracents.dev"
  description = "API subdomain"
}

variable "database_url" {
  type        = string
  sensitive   = true
  description = "PostgreSQL connection string (Supabase)"
}

variable "redis_url" {
  type        = string
  sensitive   = true
  description = "Redis connection string (Upstash)"
}

variable "github_app_id" {
  type        = string
  description = "GitHub App ID"
}

variable "github_webhook_secret" {
  type        = string
  sensitive   = true
  description = "GitHub webhook HMAC secret"
}

variable "github_private_key" {
  type        = string
  sensitive   = true
  description = "GitHub App private key (PEM)"
}

variable "stripe_secret_key" {
  type        = string
  sensitive   = true
  description = "Stripe secret API key"
}

variable "stripe_webhook_secret" {
  type        = string
  sensitive   = true
  description = "Stripe webhook signing secret"
}

variable "cloud_run_max_instances" {
  type        = number
  default     = 100
  description = "Maximum Cloud Run instances"
}

variable "cloud_run_min_instances" {
  type        = number
  default     = 0
  description = "Minimum Cloud Run instances (0 = scale to zero)"
}
