# Plano de Implementação — Fase 2 (Tech Challenge)

**Projeto:** Oficina Mecânica API  
**Objetivo:** Evoluir o MVP da Fase 1 para uma arquitetura escalável, resiliente e automatizada, aplicando Clean Architecture/Hexagonal, Kubernetes, Terraform e CI/CD.

---

## 1. Contexto e objetivos

Após o MVP inicial, a oficina precisa suportar maior demanda, múltiplas unidades e horários de pico. A Fase 2 exige:

- Refatoração do código com **Clean Code**, **Clean Architecture/Hexagonal** e testes automatizados.
- Evolução das APIs de Ordem de Serviço (OS) conforme novas regras de negócio.
- Containerização revisada com **Docker**.
- Orquestração com **Kubernetes** (HPA, ConfigMaps, Secrets, Services, Deployments).
- Infraestrutura como Código (**Terraform**).
- Pipeline de **CI/CD** completa.

---

## 2. Diagnóstico do estado atual

| Aspecto | Situação atual | Gap para a Fase 2 |
|---|---|---|
| **Arquitetura** | Monolito modular com DDD e camadas (`dominio`, `aplicacao`, `infraestrutura`, `apresentacao`). | Acoplamentos invertidos: camada de aplicação depende de `shared.notificacoes` e `shared.seguranca`; rotas instanciam repositórios concretos. |
| **APIs de OS** | Fluxo completo já existe, mas com contratos diferentes. | Adaptar para abertura unificada, consulta de status, aprovação externa, listagem ordenada e atualização por e-mail. |
| **Testes** | ~122 testes (unit + integração), cobertura ≥80% no domínio. | Faltam unit tests para casos de uso; pipeline não executa lint, build Docker nem deploy. |
| **Docker** | Dockerfile simples, sem multi-stage, executa DDL e seeds no startup. | Reescrever com multi-stage, usuário não-root, health check e separação de migrations/seeds. |
| **Kubernetes** | Inexistente. | Criar diretório `/k8s` com todos os manifestos. |
| **IaC** | Inexistente. | Criar diretório `/infra` com scripts Terraform. |
| **CI/CD** | Apenas SonarQube + pytest no GitHub Actions. | Evoluir para build, push de imagem, deploy no cluster e aplicação de migrations. |

---

## 3. Arquitetura alvo

Manter o **monolito modular** (custo/benefício adequado ao Tech Challenge), mas refatorar internamente para **Clean Architecture/Hexagonal**.

```
src/
├── main.py                 # Ponto de entrada e composição da aplicação
├── container.py            # Container de injeção de dependências
├── config.py               # Configurações (sem singleton global)
├── shared/                 # Utilitários puros (exceções HTTP genéricas, helpers)
├── identidade/
├── atendimento/
├── catalogo/
├── estoque/
└── relatorios/
    ├── dominio/            # Entidades, value objects, exceções, regras
    ├── aplicacao/          # Casos de uso + interfaces/portas
    ├── infraestrutura/     # Adapters (SQLAlchemy, SMTP, JWT, bcrypt)
    └── apresentacao/       # Rotas FastAPI + schemas Pydantic
```

### Ports (interfaces) a definir

| Porta | Responsabilidade | Implementação de infraestrutura |
|---|---|---|
| `RepositorioUsuario` | CRUD e busca de usuários | `UsuarioRepositorioImpl` (SQLAlchemy) |
| `RepositorioCliente` | CRUD e busca de clientes | `ClienteRepositorioImpl` (SQLAlchemy) |
| `RepositorioVeiculo` | CRUD e busca de veículos | `VeiculoRepositorioImpl` (SQLAlchemy) |
| `RepositorioOrdemDeServico` | Persistência do agregado OS | `OrdemDeServicoRepositorioImpl` (SQLAlchemy) |
| `RepositorioServico` | CRUD de serviços do catálogo | `ServicoRepositorioImpl` (SQLAlchemy) |
| `RepositorioPeca` | CRUD e controle de estoque | `PecaRepositorioImpl` (SQLAlchemy) |
| `ProvedorToken` | Criar e validar tokens JWT | `JwtTokenProvider` |
| `ProvedorHashSenha` | Hash e verificação de senhas | `BcryptHashProvider` |
| `Notificador` | Envio de notificações por e-mail | `SmtpNotificador` |
| `ConsultaRelatorios` | Queries de relatórios | `RelatorioConsultaImpl` (SQLAlchemy) |

---

## 4. Refatoração do código

### 4.1 Aplicar Clean Architecture/Hexagonal

1. **Isolar serviços concretos**
   - Mover `src/shared/seguranca.py` → adapters de infraestrutura (`identidade/infraestrutura/jwt_provider.py`, `identidade/infraestrutura/bcrypt_provider.py`).
   - Mover `src/shared/notificacoes.py` → adapter `estoque/infraestrutura/notificador_smtp.py` e `atendimento/infraestrutura/notificador_smtp.py` (ou `shared/infraestrutura/notificador_smtp.py`).

