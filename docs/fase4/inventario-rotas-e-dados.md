# Fase 4 · Inventário de Rotas, Propriedade de Dados e Tabela de Compatibilidade (Etapa P1)

Este documento inventaria todas as rotas e estruturas de dados existentes em `oficina-api` e define o mapeamento exato para os três microsserviços da Fase 4 (**OS Service**, **Billing Service** e **Execução Service**).

---

## 1. Inventário Completo das Rotas Atuais (`oficina-api`) e Destino na Fase 4

| # | Método e Path Atual (`oficina-api`) | Módulo Atual | Permissão Atual | Serviço Dono na Fase 4 | Contrato Novo Proposto (`/v1` ou interno) | Estratégia de Transição / Compatibilidade |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `GET /health` | `src/main.py` | Público | Todos (OS, Billing, Execução) | `GET /health/live` | Mantido como alias para compatibilidade. |
| 2 | `GET /health/live` | `src/main.py` | Público | Todos (OS, Billing, Execução) | `GET /health/live` | Liveness apenas do processo HTTP. |
| 3 | `GET /health/ready` | `src/main.py` | Público | Todos (OS, Billing, Execução) | `GET /health/ready` | Readiness verifica conectividade com o banco exclusivo do serviço. |
| 4 | `POST /auth/login` | `src/identidade` | Público | **OS Service** (`oficina-api`) | `POST /auth/login` + `GET /.well-known/admin-jwks.json` | Mantém rota; evolui assinatura de `HS256` para `RS256` (`iss=oficina-admin-{env}`, `aud=oficina-backend-{env}`). |
| 5 | `POST /clientes` | `src/atendimento` | `MECANICO`/`ADMIN` | **OS Service** (`oficina-api`) | `POST /v1/clientes` (alias `/clientes`) | Permanece no OS Service. Suporta `Idempotency-Key`. |
| 6 | `GET /clientes` | `src/atendimento` | `MECANICO`/`ADMIN` | **OS Service** (`oficina-api`) | `GET /v1/clientes` (alias `/clientes`) | Permanece no OS Service. |
| 7 | `GET /clientes/{id}` | `src/atendimento` | `MECANICO`/`ADMIN` | **OS Service** (`oficina-api`) | `GET /v1/clientes/{id}` (alias `/clientes/{id}`) | Permanece no OS Service. |
| 8 | `PUT /clientes/{id}` | `src/atendimento` | `MECANICO`/`ADMIN` | **OS Service** (`oficina-api`) | `PUT /v1/clientes/{id}` (alias `/clientes/{id}`) | Permanece no OS Service. |
| 9 | `DELETE /clientes/{id}` | `src/atendimento` | `ADMIN` | **OS Service** (`oficina-api`) | `DELETE /v1/clientes/{id}` (alias `/clientes/{id}`) | Permanece no OS Service (inativação lógica se não houver OS ativa). |
| 10 | `POST /veiculos` | `src/atendimento` | `MECANICO`/`ADMIN` | **OS Service** (`oficina-api`) | `POST /v1/veiculos` (alias `/veiculos`) | Permanece no OS Service. |
| 11 | `GET /veiculos` | `src/atendimento` | `MECANICO`/`ADMIN` | **OS Service** (`oficina-api`) | `GET /v1/veiculos` (alias `/veiculos`) | Permanece no OS Service. |
| 12 | `GET /veiculos/{id}` | `src/atendimento` | `MECANICO`/`ADMIN` | **OS Service** (`oficina-api`) | `GET /v1/veiculos/{id}` (alias `/veiculos/{id}`) | Permanece no OS Service. |
| 13 | `PUT /veiculos/{id}` | `src/atendimento` | `MECANICO`/`ADMIN` | **OS Service** (`oficina-api`) | `PUT /v1/veiculos/{id}` (alias `/veiculos/{id}`) | Permanece no OS Service. |
| 14 | `DELETE /veiculos/{id}` | `src/atendimento` | `ADMIN` | **OS Service** (`oficina-api`) | `DELETE /v1/veiculos/{id}` (alias `/veiculos/{id}`) | Permanece no OS Service. |
| 15 | `POST /ordens-de-servico` | `src/atendimento` | `ADMIN` | **OS Service** (`oficina-api`) | `POST /v1/ordens-servico` (alias `/ordens-de-servico`) | Abertura inicia a Saga (`saga_id`) e publica `SolicitarDiagnostico.v1` via outbox. Novo contrato retorna `202 Accepted` com `os_id`, `saga_id` e `Location` (rota legada mantém compatibilidade). |
| 16 | `GET /ordens-de-servico` | `src/atendimento` | Autenticado (`CLIENTE`/`MECANICO`/`ADMIN`) | **OS Service** (`oficina-api`) | `GET /v1/ordens-servico` (alias `/ordens-de-servico`) | Lista OS ativas ordenadas pela nova fila de prioridade; filtra por `cliente_id` se `actor_type == CLIENTE`. |
| 17 | `GET /ordens-de-servico/{id}` | `src/atendimento` | Autenticado (dono ou equipe) | **OS Service** (`oficina-api`) | `GET /v1/ordens-servico/{id}` | Retorna status da OS, estado atual da Saga e projeções de orçamento/pagamento/execução. |
| 18 | `GET /ordens-de-servico/{id}/status` | `src/atendimento` | Público / Autenticado | **OS Service** (`oficina-api`) | `GET /v1/ordens-servico/{id}` | Mantido como alias de leitura rápida. |
| 19 | `GET /ordens-de-servico/{id}/acompanhar` | `src/atendimento` | Público / Autenticado | **OS Service** (`oficina-api`) | `GET /v1/ordens-servico/{id}/historico` | Expõe linha do tempo auditável (`HistoricoOS` + etapas da Saga). |
| 20 | `POST /ordens-de-servico/{id}/aprovacao` | `src/atendimento` | `CLIENTE` (dono) ou `ADMIN` | **Billing Service** (`oficina-billing`) | `POST /v1/orcamentos/{orcamento_id}/decisao` | **Extraído para o Billing:** cliente aprova/recusa a versão vigente do orçamento. Responde `202 Accepted` e emite `OrcamentoAprovado.v1` ou `OrcamentoRecusado.v1`. O Gateway/OS mantém proxy/adaptador temporário se chamado pelo path antigo. |
| 21 | `POST /ordens-de-servico/{id}/gerar-orcamento` | `src/atendimento` | `ADMIN` | **Billing Service** (`oficina-billing`) | Comando assíncrono `GerarOrcamento.v1` (Saga) | **Extraído para o Billing:** na Fase 4 o orçamento é gerado automaticamente pela Saga ao receber `DiagnosticoConcluido.v1` (com preços congelados em centavos). |
| 22 | `POST /ordens-de-servico/{id}/iniciar-diagnostico` | `src/atendimento` | `MECANICO`/`ADMIN` | **Execução Service** (`oficina-execucao`) | `POST /v1/execucoes/{id}/diagnostico` | **Extraído para a Execução:** mecânico registra diagnóstico/laudo e itens necessários no serviço de Execução. |
| 23 | `POST /ordens-de-servico/{id}/finalizar-diagnostico` | `src/atendimento` | `MECANICO`/`ADMIN` | **Execução Service** (`oficina-execucao`) | `POST /v1/execucoes/{id}/diagnostico` | Consolidado no endpoint de conclusão de diagnóstico da Execução, que emite `DiagnosticoConcluido.v1`. |
| 24 | `POST /ordens-de-servico/{id}/adicionar-servico` | `src/atendimento` | `ADMIN`/`MECANICO` | **Execução Service** (`oficina-execucao`) | `POST /v1/execucoes/{id}/diagnostico` | Itens de serviço e peça passam a compor o diagnóstico na Execução. |
| 25 | `POST /ordens-de-servico/{id}/adicionar-peca` | `src/atendimento` | `ADMIN`/`MECANICO` | **Execução Service** (`oficina-execucao`) | `POST /v1/execucoes/{id}/diagnostico` | Peças indicadas no diagnóstico geram reserva atômica na etapa `RESERVANDO_PECAS`. |
| 26 | `GET /ordens-de-servico/{id}/itens` | `src/atendimento` | `MECANICO`/`ADMIN` | **Execução Service** (`oficina-execucao`) | `GET /v1/execucoes/{id}` | Consulta de tarefas e peças da execução migra para `oficina-execucao` (com projeção resumida no OS). |
| 27 | `POST /ordens-de-servico/{id}/executar-servico/{item_id}` | `src/atendimento` | `MECANICO`/`ADMIN` | **Execução Service** (`oficina-execucao`) | `POST /v1/execucoes/{id}/iniciar` e `POST /v1/execucoes/{id}/concluir` | **Extraído para a Execução:** o início consome a reserva de peças uma única vez e emite `ExecucaoIniciada.v1`; a conclusão emite `ExecucaoConcluida.v1`. |
| 28 | `POST /ordens-de-servico/{id}/finalizar` | `src/atendimento` | `ADMIN` | **OS Service** (`oficina-api`) | Automático via Saga (`ExecucaoConcluida.v1`) / alias administrativo | Quando a Execução emite `ExecucaoConcluida.v1`, a Saga transiciona a OS para `SERVICOS_CONCLUIDOS` → `FINALIZADA`. |
| 29 | `POST /ordens-de-servico/{id}/entregar` | `src/atendimento` | `ADMIN` | **OS Service** (`oficina-api`) | `POST /v1/ordens-servico/{id}/entrega` (alias `/entregar`) | Permanece no OS Service; permitido somente quando `status == FINALIZADA`. |
| 30 | `POST /webhooks/os/{id}/atualizar-status` | `src/atendimento` | Token Webhook | **Depreciado / Bloqueado para Pular Etapas** | Substituído por `POST /webhooks/mercadopago` no Billing e eventos Pub/Sub da Saga | **Regra crítica (Seção 5):** não é permitido usar webhook genérico para pular confirmação financeira ou estados da Saga. |
| 31 | `POST/GET/PUT/DELETE /servicos*` (5 rotas) | `src/catalogo` | `ADMIN` | **Execução Service** (`oficina-execucao`) | `/v1/servicos*` (alias `/servicos*` no Gateway) | **Extraído para a Execução** (persistido na coleção `servicos` do Firestore). |
| 32 | `POST/GET/PUT/DELETE /pecas*` e `/{id}/repor-estoque` (7 rotas) | `src/estoque` | `ADMIN` | **Execução Service** (`oficina-execucao`) | `/v1/pecas*` (alias `/pecas*` no Gateway) | **Extraído para a Execução** (persistido na coleção `pecas` do Firestore). |
| 33 | `GET /relatorios/tempo-medio-servicos` | `src/relatorios` | `ADMIN` | **OS Service** (`oficina-api`) | `GET /relatorios/tempo-medio-servicos` | Mantido sobre o histórico e projeções locais do OS Service. |

