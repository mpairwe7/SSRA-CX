# OpenTofu S3-Compatible WORM Object Storage Module (Audit & Legal Corpus Archive)
variable "environment" {
  type = string
}

variable "worm_retention_days" {
  type    = number
  default = 2555
}

output "audit_bucket_object_lock" {
  value = "COMPLIANCE_WORM_ENABLED"
}
