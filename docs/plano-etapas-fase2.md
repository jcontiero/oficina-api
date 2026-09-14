# Plano de Etapas — Fase 2

**Projeto:** Oficina Mecânica API  
**Última atualização:** 07/07/2026

Este documento organiza a execução da Fase 2 em etapas sequenciais, com entregáveis e critérios de verificação.

---

## Etapas concluídas

### Etapa 1 — Refatoração Arquitetural (Clean Architecture/Hexagonal)
- **Status:** ✅ Concluído
- **Entregáveis:**
  - Ports e adapters para identidade, atendimento, estoque e relatórios.
  - Container de injeção de dependências (`src/container.py`).
  - Remoção de singletons globais.
  - Refatoração de relatórios e casos de uso.
- **Critérios de verificação:**
  - `ruff check src tests scripts` passa.
  - `pytest tests/` passa.
  - Cobertura `dominio/` e `aplicacao/` ≥ 80%.
- **Relatório:** `docs/relatorios/etapa-1-refatoracao-arquitetural.md`

### Etapa 2 — APIs de Ordem de Serviço (Fase 2)
- **Status:** ✅ Concluído
- **Entregáveis:**
  - `POST /ordens-de-servico` (abertura unificada).
  - `GET /ordens-de-servico/{id}/status`.
  - `POST /ordens-de-servico/{id}/aprovacao`.
  - `GET /ordens-de-servico` (listagem ordenada).
  - `POST /webhooks/os/{id}/atualizar-status`.
  - Status Fase 2 mapeados.
  - Tokens JWT para webhook.
- **Critérios de verificação:**
  - Todas as APIs testadas (integração + unitário).
  - Cobertura mantida ≥ 80% nas camadas `dominio/` e `aplicacao/`.
- **Relatório:** `docs/relatorios/etapa-2-apis-fase2.md`

### Etapa 3 — Docker
- **Status:** ✅ Concluído
- **Entregáveis:**
  - `Dockerfile` reescrito com multi-stage build.
  - Imagem final baseada em `python:3.12-slim`.
  - Usuário não-root (`appuser`).
  - `EXPOSE 8000` e health check em `/health`.
  - Startup executa apenas `uvicorn` (sem DDL/seeds).
  - `.dockerignore` atualizado.
  - `docker-compose.yml` com `db`, `api`, `migrate` e `seed`.
  - `seed.py` ajustado para a arquitetura atual (container de DI).
- **Critérios de verificação:**
  - `docker build -t oficina-api .` executa com sucesso.
  - `docker-compose up -d` sobe a API e o banco.
  - Health check retorna 200.
  - Serviço `seed` popula o admin inicial com sucesso.
- **Relatório:** `docs/relatorios/etapa-3-docker.md`

---

## Etapas pendentes

### Etapa 4 — Kubernetes
- **Status:** ✅ Concluído
- **Entregáveis:**
  - `namespace.yaml` com namespace `oficina-api`.
  - `configmap.yaml` para variáveis não sensíveis.
  - `secret.yaml` com credenciais codificadas (placeholders).
  - `deployment.yaml` da API com probes, resources e security context.
  - `service.yaml` para expor a API internamente.
  - `hpa.yaml` com escalonamento por CPU e memória.
  - `job-migrate.yaml` para execução das migrations.
  - `pvc.yaml`, `postgres-deployment.yaml` e `postgres-service.yaml` para banco no cluster.
  - `ingress.yaml` opcional (comentado).
- **Critérios de verificação:**
  - `kubectl apply -f k8s/` aplica todos os manifestos sem erros.
  - Pods da API e do banco ficam `Running`.
  - HPA configurado com base em CPU/memória.
  - Health check via service retorna `{"status":"ok"}`.
- **Relatório:** `docs/relatorios/etapa-4-kubernetes.md`

