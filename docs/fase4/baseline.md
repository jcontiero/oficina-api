# Fase 4 · Relatório de Baseline, Governança, Secrets e Propriedade de States (Etapa P0)

Data da auditoria e execução da P0: **16 de novembro de 2026**  
**Status da Etapa P0:** **PARCIALMENTE CONCLUÍDA** *(código, testes $\ge 80\%$, SonarCloud aprovado nos 4 PRs, inventário de states/referências GCP, governança GitHub e atualização de identidades de Workload Identity concluídos; pendentes: merge dos 4 PRs, bootstrap/verificação de state no novo projeto GCP `fiap-project-514922`, secrets de ambiente `DB_URL`/`DATADOG_API_KEY` e validação operacional em runtime do Datadog e do isolamento entre ambientes).*

---

## 1. Situação das Branches, Pull Requests da P0 e Evidências de Qualidade / SonarCloud

Todos os quatro checkouts locais foram hidratados, alinhados à `origin/main` e tiveram seus Pull Requests da Etapa P0 submetidos e validados. Após a configuração do secret `SONAR_TOKEN`, todos os workflows de CI e análises do **SonarCloud** passaram com **100% de sucesso**:

| Repositório | `origin/main` Base | Branch / Pull Request P0 | Checks de CI / Validação | SonarQube Action Run ID | SonarCloud Quality Gate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `oficina-api` | `ec15d62` | `chore/p0-baseline-ci-and-isolation` ([PR #12](https://github.com/jcontiero/oficina-api/pull/12)) | `CI/CD Pipeline/validate` **Aprovado** (186 testes, **85.53%** cobertura) | Run [`43998290784`](https://github.com/jcontiero/oficina-api/actions/runs/43998290784) (**Aprovado**) | `SonarCloud Code Analysis` **Aprovado** |
| `oficina-k8s-infra` | `1ef3602` | `chore/p0-datadog-and-state-ownership` ([PR #6](https://github.com/jcontiero/oficina-k8s-infra/pull/6)) | `Terraform CI/validate` **Aprovado** | Run [`43997761614`](https://github.com/jcontiero/oficina-k8s-infra/actions/runs/43997761614) (**Aprovado**) | `SonarCloud Code Analysis` **Aprovado** |
| `oficina-database-infra` | `a33bce9` | `chore/p0-state-ownership-and-readme` ([PR #5](https://github.com/jcontiero/oficina-database-infra/pull/5)) | `Terraform CI/validate` **Aprovado** | Run [`43997779443`](https://github.com/jcontiero/oficina-database-infra/actions/runs/43997779443) (**Aprovado**) | `SonarCloud Code Analysis` **Aprovado** |
| `oficina-serverless` | `1d45fec` | `chore/p0-env-parameterization-and-ci` ([PR #5](https://github.com/jcontiero/oficina-serverless/pull/5)) | `CI/lint-test` **Aprovado** (23 testes, **97.20%** cobertura + `terraform validate`) | Run [`43997770613`](https://github.com/jcontiero/oficina-serverless/actions/runs/43997770613) (**Aprovado**) | `SonarCloud Code Analysis` **Aprovado** |

> **Nota sobre a falha inicial do SonarCloud (resolvida):** Na primeira execução dos PRs, o scanner havia retornado `HTTP 403 Forbidden` em `GET https://api.sonarcloud.io/analysis/jres` por falha de permissão/autorização do token anterior. Com a atualização do `SONAR_TOKEN` em `2026-11-17T02:03Z–02:04Z`, a reexecução aprovou todos os quatro repositórios.

---

## 2. Auditoria de Nomes e Escopo dos Secrets no GitHub (Sem Valores)

Inspeção realizada via GitHub API (`repos/jcontiero/{repo}/actions/secrets` e `repos/jcontiero/{repo}/environments/{env}/secrets`), registrando exclusivamente os nomes, escopos e datas de atualização:

| Repositório | Escopo | Nome do Secret | Última Atualização (UTC) | Observação de Isolamento |
| :--- | :--- | :--- | :--- | :--- |
| `oficina-api` | Repositório | `SONAR_TOKEN` | `2026-11-17T02:03:35Z` | Utilizado pelo workflow `Build` (`SonarQube`). |
| `oficina-api` | Repositório | `DB_URL` | `2026-09-15T17:42:15Z` | Segredo global legado; deve ser sobrescrito nos Environments `homolog` e `production` antes de liberar deploy. |
| `oficina-api` | Repositório | `DB_PASSWORD` | `2026-09-15T17:42:07Z` | Segredo global legado. |
| `oficina-api` | Environment `homolog` | *(nenhum secret específico)* | — | **Pendente:** cadastrar `DB_URL` de homologação antes de liberar deploy. |
| `oficina-api` | Environment `production` | *(nenhum secret específico)* | — | **Pendente:** cadastrar `DB_URL` de produção antes de liberar deploy. |
| `oficina-k8s-infra` | Repositório | `SONAR_TOKEN` | `2026-11-17T02:04:01Z` | Utilizado pelo workflow `Build` (`SonarQube`). |
| `oficina-k8s-infra` | Environments `homolog` / `production` | *(nenhum secret específico)* | — | **Pendente:** cadastrar `DATADOG_API_KEY` antes do `terraform apply` do Agent. |
| `oficina-database-infra` | Repositório | `SONAR_TOKEN` | `2026-11-17T02:04:55Z` | Utilizado pelo workflow `Build` (`SonarQube`). |
| `oficina-database-infra` | Environments `homolog` / `production` | *(nenhum secret específico)* | — | Autenticação via OIDC Workload Identity. |
| `oficina-serverless` | Repositório | `SONAR_TOKEN` | `2026-11-17T02:04:20Z` | Utilizado pelo workflow `Build` (`SonarQube`). |
| `oficina-serverless` | Environments `homolog` / `production` | *(nenhum secret específico)* | — | Autenticação via OIDC Workload Identity; funções leem `DATABASE_URL` do GCP Secret Manager (`database-url-homolog` / `database-url-prod`). |

---

## 3. Verificação do Novo Projeto GCP (`fiap-project-514922`), Recursos Existentes e Inventário de Referências a `pos-fiap-2026`

### 3.1. Dados Reais do Novo Projeto GCP e Inspeção Read-Only de Recursos

Consultas somente-leitura (`gcloud projects list`, `storage buckets list`, `iam service-accounts list`, `iam workload-identity-pools list`, `services list --enabled`, `container clusters list`, `sql instances list`) executadas com a conta autenticada `jonascv@gmail.com`:

- **Project ID:** `fiap-project-514922`
- **Project Name:** `fiap-project`
- **Project Number:** `936717667971` *(substitui o número `1064199753061` do projeto anterior `pos-fiap-2026`)*
- **Identidade esperada da Service Account de CI/CD:** `github-actions-sa@fiap-project-514922.iam.gserviceaccount.com`
- **Identidade esperada do Workload Identity Provider:** `projects/936717667971/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider`
- **Recursos atualmente existentes em `fiap-project-514922` (nenhum recurso foi provisionado):**
  - **Buckets GCS (`storage buckets list`):** `[]` (nenhum bucket existente no novo projeto).
  - **Service Accounts (`iam service-accounts list`):** `[]` (nenhuma Service Account customizada criada ainda).
  - **Workload Identity Pools (`iam workload-identity-pools list`):** `[]` (nenhum pool OIDC criado ainda).
  - **Clusters GKE / Instâncias Cloud SQL:** APIs `container.googleapis.com` e `sqladmin.googleapis.com` ainda desabilitadas (`SERVICE_DISABLED`); apenas as APIs padrão do projeto (`storage`, `datastore`, `logging`, `monitoring`, `bigquery`, `servicemanagement`, `serviceusage`) estão ativas.

### 3.2. Onde Estão os States Terraform e Regra de Não Substituição Global

1. **States Remotos (`backend.tf`):**
   - Os arquivos `oficina-k8s-infra/infra/backend.tf`, `oficina-database-infra/terraform/backend.tf` e `oficina-serverless/terraform/backend.tf` configuram `bucket = "pos-fiap-2026-tf-state"`, que residia no projeto anterior `pos-fiap-2026` (atualmente inacessível via CLI local com `403 Permission denied`).
   - Como **nenhum recurso deve ser provisionado na GCP neste momento** e o bucket de state pode permanecer no projeto anterior ou exigir migração/bootstrap explícito, **os arquivos `backend.tf` NÃO foram alterados**.
2. **State Local de Bootstrap (`oficina-k8s-infra/bootstrap/terraform.tfstate` e `.backup`):**
   - Registra os recursos criados em 14/09/2026 no projeto anterior `pos-fiap-2026` (`project_number: 1064199753061`). **Preservado integralmente sem edição manual** como registro histórico de state.

### 3.3. Inventário Completo das Referências a `pos-fiap-2026` / `1064199753061` nos Quatro Repositórios

| Repositório / Arquivo | Tipo de Referência | Decisão Aplicada na P0 |
| :--- | :--- | :--- |
| `oficina-api/.github/workflows/deploy.yml` | `PROJECT_ID`, `workload_identity_provider` (`1064199753061`) e `service_account` | **Atualizado** para `fiap-project-514922`, `936717667971` e `github-actions-sa@fiap-project-514922.iam.gserviceaccount.com`. |
| `oficina-api/k8s/{deployment,deployment-worker,job-migrate}.yaml` | URI da imagem no Artifact Registry (`us-east1-docker.pkg.dev/...`) | **Atualizado** para `us-east1-docker.pkg.dev/fiap-project-514922/oficina-docker/oficina-api:latest`. |
| `oficina-api/src/worker.py` e `README.md` | Default de `GCP_PROJECT_ID` | **Atualizado** para `fiap-project-514922`. |
| `oficina-api/docs/diagramas/diagrama-componentes.md` | Rótulo histórico de diagrama da Fase 3 | **Preservado** como documentação histórica da Fase 3. |
| `oficina-k8s-infra/.github/workflows/deploy.yml` | `workload_identity_provider` (`1064199753061`) e `service_account` | **Atualizado** para `936717667971` e `github-actions-sa@fiap-project-514922.iam.gserviceaccount.com`. |
| `oficina-k8s-infra/bootstrap/{variables.tf,terraform.tfvars}` | `project_id` alvo do bootstrap | **Atualizado** para `fiap-project-514922` (sem executar `terraform apply`). |
| `oficina-k8s-infra/infra/variables.tf` e `infra/environments/{homolog,main}.tfvars` | `project_id` alvo dos módulos VPC/GKE/AR | **Atualizado** para `fiap-project-514922`. |
| `oficina-k8s-infra/infra/backend.tf` | `bucket = "pos-fiap-2026-tf-state"` | **Preservado (não substituído):** aguarda definição/provisionamento do bucket de state. |
| `oficina-k8s-infra/bootstrap/terraform.tfstate*` | State local do bootstrap antigo (`pos-fiap-2026` / `1064199753061`) | **Preservado (não substituído):** arquivo de estado do Terraform não deve sofrer substituição textual. |
| `oficina-database-infra/.github/workflows/deploy.yml` | `workload_identity_provider` (`1064199753061`) e `service_account` | **Atualizado** para `936717667971` e `github-actions-sa@fiap-project-514922.iam.gserviceaccount.com`. |
| `oficina-database-infra/terraform/variables.tf` e `environments/{homolog,main}.tfvars` | `project_id` alvo do Cloud SQL e Secrets | **Atualizado** para `fiap-project-514922`. |
| `oficina-database-infra/terraform/backend.tf` | `bucket = "pos-fiap-2026-tf-state"` | **Preservado (não substituído):** aguarda definição/provisionamento do bucket de state. |
| `oficina-serverless/.github/workflows/deploy.yml` | `workload_identity_provider` (`1064199753061`) e `service_account` | **Atualizado** para `936717667971` e `github-actions-sa@fiap-project-514922.iam.gserviceaccount.com`. |
| `oficina-serverless/terraform/variables.tf` e `environments/{homolog,main}.tfvars` | `project_id` alvo das Functions/PubSub/Gateway | **Atualizado** para `fiap-project-514922`. |
| `oficina-serverless/terraform/backend.tf` | `bucket = "pos-fiap-2026-tf-state"` | **Preservado (não substituído):** aguarda definição/provisionamento do bucket de state. |

---

## 4. Propriedade dos States Terraform (`recurso → state → repositório`)

| Recurso GCP / K8s | Repositório Dono | Backend GCS (`prefix`) | Workspace Terraform | Regra de Provisionamento (`homolog` vs `main`) |
| :--- | :--- | :--- | :--- | :--- |
| APIs GCP, Bucket de State, Workload Identity Pool (`github-actions-pool`), SA `github-actions-sa` | `oficina-k8s-infra` (`bootstrap/`) | State local (`bootstrap/terraform.tfstate`) | `default` | Executado apenas sob autorização explícita do usuário. `attribute.repository` permite uso de GitHub Environments sem quebrar o subject OIDC. |
| VPC `oficina-vpc`, Subnets GKE/Serverless, VPC Connector `oficina-connector`, Private Service Access | `oficina-k8s-infra` (`infra/`) | `env/shared/k8s-infra` | `main` (único) | **Plataforma compartilhada:** `homolog` executa apenas `terraform plan` sobre o workspace `main`; `apply` exclusivo na `main` (`environment: production`). |
| Cluster GKE Standard `oficina-gke-cluster` + Node Pool `oficina-gke-cluster-node-pool` | `oficina-k8s-infra` (`infra/`) | `env/shared/k8s-infra` | `main` (único) | **Plataforma compartilhada:** `homolog` e `production` são isolados por **Namespaces K8s** no mesmo cluster. |
| Artifact Registry `oficina-docker` | `oficina-k8s-infra` (`infra/`) | `env/shared/k8s-infra` | `main` (único) | Repositório de imagens compartilhado; imagens são imutáveis por tag `${GITHUB_SHA}`. |
| Helm Release `datadog` (Datadog Agent DaemonSet no namespace `datadog`) | `oficina-k8s-infra` (`infra/`) | `env/shared/k8s-infra` | `main` (único) | Reativado na P0 em `infra/main.tf` com `datadog_site = "us5.datadoghq.com"` e `TF_VAR_datadog_api_key` via GitHub Secrets. |
| Instância Cloud SQL `oficina-postgres-db`, Databases `oficina_homolog` e `oficina_prod`, Usuário `oficina_user` | `oficina-database-infra` (`terraform/`) | `env/shared/database-infra` | `main` (único) | **Plataforma compartilhada:** instância única. `homolog` executa apenas `terraform plan` no workspace `main`; `apply` exclusivo na `main`. |
| Secrets `database-url-homolog`, `database-url-prod`, `database-password` | `oficina-database-infra` (`terraform/`) | `env/shared/database-infra` | `main` (único) | Criados com nomes distintos por ambiente no mesmo state da instância SQL. |
| Pub/Sub (`oficina-notificacoes-topic*`), Bucket de código, Cloud Functions v2 (`oficina-auth-function*`, `oficina-notificacoes-function*`), API Gateway (`oficina-api-gateway*`) | `oficina-serverless` (`terraform/`) | `env/shared/serverless` | `main` (prod) e `homolog` (homolog) | **Parametrizado por ambiente na P0:** workspace `main` preserva nomes legados (`env_suffix = ""`, secret `database-url-prod`); workspace `homolog` aplica sufixo `-homolog` em todos os recursos e usa `database-url-homolog`. |

---

## 5. Dimensionamento do GKE (Estimativa Estática Ainda Não Validada em Runtime)

> **Importante:** Como nenhum cluster GKE está ativo em `fiap-project-514922` neste momento, os números abaixo constituem uma **estimativa estática baseada nos manifestos locais**, **ainda não validada em cluster real**. Não foi realizado aumento especulativo da infraestrutura GKE.

| Workload | Réplicas (por env) | CPU Request (soma) | Memory Request (soma) | CPU Limit (soma) | Memory Limit (soma) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `Deployment/oficina-api` | 2 (`minReplicas: 2` no HPA) | `200m` (`2 × 100m`) | `256Mi` (`2 × 128Mi`) | `1000m` (`2 × 500m`) | `1024Mi` (`2 × 512Mi`) |
| `Deployment/oficina-api-worker` | 1 | `50m` (`1 × 50m`) | `64Mi` (`1 × 64Mi`) | `200m` (`1 × 200m`) | `128Mi` (`1 × 128Mi`) |
| **Subtotal declarado por ambiente (`homolog` ou `production`)** | **3 pods fixos** | **`250m` CPU** | **`320Mi` RAM** | **`1200m` CPU** | **`1152Mi` RAM** |
| **Total declarado para 2 ambientes (`homolog` + `production`)** | **6 pods fixos** | **`500m` CPU** | **`640Mi` RAM** | **`2400m` CPU** | **`2304Mi` RAM** |
| `Job/oficina-api-migrate` *(transitório no deploy, `ttlSecondsAfterFinished: 300`)* | 1 durante migration | `100m` CPU | `128Mi` RAM | `300m` CPU | `256Mi` RAM |
| `DaemonSet/datadog` *(sem requests explícitos em `modules/datadog/main.tf`)* | 1 por nó | *Não medido em runtime* (estimado ~`150m–200m`) | *Não medido em runtime* (estimado ~`256Mi–512Mi`) | *Sem limite explícito no módulo* | *Sem limite explícito no módulo* |

---

## 6. Pendências da Etapa P0 (Mantidas com Deploys Bloqueados)

1. **Merge dos 4 PRs da P0 (`oficina-api#12`, `oficina-k8s-infra#6`, `oficina-database-infra#5`, `oficina-serverless#5`):**
   - Todos os checks obrigatórios (`validate`/`lint-test`, `Build/SonarQube` e `SonarCloud Code Analysis`) estão **verdes**. Os deploys permanecem bloqueados por `workflow_dispatch` (`confirm_cloud_apply == 'true'` / `confirm_deploy == 'true'`), garantindo que o merge dos PRs **não provisionará nada na GCP**.
2. **Definição do Bucket de State e Bootstrap no Projeto `fiap-project-514922` (somente quando autorizado):**
   - Decidir se o state permanecerá em bucket existente ou se será executado o `bootstrap/` em `fiap-project-514922` (quando autorizado pelo usuário) para criar o Workload Identity Pool, a Service Account `github-actions-sa@fiap-project-514922.iam.gserviceaccount.com` e o bucket de state, atualizando então `backend.tf`.
3. **Secrets por GitHub Environment (`homolog` e `production`) e Validação Operacional em Runtime:**
   - Cadastrar `DB_URL` nos Environments `homolog` e `production` de `oficina-api` e `DATADOG_API_KEY` em `oficina-k8s-infra` antes de autorizar deploys na Etapa P7.
   - Validar em runtime na Etapa P7 o Datadog Agent, o isolamento efetivo entre `homolog` e `production`, a medição real dos nós do GKE (`kubectl describe nodes`) e **remover o bloqueio temporário de deploy manual (`workflow_dispatch`) antes do aceite final de CI/CD**.
