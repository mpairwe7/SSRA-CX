# OpenTofu Compute & Sovereign GPU Pool Module (RKE2 / k3s at NCA — OQ-003)
variable "environment" {
  type = string
}

variable "gpu_node_count" {
  type    = number
  default = 2
}

output "inference_engine" {
  value = "vllm-sovereign-gpu"
}
