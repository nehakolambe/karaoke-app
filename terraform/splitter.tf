resource "kubernetes_deployment" "music_splitter" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "music-splitter"
    labels = {
      app = "music-splitter"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "music-splitter"
      }
    }

    template {
      metadata {
        labels = {
          app = "music-splitter"
        }
      }

      spec {
        dynamic "image_pull_secrets" {
          for_each = var.use_image_pull_secret ? [1] : []
          content {
            name = "regcred"
          }
        }

        container {
          name  = "music-splitter"
          image = "us-central1-docker.pkg.dev/bda-karaoke-app/voxoff-registry/music-splitter:v1.0"

          port {
            container_port = 8080
          }

          env {
            name  = "RABBITMQ_HOST"
            value = "rabbitmq.default.svc.cluster.local"
          }

          env {
            name = "RABBITMQ_USER"
            value = "user"
          }

          env {
            name = "RABBITMQ_PASS"
            value = "password"
          }

          # GCP Credentials path
          env {
            name  = "GOOGLE_APPLICATION_CREDENTIALS"
            value = "/secrets/service-account.json"
          }

          # Mount GCP service account key
          volume_mount {
            name       = "gcp-creds"
            mount_path = "/secrets"
            read_only  = true
          }

          resources {
            requests = {
              memory = "6Gi"
              cpu    = "1500m"
            }
            limits = {
              memory = "12Gi"
              cpu    = "3000m"
            }
          }
        }

        # Define the secret volume
        volume {
          name = "gcp-creds"
          secret {
            secret_name = "firestore-key"
          }
        }
      }
    }
  }
}
