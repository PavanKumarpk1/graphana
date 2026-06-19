terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Custom VPC Network
resource "google_compute_network" "vpc" {
  name                    = "todo-vpc-v2"
  auto_create_subnetworks = false
}

# 2. Custom Subnet for GKE
resource "google_compute_subnetwork" "subnet" {
  name          = "todo-gke-subnet-v2"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id

  secondary_ip_range {
    range_name    = "k8s-pods"
    ip_cidr_range = "10.4.0.0/14"
  }

  secondary_ip_range {
    range_name    = "k8s-services"
    ip_cidr_range = "10.8.0.0/20"
  }
}

# 3. GKE Control Plane
resource "google_container_cluster" "gke" {
  name                = var.cluster_name
  location            = var.region
  deletion_protection = false

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  remove_default_node_pool = true
  initial_node_count       = 1

  node_config {
    disk_size_gb = 32
    disk_type    = "pd-standard"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "k8s-pods"
    services_secondary_range_name = "k8s-services"
  }

  release_channel {
    channel = "REGULAR"
  }
}

# 4. Core Workload Pool
resource "google_container_node_pool" "core_pool" {
  name       = "todo-core-pool"
  location   = var.region
  cluster    = google_container_cluster.gke.name
  node_count = 1

  node_config {
    preemptible  = true
    machine_type = "e2-medium"
    image_type   = "cos_containerd" # <--- Forces the lightweight container OS
    disk_size_gb = 40               # <--- Safe, tiny size for testing

    labels = {
      "workload" = "todo-core"
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}

# 5. Secondary Workload Pool
resource "google_container_node_pool" "secondary_pool" {
  name       = "todo-secondary-pool"
  location   = var.region
  cluster    = google_container_cluster.gke.name
  node_count = 1

  node_config {
    preemptible  = true
    machine_type = "e2-medium"
    image_type   = "cos_containerd" # <--- Forces the lightweight container OS
    disk_size_gb = 40               # <--- Safe, tiny size for testing

    labels = {
      "workload" = "todo-secondary"
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}