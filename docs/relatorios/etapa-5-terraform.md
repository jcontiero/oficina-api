# Relatório — Etapa 5: Terraform

**Projeto:** Oficina Mecânica API — Fase 2  
**Data:** 08/07/2026  
**Responsável:** Jonas Vasconcelos

---

## 1. Objetivo

Criar a infraestrutura como código em `/infra` com foco em **portabilidade** entre ambientes local e nuvem, provisionando cluster Kubernetes, banco de dados PostgreSQL e container registry.

---

## 2. Decisões de arquitetura

### 2.1 Ambiente local com kind
Para o Tech Challenge, optamos por ambiente **local** (sem custos de cloud):
- Cluster Kubernetes provisionado via **kind** (provider `tehcyx/kind`).
- PostgreSQL provisionado dentro do cluster via **Helm** (`bitnami/postgresql`).
- Registry local provisionado via **Docker** (`registry:2`).

### 2.2 Estrutura modular para portabilidade
A infraestrutura foi dividida em módulos com interfaces claras:

```
infra/
├── modules/
│   ├── cluster/      # Responsável pelo cluster Kubernetes
│   ├── database/     # Responsável pelo banco de dados
│   └── registry/     # Responsável pelo registry de imagens
├── main.tf
├── variables.tf
├── outputs.tf
├── providers.tf
├── backend.tf
└── environments/
    ├── local.tfvars
    └── production.tfvars.example
```

Essa separação permite que, em uma migração para nuvem, apenas os módulos sejam trocados (ex.: `modules/cluster` passa a usar EKS/GKE/AKS) sem reescrever a raiz do projeto.

### 2.3 O que ficou de fora do ambiente local
- **VPC, subnets e security groups:** específicos de cloud; documentados como próximos passos para produção.
- **IAM roles/policies:** específicos de cloud; documentados como próximos passos para produção.
- **Backend remoto:** mantido como backend local para simplificar o Tech Challenge, com instruções para migrar para S3/GCS/Azure Storage em equipe.

---

## 3. Módulos criados

### 3.1 `modules/cluster`
- Provider: `tehcyx/kind`.
- Recurso: `kind_cluster`.
- Configurações:
  - Nome e versão do Kubernetes parametrizáveis.
  - Geração de kubeconfig em caminho configurável.
  - Port mappings extras para HTTP (8080) e HTTPS (8443).
  - Label `ingress-ready=true` para futuro uso de Ingress.

### 3.2 `modules/database`
- Providers: `helm`, `kubernetes`.
- Recursos:
  - `kubernetes_namespace_v1` para o namespace da aplicação.
  - `helm_release` para instalar PostgreSQL via chart Bitnami.
- Configurações:
  - Nome do banco, usuário e senha parametrizáveis.
  - Persistência e requests/limits configuráveis.

### 3.3 `modules/registry`
- Provider: `kreuzwerker/docker`.
- Recurso: `docker_container` rodando `registry:2`.
- Configurações:
  - Nome e porta do registry parametrizáveis.
  - Labels para identificação.

---

## 4. Arquivos raiz

### 4.1 `providers.tf`
Declara os providers com versões fixas:
- `tehcyx/kind` ~> 0.11.0
- `hashicorp/helm` ~> 3.2.0
- `hashicorp/kubernetes` ~> 3.2.1
- `kreuzwerker/docker` ~> 4.5.0

### 4.2 `backend.tf`
Backend local para simplificar. Inclui comentários orientando a migração para backend remoto.

### 4.3 `variables.tf`
Variáveis centralizadas para ambiente, cluster, registry e PostgreSQL.

### 4.4 `main.tf`
Orquestra os três módulos e calcula o caminho do kubeconfig.

### 4.5 `outputs.tf`
Exibe:
- Nome do cluster e caminho do kubeconfig.
- Comando kubectl.
- URL do registry local.
- Namespace e service name do PostgreSQL.
- String de conexão (sensível).
- Próximos passos após o provisionamento.

---

## 5. Validação

### 5.1 Formatação

```bash
terraform fmt -recursive
```

Resultado: arquivos formatados com sucesso.

### 5.2 Inicialização

```bash
terraform init
```

Resultado: providers baixados com sucesso, backend local configurado.

### 5.3 Validação sintática

```bash
terraform validate
```

Resultado: `Success! The configuration is valid.`

### 5.4 Plano de execução

```bash
terraform plan -var-file=environments/local.tfvars
```

Resultado: `Plan: 4 to add, 0 to change, 0 to destroy.`

Recursos planejados:
- `module.cluster.kind_cluster.this`
- `module.registry.docker_container.this`
- `module.database.kubernetes_namespace_v1.this`
- `module.database.helm_release.postgres`

### 5.5 Arquivos de ambiente
- `environments/local.tfvars`: configuração para ambiente local.
- `environments/production.tfvars.example`: exemplo com orientações para cloud.

---

## 6. Notas de portabilidade para nuvem

Para migrar para AWS, por exemplo, as alterações seriam:

1. **`modules/cluster`**: substituir `kind_cluster` por módulo `terraform-aws-modules/eks/aws`.
2. **`modules/database`**: substituir `helm_release` postgresql por módulo `terraform-aws-modules/rds/aws`.
3. **`modules/registry`**: substituir `docker_container` registry por módulo `terraform-aws-modules/ecr/aws`.
4. **`backend.tf`**: migrar para backend S3 + DynamoDB.
5. Adicionar módulos para VPC, subnets, security groups e IAM.

A raiz (`main.tf`, `variables.tf`, `outputs.tf`) permanece praticamente inalterada, desde que os módulos preservem suas interfaces de entrada e saída.

---

## 7. Ajustes no projeto

- `.gitignore` atualizado para ignorar:
  - `infra/.terraform/`
  - `infra/*.tfstate`
  - `infra/.terraform.lock.hcl`
  - `infra/kubeconfig`
  - `infra/crash.log`

---

## 8. Próximos passos

- Etapa 6: criar/evoluir pipeline CI/CD em `.github/workflows/`.
- Adicionar Alembic ao projeto e à imagem Docker.
- Atualizar `README.md` com instruções de uso do Terraform.
