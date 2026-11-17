terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type    = string
  default = "fiap-project-514922"
}

variable "region" {
  type    = string
  default = "us-east1"
}

variable "environment" {
  type    = string
  default = "homolog"
}

locals {
  env_canon = var.environment == "prod" ? "production" : var.environment
  k8s_ns    = local.env_canon == "production" ? "oficina-prod" : "oficina-homolog"
}

data "terraform_remote_state" "cloudsql" {
  backend = "gcs"
  config = {
    bucket = "fiap-project-514922-tfstate"
    prefix = "platform/cloudsql"
  }
}

resource "random_password" "os_db_password" {
  length  = 24
  special = false
}

resource "random_password" "api_secret_key" {
  length  = 48
  special = false
}

resource "tls_private_key" "admin_jwt" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "google_sql_database" "os_db" {
  name     = "oficina_os_${local.env_canon}"
  instance = data.terraform_remote_state.cloudsql.outputs.cloud_sql_instance_name
}

resource "google_sql_user" "os_user" {
  name     = "oficina_os_${local.env_canon}"
  instance = data.terraform_remote_state.cloudsql.outputs.cloud_sql_instance_name
  password = random_password.os_db_password.result
}

resource "google_service_account" "api_sa" {
  account_id   = "oficina-api-${local.env_canon}-sa"
  display_name = "Runtime SA para oficina-api (${local.env_canon})"
}

resource "google_service_account_iam_member" "workload_identity" {
  service_account_id = google_service_account.api_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${local.k8s_ns}/oficina-api-sa]"
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api_sa.email}"
}

resource "google_pubsub_subscription" "os_orquestrador_sub" {
  name  = "oficina-${local.env_canon}-os-orquestrador-sub"
  topic = "projects/${var.project_id}/topics/oficina-${local.env_canon}-eventos-v1"

  ack_deadline_seconds = 30
  dead_letter_policy {
    dead_letter_topic     = "projects/${var.project_id}/topics/oficina-${local.env_canon}-eventos-v1-dlq"
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription_iam_member" "api_sub_reader" {
  subscription = google_pubsub_subscription.os_orquestrador_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.api_sa.email}"
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "oficina-api-database-url-${local.env_canon}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql+pg8000://${google_sql_user.os_user.name}:${random_password.os_db_password.result}@${data.terraform_remote_state.cloudsql.outputs.cloud_sql_private_ip}:5432/${google_sql_database.os_db.name}"
}

resource "google_secret_manager_secret_iam_member" "database_url_access" {
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api_sa.email}"
}

resource "google_secret_manager_secret" "secret_key" {
  secret_id = "oficina-api-secret-key-${local.env_canon}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "secret_key" {
  secret      = google_secret_manager_secret.secret_key.id
  secret_data = random_password.api_secret_key.result
}

resource "google_secret_manager_secret_iam_member" "secret_key_access" {
  secret_id = google_secret_manager_secret.secret_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api_sa.email}"
}

resource "google_secret_manager_secret" "admin_jwt_private_key" {
  secret_id = "oficina-api-admin-jwt-private-key-${local.env_canon}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "admin_jwt_private_key" {
  secret      = google_secret_manager_secret.admin_jwt_private_key.id
  secret_data = tls_private_key.admin_jwt.private_key_pem
}

resource "google_secret_manager_secret_iam_member" "admin_jwt_private_key_access" {
  secret_id = google_secret_manager_secret.admin_jwt_private_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api_sa.email}"
}

output "database_name" {
  value = google_sql_database.os_db.name
}

output "service_account_email" {
  value = google_service_account.api_sa.email
}

output "pubsub_subscription" {
  value = google_pubsub_subscription.os_orquestrador_sub.name
}

output "database_url_secret_id" {
  value = google_secret_manager_secret.database_url.secret_id
}

output "admin_jwt_private_key_secret_id" {
  value = google_secret_manager_secret.admin_jwt_private_key.secret_id
}
