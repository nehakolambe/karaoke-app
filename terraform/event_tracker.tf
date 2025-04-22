resource "kubernetes_deployment" "event_tracker" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "event-tracker"
    labels = {
      app = "event-tracker"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "event-tracker"
      }
    }

    template {
      metadata {
        labels = {
          app = "event-tracker"
        }
      }

      spec {
        # Optional: Use pull secret for private Docker Hub image
        dynamic "image_pull_secrets" {
          for_each = var.use_image_pull_secret ? [1] : []
          content {
            name = "regcred"
          }
        }

        container {
          name  = "event-tracker"
          image = "us-central1-docker.pkg.dev/bda-karaoke-app/voxoff-registry/event-tracker:v1.0"
          # image = "suyog005/event-tracker:latest"

          env {
            name  = "RABBITMQ_HOST"
            value = "rabbitmq.default.svc.cluster.local"
          }

          env {
            name  = "RABBITMQ_USER"
            value = "user"
          }

          env {
            name  = "RABBITMQ_PASS"
            value = "password"
          }

          env {
            name  = "GOOGLE_APPLICATION_CREDENTIALS"
            value = "/secrets/service-account.json"
          }

          port {
            container_port = 8080
          }

          volume_mount {
            name       = "firestore-key-volume"
            mount_path = "/secrets"
            read_only  = true
          }
        }

        volume {
          name = "firestore-key-volume"

          secret {
            secret_name = "firestore-key" # Must match kubectl secret name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "event_tracker" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "event-tracker"
  }

  spec {
    selector = {
      app = "event-tracker"
    }

    port {
      port        = 8080
      target_port = 8080
    }

    type = "ClusterIP"
  }
}
