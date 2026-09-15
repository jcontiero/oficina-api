# ADR-009: Padrão Outbox e Pub/Sub
## Decisão Permanente
Toda emissão de eventos externos ocorre gravando na tabela `outbox_eventos` na mesma transaction do BD que altera os dados de negocio. Um worker K8s as transmite de forma At-Least-Once.
