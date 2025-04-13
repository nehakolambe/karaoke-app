variable "use_image_pull_secret" {
  description = "Whether to use imagePullSecret (needed for Minikube)"
  type        = bool
  default     = false
}

variable "region" {
  description = "GCP region for Cloud Run and other services"
  type        = string
  default     = "us-central1"
}

variable "project_id" {
  description = "bda-karaoke-app"
  type        = string
}

