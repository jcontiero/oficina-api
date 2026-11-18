# Observabilidade da homologação

Dashboard: https://app.datadoghq.com/dashboard/bei-jds-ury/oficina--homologao-e-operaes

Os gráficos usam env:homolog e namespace oficina-homolog. O acesso ao dashboard requer login na organização Datadog do projeto.

## Dados e origem

| Item | Fonte e significado |
| --- | --- |
| Latência média e p95 | Métrica APM trace.fastapi.request, por serviço, em segundos |
| CPU e memória | Métricas Kubernetes por deployment, em millicores e MiB |
| Readiness | GET /health/ready nas três APIs, a cada minuto; 1 indica resposta 200 |
| Uptime observado | Média das amostras de readiness no período exibido, multiplicada por 100; intervalos anteriores à coleta não representam disponibilidade medida |
| Volume diário de OS | COUNT de ordens criadas desde 00h UTC; gauge atualizada por minuto e gráfico diário com rollup máximo |
| Diagnóstico | Média de abertura da Saga até a primeira resposta DiagnosticoConcluido.v1 registrada na Inbox, em etapas encerradas nas últimas 24h |
| Execução e Finalização | Média das permanências encerradas nos estados EM_EXECUCAO e FINALIZADA de historico_os nas últimas 24h |
| Falhas de integração | Logs de erro das APIs/workers, falhas agendadas da Outbox e situações de intervenção/compensação financeira |
| Correlação | Logs JSON com saga_id, os_id, correlation_id, event_id e IDs de trace quando presentes |

As durações são intervalos registrados pelo sistema. Não medem o tempo físico de trabalho do mecânico. A OS da abertura v1 pode permanecer RECEBIDA enquanto a Saga está em DIAGNOSTICO; por isso o tempo dessa etapa é medido pelos registros da Saga/Inbox, sem inventar uma entrada no histórico. Uma etapa sem amostras permanece sem dados, em vez de publicar zero artificial.

## Coletor

scripts/exportar_metricas.py consulta exclusivamente o banco do serviço OS em transação somente leitura e os endpoints HTTP de saúde. Não acessa bancos de Billing ou Execução. Os valores são gauges de snapshot, não incrementos repetidos a cada coleta.

O CronJob oficina-observabilidade, em oficina-homolog, executa a cada minuto com concurrencyPolicy Forbid. O código vem de ConfigMap gerado a partir do script versionado; a imagem é fixada pelo SHA de deploy. O SecretProviderClass específico monta apenas DATABASE_URL. Métricas são enviadas ao Agent por DogStatsD na porta UDP 8125. A API key Datadog não é distribuída ao coletor ou às APIs.

O workflow de deploy da API mantém ConfigMap, SecretProviderClass e CronJob. Para conferir:

```bash
kubectl get cronjob oficina-observabilidade -n oficina-homolog
kubectl get jobs -n oficina-homolog -l app=oficina-observabilidade
kubectl logs -n oficina-homolog -l app=oficina-observabilidade --tail=3
```

## Alertas configurados

- https://app.datadoghq.com/monitors/346614193 — API indisponível ou ausência de coleta por cinco minutos.
- https://app.datadoghq.com/monitors/346614194 — falhas agendadas na Outbox.
- https://app.datadoghq.com/monitors/346614196 — Saga exige intervenção manual.
- https://app.datadoghq.com/monitors/346614203 — compensação financeira pendente.
- https://app.datadoghq.com/monitors/346614210 — logs de erro nas integrações e workers.

Os monitores aparecem no Datadog. Não há destinatário de e-mail ou Slack definido nestas configurações; adicione um destino em cada monitor se desejar notificações fora da plataforma.

## Reproduzir a configuração

As definições ficam em datadog/dashboard.json e datadog/monitors.json. O script atualiza por nome/tag, preservando os mesmos recursos nas reaplicações.

```bash
uv run --extra dev python scripts/configurar_datadog.py
uv run --extra dev python scripts/configurar_datadog.py --apply
```

Sem --apply, apenas apresenta a quantidade de widgets e monitores. Com --apply, valida monitores na API e cria/atualiza os recursos. Usa DD_API_KEY e DD_APP_KEY do ambiente ou as credenciais no Secret Manager do projeto fiap-project-514922. Nenhum valor secreto pertence aos arquivos JSON ou ao Git. A chave de gerenciamento permanece fora dos pods da aplicação.

## Validação operacional

Em 18/11/2026, consultas à API do Datadog confirmaram séries de latência das três APIs, CPU/memória dos deployments, healthchecks das três APIs, volume diário, permanências por status e falhas da Outbox. A busca de logs com env:homolog e saga_id encontrou registros. Os cinco monitores foram criados após validação de suas consultas e foram observados em estado OK. O histórico de disponibilidade começa na ativação do coletor, não nas datas anteriores do projeto.