2. **Definir ports nas camadas corretas**
   - `ProvedorToken` e `ProvedorHashSenha` ficam em `identidade/aplicacao/ports.py`.
   - `Notificador` fica em `atendimento/aplicacao/ports.py` e/ou `estoque/aplicacao/ports.py`.
   - `ConsultaRelatorios` fica em `relatorios/aplicacao/ports.py`.

3. **Criar container de injeção de dependências**
   - `src/container.py` instancia todos os adapters e os injeta nos casos de uso.
   - Rotas recebem dependências via FastAPI `Depends`, sem instanciar repositórios concretos.

4. **Refatorar `relatorios`**
   - Criar caso de uso `GerarRelatorioTempoMedioDeServicos`.
   - Criar adapter `RelatorioConsultaImpl`.
   - Remover query SQLAlchemy direta da rota.

5. **Eliminar `ValueError` como controle de domínio**
   - Criar exceções específicas: `OrdemDeServicoNaoEncontradaError`, `ClienteNaoEncontradoError`, etc.
   - Mapear exceções para status HTTP na camada de apresentação.

6. **Remover `setattr` dinâmico**
   - Trocar `AtualizarCliente`, `AtualizarVeiculo` e `AtualizarPeca` por métodos explícitos nas entidades ou parâmetros tipados nos casos de uso.

7. **Configuração**
   - Evitar singleton global em `src/config.py`.
   - Instanciar configuração uma única vez em `main.py` ou `container.py`.

