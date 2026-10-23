# OpenTofu Network & Zero-Trust mTLS Mesh Module for NCA (Section 15 & 16)
variable "environment" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.88.0.0/16"
}

output "cluster_network_policy_mode" {
  value = "deny-all-default-with-mtls"
}
