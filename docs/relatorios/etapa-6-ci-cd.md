# Relatório — Etapa 6: CI/CD

**Projeto:** Oficina Mecânica API — Fase 2  
**Data:** 08/07/2026  
**Responsável:** Jonas Vasconcelos

---

## 1. Objetivo

Evoluir o workflow do GitHub Actions para uma pipeline completa de CI/CD, cobrindo lint, testes, cobertura, build/push de imagem Docker, provisionamento Terraform, deploy no Kubernetes e execução das migrations.

---

## 2. Arquivo alterado

- `.github/workflows/build.yml` — reescrito e renomeado para `Build and Deploy`.

---

## 3. Estrutura da pipeline

A pipeline é composta por 8 jobs, com dependências progressivas:

```
lint-and-format
    ├── unit-tests ────┐
    └── integration-tests ──── coverage-and-sonar ──── docker-build-push ──── terraform ──── deploy-k8s ──── migrate
```

### 3.1 `lint-and-format`
- Instala dependências de desenvolvimento (`pip install -e ".[dev]"`).
- Executa `ruff check src tests scripts`.
- Executa `black --check src tests scripts`.

### 3.2 `unit-tests`
- Depende do `lint-and-format`.
- Executa `pytest tests/unit/ -q`.

### 3.3 `integration-tests`
- Depende do `lint-and-format`.
- Sobe serviço PostgreSQL 16.
- Cria banco de testes `oficina_test`.
- Executa `pytest tests/integration/ -q`.

### 3.4 `coverage-and-sonar`
- Depende de `unit-tests` e `integration-tests`.
- Sobe serviço PostgreSQL 16.
- Executa `pytest tests/ --cov=src --cov-report=xml:coverage.xml --cov-fail-under=80 -q`.
- Envia scan para SonarQube Cloud.

### 3.5 `docker-build-push`
- Depende de `coverage-and-sonar`.
- Executa apenas na branch `main`.
- Faz login no Docker Hub.
- Build multi-stage e push com tags:
  - `DOCKER_USERNAME/oficina-api:<sha>`
  - `DOCKER_USERNAME/oficina-api:latest`

### 3.6 `terraform`
- Depende de `docker-build-push`.
- Executa apenas na branch `main`.
- Usa environment `production` para permitir aprovação manual.
- Executa `terraform init`, `plan` e `apply -auto-approve`.

### 3.7 `deploy-k8s`
- Depende de `terraform`.
- Executa apenas na branch `main`.
- Usa environment `production`.
- Configura `kubectl` a partir do secret `KUBE_CONFIG`.
- Executa `kubectl apply -f k8s/`.
- Aguarda rollout do Deployment da API.

### 3.8 `migrate`
- Depende de `deploy-k8s`.
- Executa apenas na branch `main`.
- Usa environment `production`.
- Aplica `k8s/job-migrate.yaml`.
- Aguarda conclusão do Job.

---

## 4. Triggers

A pipeline dispara em:
- Push para `main` ou `tech_challenge`.
- Pull requests abertos, sincronizados ou reabertos.

Jobs de deploy (Docker push, Terraform, deploy K8s, migrate) só executam em `main`.

---

## 5. Secrets esperados

| Secret | Uso |
|---|---|
| `SONAR_TOKEN` | Scan SonarQube |
| `DOCKER_USERNAME` | Login no Docker Hub |
| `DOCKER_PASSWORD` | Login no Docker Hub |
| `KUBE_CONFIG` | Configuração do kubectl (base64) |
| `POSTGRES_PASSWORD` | Senha do PostgreSQL no Terraform (opcional) |

### 5.1 Onde configurar os secrets no GitHub

#### Opção A — Repository secrets (mais simples)

1. Acesse o repositório no GitHub.
2. Clique em **Settings**.
3. No menu lateral, expanda **Secrets and variables** > clique em **Actions**.
4. Clique em **New repository secret**.
5. Adicione os secrets um a um (`SONAR_TOKEN`, `DOCKER_USERNAME`, `DOCKER_PASSWORD`, `KUBE_CONFIG`, etc.).

URL direta (substitua `<usuario>` e `<repo>`):

```
https://github.com/<usuario>/<repo>/settings/secrets/actions
```

#### Opção B — Environment secrets (recomendado para deploy)

Como os jobs `terraform`, `deploy-k8s` e `migrate` usam `environment: production`, você pode criar secrets específicos para esse ambiente:

1. Em **Settings** > **Environments**, clique em **New environment**.
2. Nomeie como `production`.
3. Dentro do environment, clique em **Add secret** e cadastre os valores.
4. (Opcional) Configure **Deployment protection rules** para exigir aprovação manual antes do deploy.

#### Gerando o `KUBE_CONFIG` em base64

No terminal, execute:

```bash
cat ~/.kube/config | base64
```

Cole o resultado no secret `KUBE_CONFIG`.

---

## 6. Validação

### 6.1 Validação de YAML

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/build.yml')); print('YAML válido')"
```

Resultado: `YAML válido`.

### 6.2 Alinhamento com a Fase 2

A pipeline atende todos os 12 passos definidos em `docs/plano-implementacao-fase2.md`:

1. ✅ Checkout
2. ✅ Lint (`ruff`)
3. ✅ Formatação (`black --check`)
4. ✅ Testes unitários
5. ✅ Testes de integração com Postgres
6. ✅ Cobertura (`pytest-cov`)
7. ✅ Scan SonarQube
8. ✅ Build Docker
9. ✅ Push para registry
10. ✅ Terraform plan/apply
11. ✅ Deploy no Kubernetes
12. ✅ Execução das migrations

---

## 7. Observações

- A pipeline assume que os secrets do Docker Hub e do cluster Kubernetes estão configurados no repositório.
- Para ambiente local (kind/minikube), o deploy automático pode exigir ajustes no `KUBE_CONFIG` ou exposição do cluster.
- O job de Terraform usa `environment: production`, o que habilita aprovação manual quando configurado nas regras do ambiente do GitHub.

---

## 8. Próximos passos

- Etapa 7: atualizar `README.md`, criar collection de APIs e gravar vídeo demonstrativo.
- Configurar os secrets no repositório GitHub antes do primeiro deploy.
- Validar a pipeline executando um push para `main` ou `tech_challenge`.
