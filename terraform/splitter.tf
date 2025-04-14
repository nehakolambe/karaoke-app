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
        # Useful to let minikube pull from Google artifact registry.
        dynamic "image_pull_secrets" {
          for_each = var.use_image_pull_secret ? [1] : []
          content {
            name = "regcred"
          }
        }

        container {
          name  = "music-splitter"
          image = "us-central1-docker.pkg.dev/bda-karaoke-app/voxoff-registry/music-splitter:latest"
          # image = "pratikbhirud/music-splitter:latest"


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

resource "kubernetes_service" "music_splitter" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "music-splitter"
  }

  spec {
    selector = {
      app = "music-splitter"
    }

    port {
      port        = 8080
      target_port = 8080
    }

    type = "ClusterIP"
  }
}

