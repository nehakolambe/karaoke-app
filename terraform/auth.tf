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
          image = "us-central1-docker.pkg.dev/bda-karaoke-app/voxoff-registry/auth-service:v1.0" # Replace if using remote image or use `minikube image load`
          name  = "auth-service"

          port {
            container_port = 8000
          }

          env {
            name = "GOOGLE_CLIENT_ID"
            value = "102057894489695516768"
          }

          env {
            name  = "FRONTEND_URL"
            value = "http://34.134.220.179"
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
      app = "auth"
    }

    port {
      port        = 8000
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}



