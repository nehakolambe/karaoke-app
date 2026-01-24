resource "helm_release" "rabbitmq" {
  name       = "rabbitmq"
  chart      = "oci://registry-1.docker.io/bitnamicharts/rabbitmq"
  namespace  = "default"

  version = "16.0.14"

  set {
    name  = "auth.username"
    value = "user"
  }

  set {
    name  = "auth.password"
    value = "password"
  }

  set {
    name  = "auth.erlangCookie"
    value = "thisisasecretcookie"  # Needed for clustering, can be anything
  }

  set {
    name  = "service.type"
    value = "ClusterIP"
  }

  set {
    name  = "global.security.allowInsecureImages"
    value = "true"
  }

  # --- REQUIRED: override broken Bitnami image ---
  set {
    name  = "image.registry"
    value = "docker.io"
  }

  set {
    name  = "image.repository"
    value = "bitnamilegacy/rabbitmq"
  }

  set {
    name  = "image.tag"
    value = "4.1.3-debian-12-r1"
  }

  # --- RECOMMENDED: avoid broken installs ---
  atomic          = true
  cleanup_on_fail = true
  timeout         = 600
}