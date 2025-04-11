terraform {
  backend "gcs" {
    bucket = "voxoff-terraform-bucket"
    prefix = "state"
  }

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12.0"
    }
  }

  required_version = ">= 1.3"
}

provider "kubernetes" {
  config_path = "~/.kube/config"  # change this if using a different kubeconfig location
}

provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}
