# Oficina Mecânica - OS Service (`oficina-api`)

[![Quality gate](https://sonarcloud.io/api/project_badges/quality_gate?project=jcontiero_oficina-api)](https://sonarcloud.io/summary/new_code?id=jcontiero_oficina-api)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=jcontiero_oficina-api&metric=coverage)](https://sonarcloud.io/summary/new_code?id=jcontiero_oficina-api)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=jcontiero_oficina-api&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=jcontiero_oficina-api)

## Propósito

Este repositório contém o serviço principal de **Ordens de Serviço (OS Service)** da Oficina Mecânica, responsável pela gestão de clientes, veículos, abertura e acompanhamento de OS, e orquestração transacional com *Unit of Work* e *Transactional Outbox*.

> Consulte a [documentação técnica](docs/README.md) para a arquitetura e os contratos.

## Tecnologias Utilizadas

- **Python 3.12+** com **FastAPI**
- **SQLAlchemy 2.0** + **Alembic**
- **PostgreSQL 16** (Cloud SQL) / SQLite (testes locais rápidos)
- **Google Cloud Pub/Sub** (mensageria assíncrona via Outbox Worker)
- **Docker** & **Kubernetes (GKE)**
- **Datadog** (APM via `ddtrace` e logs estruturados em JSON)
- **uv** (gerenciador de pacotes e ambientes)

## Pré-requisitos e Variáveis de Ambiente

| Variável | Descrição | Exemplo / Default Local |
| :--- | :--- | :--- |
| `DATABASE_URL` | URL SQLAlchemy do banco de dados | `postgresql+pg8000://user:pass@localhost:5432/oficina` |
| `SECRET_KEY` | Chave para assinatura de tokens internos (mín. 32 chars) | `default-secret-key-for-dev-and-tests-min-32-chars` |
| `JWKS_URL` | Endpoint JWKS público para validação de JWT de clientes | `https://oficina-gateway-dkvx20rp.ue.gateway.dev/.well-known/jwks.json` |
| `GCP_PROJECT_ID` | Projeto GCP para publicação no Pub/Sub | `fiap-project-514922` |
| `PUBSUB_TOPIC_ID` | Tópico Pub/Sub consumido a partir da Outbox | `oficina-notificacoes-topic` |

## Passos para Execução, Testes e Deploy

### 1. Instalação e Execução Local (a partir da raiz do repositório)

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn src.main:app --reload --port 8000
```

### 2. Testes Automatizados e Gate de Cobertura ($\ge 80\%$)

```bash
DD_TRACE_ENABLED=false \
TEST_DATABASE_URL="sqlite:////tmp/oficina_test.db" \
SECRET_KEY="ci-secret-key-para-testes-32-chars-ok" \
uv run pytest tests/unit tests/integration --cov=src --cov-report=term-missing --cov-fail-under=80
```

### 3. Deploy Automatizado e Isolamento (`homolog` vs `production`)

O pipeline `.github/workflows/deploy.yml` utiliza **GitHub Environments** (`homolog` para a branch `homolog` e `production` para a branch `main`):
1. **Validação:** `ruff check`, `black --check` e `pytest tests/unit tests/integration --cov=src --cov-fail-under=80`.
2. **Verificação de isolamento de banco antes da migration:** o workflow valida que `DB_URL` em `homolog` aponta exclusivamente para `oficina_homolog`/`oficina_os_homolog` e em `main` aponta exclusivamente para `oficina_prod`/`oficina_os_production`, abortando antes de qualquer migration caso haja divergência.
3. **Migration coordenada por SHA:** aplica `ConfigMap` e `Secret`, executa o Job `oficina-api-migrate` com a imagem `${GITHUB_SHA}` e aguarda `kubectl wait --for=condition=complete` antes de atualizar os Deployments `oficina-api` e `oficina-api-worker`.

### 4. Rollback

1. Para reverter a aplicação sem alteração destrutiva de schema:
   ```bash
   kubectl rollout undo deployment/oficina-api -n <homolog|production>
   kubectl rollout undo deployment/oficina-api-worker -n <homolog|production>
   ```
2. As migrations são sempre aditivas e compatíveis com a versão imediatamente anterior.

## Diagrama de Arquitetura

```mermaid
flowchart TD
    GW["API Gateway"] -->|HTTP + JWT| API["oficina-api Pods (GKE)"]
    API -->|Transação Local| DB[("Cloud SQL PostgreSQL\n(oficina_homolog / oficina_prod)")]
    API -->|Mesma Transação| OUTBOX[("Tabela outbox_eventos")]
    WORKER["oficina-api-worker"] -->|Lê PENDENTE| OUTBOX
    WORKER -->|Publica Eventos| PS["Cloud Pub/Sub"]
    API -.->|APM :8126 + JSON Logs| DD["Datadog Agent DaemonSet"]
    WORKER -.->|APM :8126 + JSON Logs| DD
```

## APIs e Documentação

- **Swagger UI:** `/docs`
- **Health Checks:** `/health/live` (liveness) e `/health/ready` (readiness com verificação SQL)
- **Contratos HTTP OpenAPI:** [`docs/contratos/openapi-fase4-contratos-v1.json`](docs/contratos/openapi-fase4-contratos-v1.json)

## Repositórios Relacionados

- [oficina-k8s-infra](https://github.com/jcontiero/oficina-k8s-infra) — GKE, VPC, Artifact Registry e Datadog Agent
- [oficina-database-infra](https://github.com/jcontiero/oficina-database-infra) — Cloud SQL e Secret Manager
- [oficina-serverless](https://github.com/jcontiero/oficina-serverless) — Cloud Functions (Auth / Notificações), Pub/Sub e API Gateway
