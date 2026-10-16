# OpenTofu Root Module for NCA Sovereign Cluster (Section 15 & 16, OQ-003)
terraform {
  required_version = ">= 1.8.0"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Target environment (dev, staging, prod, dr)"
}

variable "region" {
  type        = string
  default     = "ss-juba-nca-1"
  description = "In-country National Communication Authority (NCA) data centre region"
}
