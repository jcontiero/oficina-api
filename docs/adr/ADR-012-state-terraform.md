# ADR-012: State do Terraform no GCS
## Decisão Permanente
Os estados `.tfstate` dos repositorios ficam salvos remotamente em buckets GCS isolados, provendo controle de concorrência central.
