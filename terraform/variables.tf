variable "use_image_pull_secret" {
  description = "Whether to use imagePullSecret (needed for Minikube)"
  type        = bool
  default     = false
}