### 4.2 APIs obrigatórias da Fase 2

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/ordens-de-servico` | Abertura unificada: recebe dados do cliente, veículo, serviços e peças; retorna o identificador único da OS. |
| `GET` | `/ordens-de-servico/{id}/status` | Retorna o status atual da OS (Recebida, Diagnóstico, Aguardando Aprovação, Execução, Finalizada, Entregue). |
| `POST` | `/ordens-de-servico/{id}/aprovacao` | Recebe notificação externa de aprovação ou recusa do orçamento. |
| `GET` | `/ordens-de-servico` | Listagem ordenada: Em Execução > Aguardando Aprovação > Diagnóstico > Recebida; mais antigas primeiro; ocultar finalizadas e entregues. |
| `POST` | `/webhooks/os/{id}/atualizar-status` | Endpoint seguro (token no link) para atualização de status via e-mail. |

### 4.3 Testes

- Criar unit tests para **todos** os casos de uso.
- Manter testes de integração para fluxos críticos de OS.
- Garantir cobertura mínima de **80%** nas camadas `dominio/` e `aplicacao/`.
- Adicionar testes para adapters de infraestrutura quando necessário.

---

## 5. Infraestrutura e DevOps

### 5.1 Docker

Reescrever `Dockerfile` com:

- **Multi-stage build**: estágio de build/instalação e estágio final enxuto.
- **Imagem base** `python:3.12-slim` no estágio final.
- **Usuário não-root** (`appuser`).
- **`EXPOSE 8000`**.
- **Health check** (`curl` ou `python` verificando endpoint `/health`).
- **Sem DDL/seeds no startup**: a aplicação deve iniciar apenas `uvicorn`.
- **.dockerignore** para reduzir tamanho da imagem.

Atualizar `docker-compose.yml` para desenvolvimento local:

- Manter `db` (Postgres 16) com healthcheck.
- Manter `api` dependendo do banco.
- Adicionar serviço opcional `migrate` para rodar Alembic.
- Adicionar serviço opcional `seed` para popular dados iniciais.

### 5.2 Kubernetes (`/k8s`)

Manifestos a criar:

| Arquivo | Propósito |
|---|---|
| `namespace.yaml` | Namespace `oficina-api`. |
| `configmap.yaml` | Variáveis não sensíveis. |
| `secret.yaml` | `SECRET_KEY`, credenciais SMTP, senha do banco. |
| `deployment.yaml` | Deployment da API com readiness/liveness probes. |
| `service.yaml` | Service do tipo ClusterIP ou LoadBalancer. |
| `hpa.yaml` | HorizontalPodAutoscaler com base em CPU/memória. |
| `job-migrate.yaml` | Job para execução das migrations (Alembic). |
| `pvc.yaml` | Persistência para o PostgreSQL, caso rode no cluster. |
| `postgres-deployment.yaml` | Deployment do PostgreSQL (somente se não usar BD gerenciado). |
| `postgres-service.yaml` | Service do PostgreSQL interno. |
| `ingress.yaml` | Exposição via Ingress (opcional). |

### 5.3 Infraestrutura como Código (`/infra`)

Scripts Terraform para provisionar:

- **Cluster Kubernetes** (EKS, GKE, AKS ou cluster local via kind/k3d).
- **Banco de dados** gerenciado (RDS/Cloud SQL/Azure Database) ou PostgreSQL no cluster.
- **Container registry** (ECR/GCR/ACR/Docker Hub).
- **VPC, subnets e security groups** (se for cloud).
- **IAM roles/policies** mínimas para o cluster.
- **Outputs** com endpoints e comandos de acesso.

### 5.4 CI/CD

Evoluir `.github/workflows/build.yml` para pipeline completa:

1. **Checkout** do código.
2. **Lint** com `ruff`.
3. **Formatação** com `black` (check).
4. **Testes unitários**.
5. **Testes de integração** com banco Postgres.
6. **Cobertura** com `pytest-cov`.
7. **Scan SonarQube**.
8. **Build da imagem Docker**.
9. **Push da imagem** para registry.
10. **Aplicação do Terraform** (plan + apply, com aprovação manual em produção).
11. **Deploy no Kubernetes** (`kubectl apply -f k8s/`).
12. **Execução das migrations** (`kubectl apply -f k8s/job-migrate.yaml`).

---

## 6. Ferramentas e dependências sugeridas

| Categoria | Ferramenta |
|---|---|
| Framework | FastAPI + Uvicorn (já utilizados) |
| ORM + migrations | SQLAlchemy 2.0 + Alembic |
| Banco de dados | PostgreSQL 16 |
| Testes | pytest, pytest-cov, httpx, factory-boy (opcional) |
| Lint/Format | ruff, black |
| Container | Docker + Docker Compose |
| Orquestração | Kubernetes (kubectl, minikube/kind/k3d para local) |
| IaC | Terraform + provider do provedor cloud escolhido |
| CI/CD | GitHub Actions |
| Registry | Docker Hub / ECR / GCR / ACR |

---

## 7. Entregáveis finais

- Código-fonte refatorado seguindo Clean Architecture/Hexagonal.
- `Dockerfile` e `docker-compose.yml` revisados.
- Diretório `/k8s` com manifestos Kubernetes completos.
- Diretório `/infra` com scripts Terraform documentados.
- Pipeline CI/CD em `.github/workflows/`.
- `README.md` atualizado com:
  - Descrição da solução e objetivos da Fase 2.
  - Desenho da arquitetura (componentes, infraestrutura, fluxo de deploy).
  - Instruções de execução local, deploy em Kubernetes e provisionamento com Terraform.
  - Link para collection de APIs (Postman/Swagger).
  - Link para vídeo demonstrativo.
- Vídeo de até 15 minutos demonstrando deploy, CI/CD, consumo de APIs e escalabilidade automática.

---

## 8. Perguntas pendentes de alinhamento

Antes de iniciar a implementação, é necessário confirmar:

1. **Provedor de cloud:** Ambiente local via `kind`.
2. **Banco de dados:** PostgreSQL rodando dentro do próprio cluster Kubernetes.
3. **Registry de imagens:** Docker Hub.
4. **Notificações por e-mail:** Manter SMTP síncrono (definição inicial, pode ser alterada).
5. **Domínio/URL pública:** Usaremos `localhost`/Ngrok para testes locais.
6. **Ferramenta de CI/CD:** GitHub Actions.

---

## 9. Cronograma sugerido

| Etapa | Tarefas | Tempo estimado |
|---|---|---|
| **1. Alinhamento** | Responder perguntas pendentes e definir stack final. | 1 dia |
| **2. Refatoração arquitetural** | Ports/adapters, container de DI, refatorar `relatorios`, remover acoplamentos. | 3–4 dias |
| **3. APIs da Fase 2** | Abertura unificada, status, aprovação, listagem ordenada, webhook de e-mail. | 2–3 dias |
| **4. Testes** | Unit tests de casos de uso + ajustes nos testes de integração. | 2 dias |
| **5. Docker** | Reescrever Dockerfile, docker-compose, adicionar health check. | 1 dia |
| **6. Kubernetes** | Criar manifestos /k8s, HPA, ConfigMaps, Secrets, jobs. | 2–3 dias |
| **7. Terraform** | Criar /infra, provisionar cluster, banco e registry. | 2–3 dias |
| **8. CI/CD** | Evoluir workflow para build, push, deploy e migrations. | 2 dias |
| **9. Documentação e vídeo** | Atualizar README, collection, gravar vídeo. | 2 dias |
| **10. Validação final** | Testes end-to-end, ajustes e entrega. | 1–2 dias |

**Total estimado:** 18–24 dias.

---

## 10. Próximos passos

1. Revisar e aprovar este plano.
2. Responder as perguntas de alinhamento da seção 8.
3. Iniciar pela refatoração arquitetural (ports/adapters + container de DI).
4. Evoluir incrementalmente para APIs, Docker, K8s, Terraform e CI/CD.
