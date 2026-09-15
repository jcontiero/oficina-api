# RFC-006: Observabilidade com Datadog (Coleta, Sampling e Custos)

## Proposta
Implementar o Datadog Agent no cluster GKE (via Helm), delegando a coleta de logs via daemonset em vez de fluent-bit/GCP Cloud Logging puro, e habilitando a porta APM via hostPort/serviço.

## Coleta
- **Logs**: O Datadog Agent captura a saída padrão JSON do `uvicorn` / `worker`.
- **Traces**: A injeção automática de Spans no banco de dados e FastAPI ocorre pela biblioteca `ddtrace`.

## Sampling e Retenção
- Para o APM, o padrão será retenção de 100% de ingestão no plano trial/inicial, podendo ser reduzido por regras de ingestion no Datadog (e.g. 20% para tráfego saudável) em produção.
- Logs: 15 dias de retenção indexada e arquivamento em cold storage (GCS) para compliance.

## Conclusão
Aceito para a Fase 3 - Pacote 10, consolidando-se no ADR-011.
