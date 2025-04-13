resource "kubernetes_deployment" "sync_lyrics" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "sync-lyrics"
    labels = {
      app = "sync-lyrics"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "sync-lyrics"
      }
    }

    template {
      metadata {
        labels = {
          app = "sync-lyrics"
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
          name  = "sync-lyrics"
          # image = "us-central1-docker.pkg.dev/bda-karaoke-app/voxoff-registry/sync-lyrics:latest"
          image = "nehakolambe15/sync-lyrics:latest"

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
        }
      }
    }
  }
}

resource "kubernetes_service" "sync_lyrics" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "sync-lyrics"
  }

  spec {
    selector = {
      app = "sync-lyrics"
    }

    port {
      port        = 8080
      target_port = 8080
    }

    type = "ClusterIP"
  }
}
