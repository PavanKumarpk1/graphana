output "kubernetes_cluster_name" {
  value       = google_container_cluster.gke.name
  description = "GKE Cluster Name"
}

output "gke_endpoint" {
  value       = google_container_cluster.gke.endpoint
  description = "GKE Control Plane Endpoint"
}