---

## 2. Novas Rotas Exclusivas da Fase 4

| Serviço | Método e Path | Autenticação / Segurança | Responsabilidade |
| :--- | :--- | :--- | :--- |
| **OS Service** (`oficina-api`) | `POST /internal/clientes/autenticacao` | Google OIDC ID Token (`serviceAccount` da Auth Function + audience exata); bloqueado no Gateway público | Recebe `{cpf}` da Cloud Function de autenticação e retorna `{id, status}` do cliente sem expor o banco SQL. |
| **OS Service** (`oficina-api`) | `GET /.well-known/admin-jwks.json` | Público (leitura de chaves públicas) | Publica o conjunto JWK (`RS256`, `kid`) para validação distribuída dos tokens de funcionários (`ADMIN`/`MECANICO`). |
| **OS Service** (`oficina-api`) | `POST /internal/sagas/{id}/retomar` | `ADMIN` (com auditoria e `Idempotency-Key`) | Retoma/reconcilia sagas em `COMPENSACAO_PENDENTE` ou `INTERVENCAO_MANUAL` após resolução operacional. |
| **Billing Service** (`oficina-billing`) | `GET /v1/orcamentos/{id}` | `CLIENTE` (dono) ou `ADMIN`/`MECANICO` | Consulta detalhes do orçamento versionado, itens e status de aprovação. |
| **Billing Service** (`oficina-billing`) | `POST /v1/orcamentos/{id}/decisao` | `CLIENTE` (dono) ou `ADMIN` (`Idempotency-Key`) | Registra aprovação ou recusa `{aprovado, versao, motivo}` e publica `OrcamentoAprovado.v1` ou `OrcamentoRecusado.v1`. |
| **Billing Service** (`oficina-billing`) | `GET /v1/pagamentos/{id}` | `CLIENTE` (dono) ou `ADMIN` | Retorna status da cobrança, `provider_order_id`, `qr_data` dinâmico e valor em centavos. |
| **Billing Service** (`oficina-billing`) | `POST /webhooks/mercadopago` | Público HTTPS + validação HMAC-SHA256 do header `x-signature` | Persiste notificação em `webhook_inbox`, responde `200 OK` e agenda consulta/reconciliação da order no Mercado Pago. |
| **Execução Service** (`oficina-execucao`) | `GET /v1/execucoes` | `MECANICO` / `ADMIN` | Lista a fila de execução e diagnósticos ativos ordenados por prioridade. |
| **Execução Service** (`oficina-execucao`) | `POST /v1/execucoes/{id}/diagnostico` | `MECANICO` / `ADMIN` (`Idempotency-Key`) | Registra o laudo de diagnóstico e lista de serviços/peças necessários, emitindo `DiagnosticoConcluido.v1`. |
| **Execução Service** (`oficina-execucao`) | `POST /v1/execucoes/{id}/iniciar` | `MECANICO` / `ADMIN` (`Idempotency-Key`) | Disputa o documento transacional `controle_saga/{saga_id}`, consome a reserva de peças uma única vez e emite `ExecucaoIniciada.v1`. |
| **Execução Service** (`oficina-execucao`) | `POST /v1/execucoes/{id}/concluir` | `MECANICO` / `ADMIN` (`Idempotency-Key`) | Marca as tarefas de reparo como concluídas e emite `ExecucaoConcluida.v1`. |

