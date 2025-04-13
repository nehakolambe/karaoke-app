resource "kubernetes_deployment" "music_downloader" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "music-downloader"
    labels = {
      app = "music-downloader"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "music-downloader"
      }
    }

    template {
      metadata {
        labels = {
          app = "music-downloader"
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
          name  = "music-downloader"
          # image = "us-central1-docker.pkg.dev/bda-karaoke-app/voxoff-registry/music-downloader:latest"
          image = "suyog005/music-downloader:latest"

          port {
            container_port = 8080
          }

          env {
            name  = "RABBITMQ_HOST"
            value = "rabbitmq.default.svc.cluster.local"
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "music_downloader" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "music-downloader"
  }

  spec {
    selector = {
      app = "music-downloader"
    }

    port {
      port        = 8080
      target_port = 8080
    }

    type = "ClusterIP"
  }
}
