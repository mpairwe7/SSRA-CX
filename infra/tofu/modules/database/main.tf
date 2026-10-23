# OpenTofu Database & Valkey HA Module (CloudNativePG PostgreSQL 18 + pgvector 0.8+)
variable "environment" {
  type = string
}

variable "pg_instances" {
  type    = number
  default = 3
}

output "rpo_minutes" {
  value = 5
}

output "rto_minutes" {
  value = 60
}