---

## 3. Propriedade dos Dados por Serviço (Modelos de Persistência)

### 3.1. OS Service (`oficina-api` · PostgreSQL `oficina_os_{env}`)
- **`clientes`**: `id (UUID PK)`, `nome`, `cpf (UNIQUE)`, `cnpj (UNIQUE)`, `email`, `telefone`, `status (ATIVO/INATIVO)`.
- **`veiculos`**: `id (UUID PK)`, `cliente_id (FK clientes)`, `placa (UNIQUE)`, `marca`, `modelo`, `ano`, `cor`, `status`.
- **`usuarios`**: `id (UUID PK)`, `email (UNIQUE)`, `senha_hash`, `perfil (ADMIN/MECANICO)`.
- **`ordens_de_servico`**: `id (UUID PK)`, `cliente_id (FK clientes)`, `veiculo_id (FK veiculos)`, `descricao_problema`, `status (StatusOS)`, `version (INT)`, `rodada_atual (INT)`, `saga_id_ativa (UUID NULL)`, `orcamento_id_atual (UUID NULL)`, `orcamento_versao_atual (INT NULL)`, `valor_orcamento_centavos (BIGINT NULL)`, `pagamento_status_projecao (VARCHAR NULL)`, `execucao_status_projecao (VARCHAR NULL)`, `laudo_diagnostico_projecao (TEXT NULL)`, `criada_em`, `atualizada_em`.
- **`historico_os`**: `id (UUID PK)`, `os_id (FK ordens_de_servico)`, `status_anterior`, `status_novo`, `ocorrido_em`, `sequencia`, `origem`, `saga_id (UUID NULL)`.
- **`saga_instances`**: `id (UUID PK)`, `os_id (UUID)`, `rodada (INT)`, `estado (EstadoSaga)`, `subestado_compensacao (VARCHAR NULL)`, `compensacao_financeira_status (VARCHAR DEFAULT 'NAO_APLICAVEL')`, `execucao_cancelada_event_id (UUID NULL)`, `efeitos_esperados_json (JSONB)`, `efeitos_confirmados_json (JSONB)`, `version (INT)`, `deadline_at (TIMESTAMPTZ NULL)`, `ultimo_erro (TEXT NULL)`, `criada_em`, `atualizada_em`. Constraint parcial garantindo apenas uma Saga ativa por `os_id`.
- **`saga_steps`**: `id (UUID PK)`, `saga_id (FK saga_instances)`, `etapa`, `comando_event_id (UUID UNIQUE)`, `comando_tipo`, `resposta_event_id (UUID NULL)`, `resposta_tipo (VARCHAR NULL)`, `status (PENDENTE/CONCLUIDO/FALHOU/COMPENSADO)`, `tentativas (INT)`, `criado_em`, `atualizado_em`.
- **`inbox_eventos` / `outbox_eventos`**: controle transacional de mensagens Pub/Sub.