### Etapa 5 — Terraform
- **Status:** ✅ Concluído
- **Entregáveis:**
  - Estrutura modular em `/infra` (`modules/cluster`, `modules/database`, `modules/registry`).
  - Cluster Kubernetes local via kind (`tehcyx/kind`).
  - Banco PostgreSQL dentro do cluster via Helm (`bitnami/postgresql`).
  - Registry local via Docker (`registry:2`).
  - `providers.tf`, `variables.tf`, `outputs.tf`, `backend.tf`.
  - Arquivos `environments/local.tfvars` e `production.tfvars.example`.
  - `.gitignore` atualizado para arquivos do Terraform.
- **Critérios de verificação:**
  - `terraform fmt -recursive` passa.
  - `terraform init` baixa providers corretamente.
  - `terraform validate` passa.
  - `terraform plan -var-file=environments/local.tfvars` executa sem erros.
- **Notas de portabilidade:**
  - Módulos com interfaces claras permitem substituir implementações locais por módulos de cloud (AWS/GCP/Azure) sem alterar a raiz.
  - VPC, subnets, IAM e banco gerenciado são omitidos no ambiente local, mas documentados como próximos passos para produção.
- **Relatório:** `docs/relatorios/etapa-5-terraform.md`

### Etapa 6 — CI/CD
- **Status:** ✅ Concluído
- **Entregáveis:**
  - Workflow `.github/workflows/build.yml` reescrito e renomeado para `Build and Deploy`.
  - Jobs separados:
    1. `lint-and-format` (ruff + black).
    2. `unit-tests`.
    3. `integration-tests` (com serviço PostgreSQL).
    4. `coverage-and-sonar` (pytest-cov + SonarQube).
    5. `docker-build-push` (build multi-stage + push para Docker Hub, apenas `main`).
    6. `terraform` (plan/apply, com environment `production` para aprovação manual).
    7. `deploy-k8s` (`kubectl apply -f k8s/`, apenas `main`).
    8. `migrate` (`kubectl apply -f k8s/job-migrate.yaml`, apenas `main`).
  - Validação de YAML bem-sucedida.
- **Critérios de verificação:**
  - Pipeline executa todos os passos em push para `main`.
  - Build e push da imagem funcionam.
  - Deploy aplica os manifestos no cluster.
- **Relatório:** `docs/relatorios/etapa-6-ci-cd.md`

### Etapa 7 — Documentação e Vídeo
- **Status:** ✅ Concluído (documentação)
- **Entregáveis:**
  - `README.md` atualizado com:
    - Objetivos da Fase 2.
    - Desenho da arquitetura (Clean Architecture, Kubernetes, Terraform, CI/CD).
    - Instruções de execução local, deploy K8s e provisionamento Terraform.
    - Link para collection de APIs (`docs/collection-postman.json`).
    - Seção para link do vídeo demonstrativo.
  - Collection Postman criada em `docs/collection-postman.json` cobrindo as APIs obrigatórias da Fase 2.
  - Instruções para gravação do vídeo de até 15 minutos.
- **Critérios de verificação:**
  - README reflete o estado atual do projeto.
  - Collection cobre as APIs obrigatórias da Fase 2.
  - Vídeo a ser gravado e link adicionado ao README.
- **Relatório:** `docs/relatorios/etapa-7-documentacao.md`

---

## Decisões pendentes de alinhamento

Antes de prosseguir, algumas decisões do plano original ainda precisam ser confirmadas:

1. **Provedor de cloud:** AWS, Azure, GCP ou ambiente local (kind/minikube/k3d)?
2. **Banco de dados:** serviço gerenciado na cloud ou PostgreSQL dentro do Kubernetes?
3. **Registry de imagens:** Docker Hub, ECR, GCR ou ACR?
4. **Notificações por e-mail:** manter SMTP síncrono ou evoluir para fila assíncrona?
5. **Domínio/URL pública:** haverá domínio para os links de aprovação por e-mail?

Para o Tech Challenge, a abordagem sugerida é:
- **Cloud:** local (kind/k3d/minikube) para facilitar demonstração sem custo.
- **Banco:** PostgreSQL dentro do cluster.
- **Registry:** Docker Hub.
- **Notificações:** SMTP síncrono mantido.
- **Domínio:** `localhost`/Ngrok para demonstração.

Caso prefira outra configuração, informe antes de iniciarmos a Etapa 5.
