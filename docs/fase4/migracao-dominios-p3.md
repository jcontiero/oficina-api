# Fase 4 · Etapa P3 — Extração de Domínios, Autenticação RS256 e Consulta Interna

Este documento registra a extração dos domínios realizada na Etapa P3, garantindo **um único serviço escritor por domínio**, ausência de acesso cruzado a bancos de dados e preservação dos contratos externos.

---

## 1. Matriz de Propriedade de Escrita por Domínio

| Domínio / Dados | Serviço Dono (Único Escritor) | Persistência Exclusiva | Observação de Desacoplamento |
| :--- | :--- | :--- | :--- |
| **Clientes, Veículos, Usuários, OS e Histórico** | `oficina-api` (OS Service) | PostgreSQL `oficina_os_{env}` | Expõe `POST /v1/ordens-servico` (`202 Accepted` + `saga_id` + `Location`), `GET /.well-known/admin-jwks.json` e `POST /internal/clientes/autenticacao`. |
| **Orçamentos Versionados e Pagamentos (MP QR)** | `oficina-billing` (Billing Service) | PostgreSQL `oficina_billing_{env}` | Único escritor de `orcamentos`, `orcamento_itens`, `pagamentos`, `provider_operations`, `webhook_inbox` e `saga_tombstones`. |
| **Catálogo de Serviços, Estoque, Diagnóstico e Execução** | `oficina-execucao` (Execução Service) | Firestore `oficina-execucao-{env}` | Único escritor de `servicos`, `pecas`, `diagnosticos`, `reservas`, `execucoes` e `controle_saga`. |
| **Autenticação CPF / JWKS Cliente** | `oficina-serverless` (`auth_function`) | *(stateless — sem banco)* | `DATABASE_URL` e `psycopg` removidos. Consulta `POST /internal/clientes/autenticacao` com Google OIDC ID Token. |

---

## 2. Desativação de Escritas Legadas no OS Service (`ENABLE_LEGACY_MONOLITH_DOMAINS`)

- Em `oficina-api/src/main.py`, os routers legados de Catálogo (`/servicos`) e Estoque (`/pecas`) são controlados pela flag `ENABLE_LEGACY_MONOLITH_DOMAINS`.
- Na stack distribuída (`integration/compose.yml`) e nos ambientes de nuvem, `ENABLE_LEGACY_MONOLITH_DOMAINS=false` garante que apenas `oficina-execucao` exponha e escreva em `/servicos*` e `/pecas*`.
- Os testes de unidade e integração de Catálogo e Estoque foram transferidos para `oficina-execucao/tests/` com preservação integral de IDs, regras de negócio, autorização (`ADMIN`) e payloads.

---

## 3. Contrato de Autenticação Distribuída (RS256 + JWKS + Google OIDC)

1. **Funcionários (`ADMIN` / `MECANICO`):** `oficina-api` migrou de `HS256` para `RS256` (`iss=oficina-admin-{env}`, `aud=oficina-backend-{env}`, `kid`), publicando a chave pública em `GET /.well-known/admin-jwks.json`.
2. **Clientes (`CLIENTE`):** `oficina-serverless` emite `RS256` (`iss=oficina-auth-{env}`, `aud=oficina-backend-{env}`, `kid`) após consultar o OS Service via `POST /internal/clientes/autenticacao` autenticado por **Google OIDC ID Token** (verificando `iss`, `aud` exata e `email` na allowlist `INTERNAL_AUTH_ALLOWED_SERVICE_ACCOUNTS`).
3. **`oficina-billing` e `oficina-execucao`:** validam ambos os emissores por chave pública/JWKS estaticamente mapeada por emissor, sem compartilhar `SECRET_KEY` simétrica.

---

## 4. Diferença entre Firestore Emulator (`(default)`) e Bancos Nomeados no GCP

- **Limitação do Firestore Emulator local:** o emulador oficial (`gcloud beta emulators firestore start`) atende exclusivamente sobre o database `(default)`.
- **GCP (`homolog` e `production`):** em ambiente gerenciado na nuvem, `GoogleFirestoreStore` conecta aos bancos nomeados exclusivos **`oficina-execucao-homolog`** e **`oficina-execucao-production`** configurados via `FIRESTORE_DATABASE`.
- Essa diferença está tratada explicitamente em `oficina-execucao/src/execucao/infraestrutura/firestore_store.py`.

---

## 5. Barreira de Cancelamento (`execucao_cancelada_event_id`) — Limite P3 vs. P4

- O campo `execucao_cancelada_event_id` presente nos payloads de `LiberarReserva.v1`, `CancelarOrcamento.v1`, `CancelarCobranca.v1` e `EstornarPagamento.v1` **não é tratado como prova autossuficiente**.
- Em `oficina-execucao` (`ControleSagaExecucao` + `ReservaEstoque`), a barreira exige estado persistido `CANCELADO_TOMBSTONE` e correspondência exata do `cancelamento_event_id`.
- Em `oficina-billing` (`SagaTombstoneBillingModel`), o tombstone da barreira é persistido na tabela `saga_tombstones` e bloqueia criação tardia (`409 Conflict`).
- A orquestração assíncrona completa via Outbox/Inbox e transações Firestore `@firestore.transactional` será concluída na **Etapa P4**.
