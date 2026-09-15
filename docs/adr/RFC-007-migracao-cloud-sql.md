# RFC-007: Migração Cloud SQL
## Contexto
Necessidade de provisionar o Cloud SQL via Terraform com down-time mínimo no Tech Challenge.
## Decisão
Foi provisionado o BD numa VPC privada. A migracao é garantida pelos scripts alembic que rodam em um Job no K8s antes do rollout do Deployment (Expand and Contract strategy).
