resource "helm_release" "rabbitmq" {
  name       = "rabbitmq"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "rabbitmq"
  namespace  = "default"

  version = "12.1.3"

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
}
