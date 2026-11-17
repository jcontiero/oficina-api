terraform {
  backend "gcs" {
    bucket = "fiap-project-514922-tfstate"
    prefix = "services/oficina-api"
  }
}
