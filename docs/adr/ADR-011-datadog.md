# ADR-011: Observabilidade com Datadog

## Status
Aceito

## Contexto
O projeto precisa de uma solução robusta de monitoramento e observabilidade, abrangendo logs estruturados, métricas e tracing (APM) para acompanhar as execuções de ordens de serviço.

## Decisão
Adotamos o **Datadog** como plataforma unificada de observabilidade.
1. **Tracing (APM)**: Instrumentação via `ddtrace` em Python.
2. **Logs**: JSON stdout injetando `dd.trace_id` permitindo a correlação direta no painel.
3. **Métricas**: Métricas de negócio (como OS's aprovadas ou criadas) são extraídas a partir de Logs e Spans customizados (Log-based metrics).

## Consequências
- A aplicação Python agora tem dependência do `ddtrace` e de JSON logging.
- O provisionamento via Terraform da infraestrutura necessita injetar uma `DD_API_KEY`.
- Traz forte correlação de requisições, mas eleva o vendor lock-in levemente com APM de agentes proprietários.
