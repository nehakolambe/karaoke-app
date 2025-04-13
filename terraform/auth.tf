resource "kubernetes_deployment" "auth" {
  metadata {
    name = "auth-service"
    labels = {
      app = "auth"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "auth"
      }
    }

    template {
      metadata {
        labels = {
          app = "auth"
        }
      }

      spec {
        container {
          image = "srsa1520/auth-service:latest" # Replace if using remote image or use `minikube image load`
          name  = "auth-service"

          port {
            container_port = 8080
          }

          env {
            name = "GOOGLE_CLIENT_ID"
            value = "102057894489695516768" # Replace with real or use secret
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "auth_service" {
  metadata {
    name = "auth-service"
  }

  spec {
    selector = {
      app = "auth"  # Match label in your deployment
    }

    port {
      port        = 8000         # Exposed service port
      target_port = 8000      # Must match container_port in Deployment
    }

    type = "LoadBalancer"
  }
}