### 3.2. Billing Service (`oficina-billing` · PostgreSQL `oficina_billing_{env}`)
- **`orcamentos`**: `id (UUID PK)`, `os_id (UUID)`, `saga_id (UUID)`, `cliente_id (UUID)`, `rodada (INT)`, `versao (INT)`, `status (GERADO/APROVADO/RECUSADO/CANCELADO)`, `total_centavos (BIGINT)`, `moeda (VARCHAR(3) DEFAULT 'BRL')`, `motivo_decisao (TEXT NULL)`, `decidido_em (TIMESTAMPTZ NULL)`, `criado_em`, `atualizado_em`. Unique `(os_id, rodada, versao)`.
- **`orcamento_itens`**: `id (UUID PK)`, `orcamento_id (FK orcamentos)`, `tipo (SERVICO/PECA)`, `referencia_id (UUID)`, `descricao`, `quantidade (INT)`, `preco_unitario_centavos (BIGINT)`, `subtotal_centavos (BIGINT)`.
- **`pagamentos`**: `id (UUID PK)`, `orcamento_id (FK orcamentos)`, `os_id (UUID)`, `saga_id (UUID)`, `rodada (INT)`, `provider_order_id (VARCHAR UNIQUE NULL)`, `qr_data (TEXT NULL)`, `status (PENDENTE/CONFIRMADO/RECUSADO/CANCELADO/ESTORNADO/ESTORNO_PENDENTE/ESTORNO_FALHOU)`, `total_centavos (BIGINT)`, `moeda (VARCHAR(3))`, `criado_em`, `atualizado_em`.
- **`provider_operations`**: `id (UUID PK)`, `pagamento_id (UUID NULL)`, `saga_id (UUID)`, `idempotency_key (VARCHAR UNIQUE)`, `tipo (CREATE_ORDER/CANCEL_ORDER/REFUND_ORDER)`, `estado (PENDENTE/SUCESSO/FALHA_TRANSITORIA/FALHA_DEFINITIVA)`, `request_hash (VARCHAR)`, `provider_id (VARCHAR NULL)`, `response_json (JSONB NULL)`, `criado_em`, `atualizado_em`.
- **`saga_tombstones`**: `saga_id (UUID PK)`, `os_id (UUID)`, `rodada (INT)`, `motivo (VARCHAR)`, `criado_em`. Impede `GerarOrcamento` ou `CriarCobranca` tardios após cancelamento.
- **`webhook_inbox`**, **`inbox_eventos`**, **`outbox_eventos`**.

