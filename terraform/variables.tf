variable "project_id" {
  type        = string
  description = "The GCP Project ID where resources will be deployed."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "The GCP region for the cluster."
}

variable "cluster_name" {
  type        = string
  default     = "todo-microservices-cluster"
  description = "The name of the GKE cluster."
}