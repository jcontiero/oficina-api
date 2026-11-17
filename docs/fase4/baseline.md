# Fase 4 · Relatório de Baseline, Governança e Propriedade de States (Etapa P0)

Data da auditoria e execução da P0: **16 de novembro de 2026**  
**Status da Etapa P0:** **PARCIALMENTE CONCLUÍDA** *(trabalho local, inventário de states, governança GitHub e PRs concluídos; pendentes: correção de permissão/token do SonarCloud, merge dos 4 PRs, acesso ao projeto GCP e validação operacional em runtime do Datadog e do isolamento entre ambientes).*

---

## 1. Situação das Branches e Alinhamento dos Repositórios

Na inspeção inicial do workspace local (`/Users/jonascv/Library/Mobile Documents/com~apple~CloudDocs/jonas/pos_fiap`), três dos quatro repositórios estavam posicionados em branches secundárias locais cujos Pull Requests já haviam sido integrados em `origin/main`. Todos os quatro checkouts foram hidratados e alinhados em `main` (`git merge --ff-only origin/main`) antes da abertura das branches da Etapa P0:

| Repositório | Branch Inicial Local | Commit Inicial Local | Commit Canônico (`origin/main`) | Status do Alinhamento Local | Branch de Correção P0 / Pull Request |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `oficina-api` | `main` | `ec15d62` | `ec15d62` | Alinhado com `origin/main` | `chore/p0-baseline-ci-and-isolation` ([PR #12](https://github.com/jcontiero/oficina-api/pull/12)) |
| `oficina-k8s-infra` | `fix/terraform-datadog-module` | `7e5b312` | `1ef3602` (PR #5 mergeado) | Alinhado para `main` (`1ef3602`) | `chore/p0-datadog-and-state-ownership` ([PR #6](https://github.com/jcontiero/oficina-k8s-infra/pull/6)) |
| `oficina-database-infra` | `fix/sonar-vulnerabilities` | `a11235b` | `a33bce9` (PR #4 mergeado) | Alinhado para `main` (`a33bce9`) | `chore/p0-state-ownership-and-readme` ([PR #5](https://github.com/jcontiero/oficina-database-infra/pull/5)) |
| `oficina-serverless` | `feature/aumentar-cobertura-serverless` | `89562fa` | `1d45fec` (PR #4 mergeado) | Alinhado para `main` (`1d45fec`) | `chore/p0-env-parameterization-and-ci` ([PR #5](https://github.com/jcontiero/oficina-serverless/pull/5)) |

> **Por que a branch `homolog` não foi publicada antes dos PRs da P0:**
> Nos workflows originais (`deploy.yml`), um push para `homolog` em `oficina-k8s-infra` e `oficina-database-infra` executava `terraform workspace select homolog || terraform workspace new homolog` seguido de `terraform apply`, o que tentaria recriar a VPC, o cluster GKE e a instância Cloud SQL em um segundo state. A branch `homolog` deve ser criada a partir de `main` **somente após** o merge dos PRs da P0 que blindam os states compartilhados e a verificação de banco no deploy.

---

## 2. Propriedade dos States Terraform (`recurso → state → repositório`)

Todos os states remotos residem no bucket GCS `gs://pos-fiap-2026-tf-state` (criado pelo módulo `oficina-k8s-infra/bootstrap`). A tabela abaixo formaliza o dono único de cada recurso para impedir conflito de states entre `homolog` e `production`:

| Recurso GCP / K8s | Repositório Dono | Backend GCS (`prefix`) | Workspace Terraform | Regra de Provisionamento (`homolog` vs `main`) |
| :--- | :--- | :--- | :--- | :--- |
| APIs GCP, Bucket `pos-fiap-2026-tf-state`, Workload Identity Pool (`github-actions-pool`), SA `github-actions-sa` | `oficina-k8s-infra` (`bootstrap/`) | State local (`bootstrap/terraform.tfstate`) | `default` | Executado apenas em mudanças de bootstrap da conta GCP. `attribute.repository` permite uso de GitHub Environments sem quebrar o subject OIDC. |
| VPC `oficina-vpc`, Subnets GKE/Serverless, VPC Connector `oficina-connector`, Private Service Access | `oficina-k8s-infra` (`infra/`) | `env/shared/k8s-infra` | `main` (único) | **Plataforma compartilhada:** `homolog` executa apenas `terraform plan` sobre o workspace `main`; `apply` exclusivo na `main` (`environment: production`). |
| Cluster GKE Standard `oficina-gke-cluster` + Node Pool `oficina-gke-cluster-node-pool` | `oficina-k8s-infra` (`infra/`) | `env/shared/k8s-infra` | `main` (único) | **Plataforma compartilhada:** `homolog` e `production` são isolados por **Namespaces K8s** no mesmo cluster. |
| Artifact Registry `oficina-docker` | `oficina-k8s-infra` (`infra/`) | `env/shared/k8s-infra` | `main` (único) | Repositório de imagens compartilhado; imagens são imutáveis por tag `${GITHUB_SHA}`. |
| Helm Release `datadog` (Datadog Agent DaemonSet no namespace `datadog`) | `oficina-k8s-infra` (`infra/`) | `env/shared/k8s-infra` | `main` (único) | Reativado na P0 em `infra/main.tf` com `datadog_site = "us5.datadoghq.com"` e `TF_VAR_datadog_api_key` via GitHub Secrets. |
| Instância Cloud SQL `oficina-postgres-db` (IP privado `10.152.0.3`), Databases `oficina_homolog` e `oficina_prod`, Usuário `oficina_user` | `oficina-database-infra` (`terraform/`) | `env/shared/database-infra` | `main` (único) | **Plataforma compartilhada:** instância única. `homolog` executa apenas `terraform plan` no workspace `main`; `apply` exclusivo na `main`. |
| Secrets `database-url-homolog`, `database-url-prod`, `database-password` | `oficina-database-infra` (`terraform/`) | `env/shared/database-infra` | `main` (único) | Criados com nomes distintos por ambiente no mesmo state da instância SQL. |
| Pub/Sub (`oficina-notificacoes-topic*`), Bucket de código, Cloud Functions v2 (`oficina-auth-function*`, `oficina-notificacoes-function*`), API Gateway (`oficina-api-gateway*`) | `oficina-serverless` (`terraform/`) | `env/shared/serverless` | `main` (prod) e `homolog` (homolog) | **Parametrizado por ambiente na P0:** workspace `main` preserva nomes legados (`env_suffix = ""`, secret `database-url-prod`); workspace `homolog` aplica sufixo `-homolog` em todos os recursos e usa `database-url-homolog`. |

---

## 3. Dimensionamento do GKE (Estimativa Estática Ainda Não Validada em Runtime)

> **Importante:** Como o cluster GKE (`oficina-gke-cluster`) não pôde ser inspecionado em execução nesta sessão (`kubectl get nodes` / `kubectl describe nodes` indisponíveis localmente), os números abaixo constituem uma **estimativa estática baseada nos manifestos e no state histórico**, **ainda não validada no cluster real**. Em consonância com a diretriz da P0, **não foi realizado aumento especulativo da infraestrutura GKE** baseando-se apenas em estimativa.

1. **Configuração declarada no Terraform e último apply registrado (Run `35036689334` de `oficina-k8s-infra` e `infra/modules/gke/main.tf`):**
   - Cluster: `projects/pos-fiap-2026/locations/us-east1/clusters/oficina-gke-cluster` (GKE Standard em `us-east1`).
   - Node Pool: `oficina-gke-cluster-node-pool` declarado com `node_count = 1`, `machine_type = "e2-medium"` (2 vCPUs / 2000m CPU nominal, 4 GiB RAM nominal; capacidade alocável teórica em GKE Standard após reservas de sistema: ~`940m` CPU e ~`2.85 GiB` RAM — *valor teórico pendente de confirmação via `kubectl describe nodes`*).
   - *Limitação de verificação local:* A tentativa de conexão ao endpoint registrado no kubeconfig (`https://34.148.79.42`) atingiu timeout e a conta local `jonascv@gmail.com` recebeu `403 Permission denied` na API do projeto `pos-fiap-2026`.

2. **Levantamento estático dos `requests` e `limits` nos manifestos locais (`oficina-api/k8s/`):**

| Workload | Réplicas (por env) | CPU Request (soma) | Memory Request (soma) | CPU Limit (soma) | Memory Limit (soma) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `Deployment/oficina-api` | 2 (`minReplicas: 2` no HPA) | `200m` (`2 × 100m`) | `256Mi` (`2 × 128Mi`) | `1000m` (`2 × 500m`) | `1024Mi` (`2 × 512Mi`) |
| `Deployment/oficina-api-worker` | 1 | `50m` (`1 × 50m`) | `64Mi` (`1 × 64Mi`) | `200m` (`1 × 200m`) | `128Mi` (`1 × 128Mi`) |
| **Subtotal declarado por ambiente (`homolog` ou `production`)** | **3 pods fixos** | **`250m` CPU** | **`320Mi` RAM** | **`1200m` CPU** | **`1152Mi` RAM** |
| **Total declarado para 2 ambientes (`homolog` + `production`)** | **6 pods fixos** | **`500m` CPU** | **`640Mi` RAM** | **`2400m` CPU** | **`2304Mi` RAM** |
| `Job/oficina-api-migrate` *(transitório no deploy, `ttlSecondsAfterFinished: 300`)* | 1 durante migration | `100m` CPU | `128Mi` RAM | `300m` CPU | `256Mi` RAM |
| `DaemonSet/datadog` *(sem requests explícitos em `modules/datadog/main.tf`)* | 1 por nó | *Não medido em runtime* (estimado ~`150m–200m`) | *Não medido em runtime* (estimado ~`256Mi–512Mi`) | *Sem limite explícito no módulo* | *Sem limite explícito no módulo* |

3. **Decisão na P0 e critério para a P7:**
   - `node_count = 1` e `machine_type = "e2-medium"` foram mantidos inalterados para não aumentar infraestrutura por estimativa.
   - A validação real de capacidade (`kubectl get nodes`, `kubectl describe nodes`, `kubectl top nodes` e consumo efetivo do DaemonSet do Datadog + pods de sistema do `kube-system`) permanece registrada como **pendência obrigatória antes do dimensionamento/deploy da Etapa P7**.

---

## 4. Governança GitHub, Environments e Comprovação de Isolamento antes de Migrations

1. **Acesso do avaliador (`soat-architecture`):**
   - Verificado via GitHub API (`repos/jcontiero/{repo}/collaborators`): o usuário `soat-architecture` possui acesso ativo nos quatro repositórios (`oficina-api`, `oficina-k8s-infra`, `oficina-database-infra` e `oficina-serverless`).

2. **Ativação dos Rulesets (`main` e `homolog`):**
   - Nos 4 repositórios, os rulesets `main` e `homolog` estavam com `"enforcement": "disabled"`.
   - Na P0, todos os **8 rulesets** foram atualizados via API para `"enforcement": "active"`, exigindo:
     - Proibição de deleção (`deletion`) e force-push (`non_fast_forward`);
     - Pull Request obrigatório (`pull_request`);
     - Status checks obrigatórios (`required_status_checks`): `validate` (ou `lint-test` no serverless), `SonarQube` e `SonarCloud Code Analysis`.

3. **GitHub Environments (`homolog` e `production`) com Branch Policy estrita:**
   - Criados e configurados via GitHub API nos 4 repositórios:
     - Environment `homolog` (`custom_branch_policies: true`): permite deploy **exclusivamente** da branch `homolog`.
     - Environment `production` (`custom_branch_policies: true`): permite deploy **exclusivamente** da branch `main`.

4. **Trava de isolamento antes de executar migrations (`oficina-api/.github/workflows/deploy.yml`):**
   - Antes de autenticar no GKE ou aplicar o `job-migrate.yaml`, o job `build-push-deploy` executa a etapa `Verify Homolog / Production Database Isolation Before Migration`:
     - Em `homolog`, exige que `DB_URL` aponte explicitamente para `oficina_homolog` (ou `oficina_os_homolog`) e **aborta com erro (`exit 1`)** caso contenha `oficina_prod` ou `oficina_os_production` ou esteja vazio.
     - Em `main` (`production`), exige que `DB_URL` aponte explicitamente para `oficina_prod` (ou `oficina_os_production`) e **aborta com erro (`exit 1`)** caso contenha `homolog`.
   - Adicionalmente, o `job-migrate.yaml` agora recebe a imagem com tag imutável `${GITHUB_SHA}` e é aguardado com `kubectl wait --for=condition=complete job/oficina-api-migrate --timeout=120s` **antes** da aplicação dos Deployments da API e do Worker.

---

## 5. Baseline de Testes e Cobertura

1. **`oficina-api`:**
   - **Antes das correções da P0:** `build.yml` executava apenas `tests/unit` com `--cov-fail-under=0` (141 testes passando, cobertura total de `38.83%` sobre `src/`). Os testes em `tests/integration` falhavam porque `CriarUsuario` nas fixtures `conftest.py` e `test_auth.py` era instanciado sem `uow=SQLAlchemyUnitOfWork(db)` com `autoflush=False`.
   - **Após as correções da P0:**
     - Removido o atributo duplicado `status: StatusCliente = StatusCliente.ATIVO` em `src/atendimento/dominio/entidades.py`.
     - Corrigido o uso de `SQLAlchemyUnitOfWork(db)` nas fixtures de integração, a exclusão de `status` em `atualizar_cliente` e a compatibilidade do payload de token em `AtualizarStatusViaWebhook`.
     - Resultado local verificado (`pytest tests/unit tests/integration --cov=src --cov-fail-under=80`): **186 testes passando, 0 falhas, cobertura total de `85.53%`** (acima do gate obrigatório de 80%).
     - Gate `--cov-fail-under=80` ativado em `build.yml` e `deploy.yml`.

2. **`oficina-serverless`:**
   - Resultado local verificado (`PYTHONPATH=src:src/notificacoes pytest tests/unit --cov=src --cov-fail-under=80`): **23 testes passando, 0 falhas, cobertura total de `97.20%`**.
   - Removido o bypass `|| echo` em `.github/workflows/ci.yml` e adicionado gate `--cov-fail-under=80` + validação de Terraform no CI.

---

## 6. Pendências da Etapa P0 (Status: Parcialmente Concluída)

A Etapa P0 permanece classificada como **parcialmente concluída** até que as cinco pendências abaixo sejam resolvidas (nenhuma delas bloqueia a execução local das etapas P1 a P6):

1. **Falha de autorização no SonarCloud (`HTTP 403 Forbidden`) e merge dos 4 PRs da P0:**
   - Na execução dos checks dos 4 PRs da P0 ([`oficina-api#12`](https://github.com/jcontiero/oficina-api/pull/12), [`oficina-k8s-infra#6`](https://github.com/jcontiero/oficina-k8s-infra/pull/6), [`oficina-database-infra#5`](https://github.com/jcontiero/oficina-database-infra/pull/5) e [`oficina-serverless#5`](https://github.com/jcontiero/oficina-serverless/pull/5)), os jobs de validação de código, cobertura ($\ge 80\%$) e Terraform passaram com sucesso, mas o job `Build/SonarQube` falhou com `GET https://api.sonarcloud.io/analysis/jres?os=linux&arch=x86_64 failed with HTTP 403 Forbidden. Please check the property sonar.token or the environment variable SONAR_TOKEN`.
   - **Classificação correta do erro:** `HTTP 403 Forbidden` indica **falta de permissão / falha de autorização do token `SONAR_TOKEN`** (token inválido, revogado ou sem permissão `Execute Analysis` na organização/projeto do SonarCloud — não é possível afirmar apenas pelo código HTTP que a causa tenha sido expiração por prazo).
   - **Ação pendente:** Atualizar `SONAR_TOKEN` nos 4 repositórios com um token válido com permissão de análise no SonarCloud, reexecutar o check `SonarQube`, realizar o **merge dos 4 PRs na `main`** e criar a branch `homolog` a partir da `main` atualizada.
2. **Acesso ao projeto GCP (`pos-fiap-2026`) e verificação de capacidade real do GKE:**
   - Restabelecer acesso autenticado ao projeto GCP e executar `kubectl get nodes -o wide`, `kubectl describe nodes` e `kubectl top nodes` para substituir a estimativa estática da Seção 3 por medição real antes de redimensionar ou implantar os três serviços na P7.
3. **Validação operacional do Datadog Agent e do isolamento `homolog`/`production`:**
   - Embora o módulo Terraform do Datadog e as travas de isolamento (`GitHub Environments` + validação de `DB_URL` antes de migrations + `env_suffix` serverless) estejam codificados nos PRs, sua comprovação operacional depende da aplicação em nuvem (DaemonSet `datadog` saudável reportando traces/logs e smoke test de isolamento entre `homolog` e `production`).
4. **Configuração dos Secrets por GitHub Environment:**
   - Cadastrar `DB_URL` no GitHub Environment `homolog` (`oficina_homolog` / `oficina_os_homolog`) e no GitHub Environment `production` (`oficina_prod` / `oficina_os_production`), além de `DATADOG_API_KEY` em `oficina-k8s-infra`.
5. **Remoção do bloqueio temporário de deploy manual antes do aceite final de CI/CD (P7):**
   - Atendendo à solicitação de segurança para não criar recursos na nuvem sem permissão explícita, os workflows `.github/workflows/deploy.yml` dos 4 repositórios estão temporariamente travados em `workflow_dispatch` com input `confirm_cloud_apply == 'true'` / `confirm_deploy == 'true'`.
   - **Ação obrigatória na P7 (antes do aceite final de CI/CD e gravação do vídeo):** Remover esse bloqueio temporário para restaurar o **deploy automatizado em Kubernetes a cada push/merge em `homolog` e `main`**, conforme exigido pelo enunciado da Fase 4 (páginas 4–5).