### 3.3. Execução Service (`oficina-execucao` · Firestore `oficina-execucao-{env}`)
- **`servicos/{servico_id}`**: `{id, nome, descricao, preco_base_centavos, tempo_estimado_minutos, ativo}`.
- **`pecas/{peca_id}`**: `{id, codigo, nome, descricao, preco_unitario_centavos, quantidade_disponivel, quantidade_reservada, estoque_minimo, ativo, updated_at}`.
- **`controle_saga/{saga_id}`**: `{saga_id, os_id, rodada, estado_controle (ATIVO | EM_FILA | REPARO_INICIADO | CONCLUIDO | CANCELADO_TOMBSTONE), cancelado_em, cancelamento_event_id, iniciado_em, version}`. Documento âncora disputado transacionalmente por `diagnosticar`, `enfileirar`, `iniciar_reparo` e `CancelarExecucao.v1`.
- **`diagnosticos/{os_id}_{rodada}`**: `{id, os_id, saga_id, rodada, laudo, itens_servico: [...], itens_peca: [...], status, concluido_em}`.
- **`reservas/{saga_id}`**: `{saga_id, os_id, rodada, status (ATIVA | CONSUMIDA | LIBERADA), itens: [{peca_id, quantidade, preco_unitario_centavos}], criada_em, atualizada_em}`.
- **`execucoes/{os_id}_{rodada}`**: `{id, os_id, saga_id, rodada, status (AGUARDANDO_EXECUCAO | EM_EXECUCAO | CONCLUIDA | CANCELADA), tarefas: [...], iniciada_em, concluida_em}`.
- **`inbox/{consumer}_{event_id}`** e **`outbox/{event_id}`**.

---

## 4. Máquina de Estados Públicos da OS (`StatusOS`) e Estados da Saga (`EstadoSaga`)

### 4.1. Evolução de `StatusOS` e Prioridade de Listagem
- Valores de `StatusOS`:
  1. `RECEBIDA`
  2. `EM_DIAGNOSTICO`
  3. `AGUARDANDO_ORCAMENTO`
  4. `AGUARDANDO_APROVACAO`
  5. `AGUARDANDO_PAGAMENTO` *(novo na Fase 4)*
  6. `AGUARDANDO_EXECUCAO` *(novo na Fase 4)*
  7. `EM_EXECUCAO`
  8. `SERVICOS_CONCLUIDOS`
  9. `COMPENSACAO_PENDENTE` *(novo na Fase 4 — visível em consulta administrativa fora da fila normal)*
  10. `FINALIZADA` *(terminal)*
  11. `ENTREGUE` *(terminal)*
  12. `CANCELADA` *(terminal)*

- Ordem de prioridade na listagem operacional (`GET /v1/ordens-servico`):
  `EM_EXECUCAO` (1) → `AGUARDANDO_EXECUCAO` (2) → `AGUARDANDO_PAGAMENTO` (3) → `AGUARDANDO_APROVACAO` (4) → `AGUARDANDO_ORCAMENTO` / `EM_DIAGNOSTICO` (5) → `RECEBIDA` (6), desempatando por `criada_em ASC`.
  Excluídas da fila operacional padrão: `FINALIZADA`, `ENTREGUE`, `CANCELADA` e `COMPENSACAO_PENDENTE`.
