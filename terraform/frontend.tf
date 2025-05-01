resource "kubernetes_deployment" "frontend" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "frontend"
    labels = {
      app = "frontend"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "frontend"
      }
    }

    template {
      metadata {
        labels = {
          app = "frontend"
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
          name  = "frontend"
          image = "us-central1-docker.pkg.dev/bda-karaoke-app/voxoff-registry/frontend:v1.0"
          # image = "nehakolambe15/frontend:latest"

          port {
            container_port = 5001
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

          env_from {
            secret_ref {
              name = "frontend-env"
            }
          }

          env {
            name  = "SERVICE_ACCOUNT_PATH"
            value = "/secrets/service-account.json"
          }

          env {
            name  = "DATA_READER_URL"
            value = "http://data-reader.default.svc.cluster.local:5002"
          }

          env {
            name  = "AUTH_URL"
            value = "http://auth-service.default.svc.cluster.local:8000"
          }


          volume_mount {
            name       = "gcp-creds"
            mount_path = "/secrets"
            read_only  = true
          }
        }

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

resource "kubernetes_service" "frontend" {
  depends_on = [helm_release.rabbitmq]

  metadata {
    name = "frontend"
  }

  spec {
    selector = {
      app = "frontend"
    }

    port {
      port        = 80
      target_port = 5001
    }

    type = "LoadBalancer"

    load_balancer_ip = "34.134.220.179"
  }
}
