# ADR-017: Topologia de Mensageria Pub/Sub, Envelope Versionado e Padrão Outbox/Inbox com Lease

- **Data:** 2026-11-16
- **Status:** Aceito (Fase 4 — Etapa P1)
- **Contexto:** O Google Cloud Pub/Sub possui semântica de entrega *at-least-once* e pode entregar mensagens fora de ordem. Na Fase 3, o `src/worker.py` publicava apenas o payload bruto sem `event_id` estável, marcava falhas definitivamente como `ERRO` sem reprocessamento e não utilizava lock concorrente (`SKIP LOCKED`), sendo insuficiente para sustentar uma Saga distribuída com múltiplas réplicas.

## Decisão

1. **Topologia de Tópicos e Subscriptions por Ambiente (`homolog` e `production`):**
   - **Tópico de Eventos de Domínio/Saga:** `oficina-{env}-eventos-v1`
     - Subscriptions exclusivas por consumidor lógico:
       - `oficina-{env}-os-orquestrador-eventos-sub` (consumido pelo OS Service)
       - `oficina-{env}-notificacoes-eventos-sub` (consumido pela Cloud Function de notificações)
   - **Tópico de Comandos para Billing:** `oficina-{env}-billing-comandos-v1`
     - Subscription: `oficina-{env}-billing-comandos-sub` (consumido apenas por `oficina-billing`; publicação restrita por IAM à Service Account do OS Service).
   - **Tópico de Comandos para Execução:** `oficina-{env}-execucao-comandos-v1`
     - Subscription: `oficina-{env}-execucao-comandos-sub` (consumido apenas por `oficina-execucao`; publicação restrita por IAM à Service Account do OS Service).
   - **Dead Letter Queues (DLQ):** Cada subscription possui política de retry com backoff exponencial e encaminhamento para tópico DLQ (`*-dlq`) com subscription de inspeção e alerta imediato no Datadog (`DLQ > 0`).

2. **Envelope Obrigatório Versionado (`schema_version = 1`):**
   - Toda mensagem (comando ou evento) trafega serializada em JSON UTF-8 seguindo o schema `docs/contratos/schemas/envelope-v1.schema.json`, contendo obrigatoriamente:
     `event_id` (UUID estável gerado na criação da outbox), `event_type` (ex.: `PagamentoConfirmado.v1`), `schema_version` (`1`), `occurred_at` (RFC3339 UTC), `producer`, `saga_id`, `os_id`, `correlation_id`, `causation_id`, `aggregate_version` e `payload`.
   - Atributos da mensagem Pub/Sub: `event_type`, `producer`, `schema_version` e `traceparent` (W3C Trace Context para correlação distribuída no Datadog APM). Dados sensíveis (CPF em claro, senhas, tokens JWT ou chaves de API) são proibidos no payload e nos atributos.

3. **Transactional Outbox com Lease e Retry Exponencial:**
   - A mutação das entidades de negócio e a inserção do registro na `outbox` ocorrem na **mesma transação local** (SQL ou Firestore).
   - Campos da `outbox`: `id` (`event_id`), `event_type`, `envelope_json`, `traceparent`, `status` (`PENDENTE`, `PUBLICADO`, `DLQ`), `tentativas`, `next_attempt_at`, `locked_until`, `ultimo_erro`, `criado_em`, `publicado_em`.
   - O worker publicador reivindica lotes elegíveis (`status = 'PENDENTE' AND next_attempt_at <= NOW() AND (locked_until IS NULL OR locked_until < NOW())`) gravando `locked_until = NOW() + 30s` (usando `FOR UPDATE SKIP LOCKED` no PostgreSQL e transação atômica no Firestore) e publica no Pub/Sub **fora** da transação de banco.
   - Somente após confirmação do `message_id` pelo broker o item é marcado como `PUBLICADO`. Em falha de rede/broker, incrementa `tentativas`, agenda `next_attempt_at` com backoff exponencial + jitter e limpa `locked_until`, mantendo o registro elegível para reprocessamento.

4. **Transactional Inbox e Tombstones para Idempotência e Fora de Ordem:**
   - No consumidor, o processamento grava `inbox(consumer, event_id, received_at)` com chave única composta na **mesma transação** da alteração de domínio e da eventual geração de nova `outbox`.
   - O `ACK` no Pub/Sub ocorre exclusivamente após o commit local. Se a mensagem já constar na `inbox`, o consumidor realiza `ACK` imediato sem repetir efeitos colaterais.
   - Comandos de cancelamento (`CancelarExecucao.v1`, `CancelarOrcamento.v1`, `CancelarCobranca.v1`) gravam *tombstones* por `(saga_id, rodada)` mesmo que o comando de criação correspondente ainda não tenha chegado, bloqueando criações tardias fora de ordem.

## Consequências

- **Positivas:** Tolerância a quedas entre commit e publicação, entre publicação e atualização da outbox e entre commit do consumidor e ACK; suporte seguro a múltiplas réplicas de API e workers no GKE.
- **Trade-offs:** Necessidade de rotina periódica de limpeza/arquivamento de registros antigos de `inbox` e `outbox` já publicados.
