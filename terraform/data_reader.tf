resource "kubernetes_deployment" "data_reader" {
  metadata {
    name = "data-reader"
    labels = {
      app = "data-reader"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "data-reader"
      }
    }

    template {
      metadata {
        labels = {
          app = "data-reader"
        }
      }

      spec {
        container {
          name  = "data-reader"
          image = "srsa1520/data-reader-service:latest"

          port {
            container_port = 5002
          }

          env {
            name  = "GOOGLE_APPLICATION_CREDENTIALS"
            value = "/secrets/service-account.json"
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


resource "kubernetes_service" "data_reader" {
  metadata {
    name = "data-reader"
  }

  spec {
    selector = {
      app = "data-reader"
    }

    port {
      port        = 5002
      target_port = 5002
    }

    type = "LoadBalancer"
  }
}
