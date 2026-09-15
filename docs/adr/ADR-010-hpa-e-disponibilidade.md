# ADR-010: HPA e Disponibilidade
## Decisão Permanente
A `oficina-api` conta com Kubernetes Horizontal Pod Autoscaler (HPA) baseado em métricas de CPU/Memory e `minReplicas` = 2, atrelado com PodDisruptionBudget.
