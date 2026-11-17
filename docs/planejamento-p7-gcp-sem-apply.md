# Planejamento de Provisionamento e Go-Live — Etapa P7 (`fiap-project-514922`)

> **Status:** Planejamento revisado sem execução de `bootstrap`, `terraform apply` ou migração de state. Deploys permanecem bloqueados por `workflow_dispatch` (`confirm_deploy == 'true'`).
> **Pendências preservadas:**
> - **P5 (Mercado Pago externo):** aceite externo pendente por ausência de credenciais de teste (`MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`) e URL HTTPS pública para webhook.
> - **P6 (parcialmente concluída):** `oficina-api` (#17, #18) e `bdd-integrado` aprovados no CI; Quality Gates de `oficina-billing#4` e `oficina-execucao#4` bloqueados até importação dos projetos no SonarCloud (`Execute Analysis`) e atualização de `SONAR_TOKEN` válido nos dois repositórios.

---

## 1. Princípio de Posse Única e Desenho dos States Terraform

Nenhum recurso de nuvem pode ser gerenciado por mais de um state Terraform. Recursos compartilhados possuem **um único state dono**, enquanto recursos exclusivos de cada domínio/ambiente ficam isolados em states próprios por serviço e ambiente. Os states históricos do projeto anterior permanecem intactos e isolados, sem reutilização nem sobrescrita.

### 1.1 Backend Novo

- **Bucket:** `gs://fiap-project-514922-tfstate` (versionamento habilitado, `uniform_bucket_level_access = true`, `prevent_destroy = true`).
- **Organização de prefixos:**
  - `bootstrap/` — APIs base do projeto, bucket de state e Workload Identity Federation.
  - `platform/network-gke/` — VPC, subnets, Cloud NAT, Private Service Access, GKE, Artifact Registry (`oficina-docker`) e base do Datadog Agent.
  - `platform/cloudsql/` — instância Cloud SQL PostgreSQL compartilhada (sem bancos lógicos de serviço).
  - `services/oficina-api/{homolog,prod}/` — banco lógico `oficina_os_{env}`, usuário, tópicos/subscriptions da Saga, segredos e IAM do OS Service.
  - `services/oficina-billing/{homolog,prod}/` — banco lógico `oficina_billing_{env}`, usuário, subscriptions, segredos do Billing/Mercado Pago e IAM do Billing Service.
  - `services/oficina-execucao/{homolog,prod}/` — banco Firestore Native nomeado `oficina-execucao-{env}`, subscriptions, segredos e IAM do Execução Service.

---

## 2. Matriz Recurso → Repositório → State → Ambiente

| Recurso | Repositório Dono | State (`gs://fiap-project-514922-tfstate/...`) | Ambiente |
|---|---|---|---|
| APIs GCP, Bucket TFState, Workload Identity Pool/Provider, `github-actions-sa` | `oficina-api` (infra/bootstrap) | `bootstrap/` | Projeto (Global) |
| VPC, Subnets, Cloud NAT, Private Service Access | `oficina-api` (infra/platform) | `platform/network-gke/` | Compartilhado |
| Artifact Registry (`oficina-docker`, `us-east1`) | `oficina-api` (infra/platform) | `platform/network-gke/` | Compartilhado |
| Cluster GKE e Datadog Agent (DaemonSet/Cluster Agent) | `oficina-api` (infra/platform) | `platform/network-gke/` | Compartilhado |
| Instância Cloud SQL PostgreSQL 16 (privada) | `oficina-api` (infra/platform) | `platform/cloudsql/` | Compartilhado |
| Database lógico `oficina_os_{env}`, usuário SQL, IAM OS, Tópicos/Subs Saga | `oficina-api` | `services/oficina-api/{homolog,prod}/` | `homolog` / `prod` |
| Secret Manager OS (`SECRET_KEY`, `JWT_PRIVATE_KEY_PEM`, `DD_API_KEY`) | `oficina-api` | `services/oficina-api/{homolog,prod}/` | `homolog` / `prod` |
| Database lógico `oficina_billing_{env}`, usuário SQL, IAM Billing, Subs Billing | `oficina-billing` | `services/oficina-billing/{homolog,prod}/` | `homolog` / `prod` |
| Secret Manager Billing (`MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`, `DD_API_KEY`) | `oficina-billing` | `services/oficina-billing/{homolog,prod}/` | `homolog` / `prod` |
| Firestore Native (`oficina-execucao-{env}`), IAM Execução, Subs Execução | `oficina-execucao` | `services/oficina-execucao/{homolog,prod}/` | `homolog` / `prod` |

---

## 3. Criação do Bucket de Backend e Transferência Controlada do State de Bootstrap

O bucket `gs://fiap-project-514922-tfstate` precisa existir **antes** do `terraform init` de qualquer stack de plataforma ou serviço. O bootstrap segue uma sequência em duas etapas para evitar dependência circular:

1. **Etapa A — Bootstrap inicial com state local temporário:**
   - O módulo `bootstrap/` inicia sem bloco `backend "gcs"` (usando state local temporário).
   - Executa-se `terraform init`, `terraform plan -out=bootstrap.tfplan` e, após revisão, `terraform apply bootstrap.tfplan`, criando o bucket `gs://fiap-project-514922-tfstate`, as APIs base e o Workload Identity.
2. **Etapa B — Transferência controlada para o backend remoto:**
   - Habilita-se o bloco `backend "gcs" { bucket = "fiap-project-514922-tfstate", prefix = "bootstrap" }` no `bootstrap/`.
   - Executa-se `terraform init -migrate-state`, confirmando a cópia do state local para `gs://fiap-project-514922-tfstate/bootstrap/default.tfstate`.
   - Valida-se com `terraform state list` e `terraform plan` (esperado: `No changes`) antes de arquivar/remover o arquivo local temporário.
3. **Etapa C — Demais stacks:**
   - Somente após a Etapa B concluída, `platform/network-gke/`, `platform/cloudsql/` e `services/*` executam `terraform init` diretamente apontando para `gs://fiap-project-514922-tfstate`.

---

## 4. Ordem de Execução (IAM/WIF, Infraestrutura e Deploy)

1. **Bootstrap e WIF (`bootstrap/`):** criação do bucket de state, APIs e vínculo OIDC para `github-actions-sa@fiap-project-514922.iam.gserviceaccount.com`.
2. **Plataforma (`platform/network-gke/` $\rightarrow$ `platform/cloudsql/`):** rede, Artifact Registry, GKE/Datadog e instância Cloud SQL.
3. **Serviços por ambiente (`homolog` antes de `prod`):** `services/oficina-api/homolog/`, `services/oficina-billing/homolog/`, `services/oficina-execucao/homolog/` (referenciando a plataforma via `terraform_remote_state` ou `data` sources, sem gerenciá-la).
4. **Secrets e Migrations:** preenchimento do Secret Manager e execução de `job-migrate.yaml` (`alembic upgrade head` no OS e no Billing) antes do rollout.
5. **Deploy de Workloads (`confirm_deploy=true`):** rollout das 3 APIs, 3 workers e validação de `/health/ready` + correlação Datadog.

---

## 5. Estimativa de Custo e Plano de Capacidade

> **Distinção obrigatória:** não há recursos provisionados em `fiap-project-514922`; portanto, **nenhum valor abaixo foi verificado em fatura/billing real**. Todos os números são estimativas preliminares para `us-east1` em ambiente `homolog` contínuo.

| Componente | Dimensionamento Estimado (`homolog`) | Estimativa Mensal (USD, não verificada) | Valor Verificado em Fatura |
|---|---|---|---|
| GKE (Autopilot ou 2–3 nós `e2-medium`) | 6 pods API + 3 pods worker + Datadog Agent | ~$70 – $140 | Não verificado (pré-provisionamento) |
| Cloud SQL PostgreSQL 16 | 1 instância (`db-f1-micro` / `db-custom-1-3840`) | ~$15 – $55 | Não verificado (pré-provisionamento) |
| Firestore Native + Pub/Sub + Artifact Registry + Secret Manager + GCS TFState | Baixo volume transacional | ~$1 – $10 | Não verificado (pré-provisionamento) |
| **Total estimado (`homolog`)** | — | **~$86 – $205 / mês** | **Não verificado** |

---

## 6. Configuração de Ambientes, Secrets, Datadog, Planos Revisáveis e Rollback

- **Ambientes e Isolamento:** `ENVIRONMENT=homolog|production`, `GCP_PROJECT_ID=fiap-project-514922`, `FIRESTORE_DATABASE=oficina-execucao-{env}`, `ENABLE_LEGACY_MONOLITH_DOMAINS=false`.
- **Secrets:** `DATABASE_URL` por serviço, `DD_API_KEY`, `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET` e `JWT_PRIVATE_KEY_PEM` (exclusivo do OS).
- **Datadog:** `DD_TRACE_ENABLED=true`, `DD_ENV={env}`, `DD_VERSION={git_sha}`, `DD_AGENT_HOST` apontando para o Agent no cluster, mantendo logs JSON estruturados (`dd.trace_id`, `dd.span_id`, `correlation_id`, `saga_id`, `os_id`).
- **Planos Terraform revisáveis:** todo PR executa `terraform fmt -check`, `terraform validate` e `terraform plan -no-color` para revisão antes de qualquer `apply`.
- **Rollback:**
  - **Aplicação:** `kubectl rollout undo deployment/<servico> -n <namespace>` com imagem imutável por SHA.
  - **Banco relacional:** migrations aditivas compatíveis com a versão anterior; em falha grave, restauração via snapshot/PITR do Cloud SQL.
  - **Mensageria:** pausa dos workers, inspeção de DLQs e `outbox_eventos`/`inbox_eventos`, correção e reprocessamento idempotente.
