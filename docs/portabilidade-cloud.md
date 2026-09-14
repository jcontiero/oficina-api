# Portabilidade e Migração para Cloud

**Projeto:** Oficina Mecânica API  
**Status Atual:** Ambiente de desenvolvimento local (Docker, Kubernetes via `kind`, banco via `helm`, Terraform com providers locais).  
**Avaliação de Portabilidade:** Altíssima (Cloud-Native / 12-Factor App)

Este documento descreve como a arquitetura atual permite uma transição natural e de baixo esforço para provedores de nuvem pública (AWS, Azure, GCP).

---

## 1. Por que a aplicação é portátil?

A aplicação foi concebida sob as práticas de *Cloud-Native* e *12-Factor App*, o que garante alta portabilidade devido aos seguintes pilares:

### Aplicação (FastAPI + Docker)
- **Agnóstica ao Host:** Embalada em uma imagem Docker enxuta baseada em `python:3.12-slim`. Sem dependências amarradas ao sistema operacional do host.
- **Configurações Dinâmicas:** Todo o comportamento variável (credenciais de banco, chaves JWT, SMTP) é injetado estritamente via Variáveis de Ambiente, permitindo plugar novos serviços em nuvem sem alterar uma linha de código Python.

### Kubernetes (`/k8s`)
- **APIs Nativas:** Foram utilizados recursos oficiais do Kubernetes (`Deployment`, `Service`, `HPA`, `Secret`, `ConfigMap`).
- **Sem Amarras de Armazenamento Host:** Não existem volumes `hostPath` que "amarram" o container a uma máquina específica.

### Infraestrutura como Código (`/infra`)
- **Arquitetura Modular:** O arquivo `main.tf` apenas invoca módulos isolados (`modules/cluster`, `modules/database`). Trocar a tecnologia do cluster significa alterar o conteúdo do módulo, sem quebrar o ecossistema.

---

## 2. Exemplos Práticos de Migração (Cenário: AWS)

Se a decisão for hospedar o projeto na Amazon Web Services (AWS), o esforço do time de DevOps consistirá nas seguintes adaptações modulares:

### Exemplo A: Terraform (Migrando de `kind` para EKS e RDS)

O arquivo principal `infra/main.tf` manteria sua assinatura estrutural, mas o interior dos módulos seria atualizado.

**Antes (Local):**
```hcl
module "cluster" {
  source = "./modules/cluster" # Usa o provider tehcyx/kind
  cluster_name = "oficina-api"
}

module "database" {
  source = "./modules/database" # Usa Helm para subir o banco dentro do cluster
}
```

**Depois (AWS):**
```hcl
module "cluster" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"
  cluster_name = "oficina-api-eks"
  vpc_id = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
}

module "database" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"
  identifier = "oficina-db-rds"
  engine = "postgres"
  engine_version = "16.1"
  instance_class = "db.t4g.micro"
}
```

### Exemplo B: Kubernetes (Ajustes de Ingress e Banco)

Com o banco de dados rodando de forma gerenciada na nuvem (RDS), o Kubernetes fica focado apenas no processamento (API).

1. **Remoção do Banco Interno:** Apagam-se os arquivos `postgres-deployment.yaml`, `postgres-service.yaml` e `pvc.yaml` do diretório `/k8s/`.
2. **Atualização do Secret:** O `k8s/secret.yaml` passa a receber o _endpoint_ fornecido pelo RDS no campo `DATABASE_URL`.
3. **Exposição para a Web (Ingress):** Cria-se um `ingress.yaml` usando o controlador nativo da nuvem (AWS ALB Ingress Controller).

**Exemplo de `ingress.yaml` para AWS:**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: oficina-api-ingress
  namespace: oficina-api
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
spec:
  ingressClassName: alb
  rules:
    - host: api.oficina.com.br
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: oficina-api
                port:
                  number: 8000
```

### Exemplo C: Pipeline CI/CD (Migrando para AWS ECR)

O fluxo automatizado de integração e deploy (GitHub Actions) ganharia etapas de autenticação na nuvem para realizar o push da imagem para um _container registry_ privado.

**Adição no `.github/workflows/build.yml` antes do Deploy:**
```yaml
      - name: Configurar credenciais AWS
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Login no Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and Push Docker Image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: oficina-api
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
```

---

## Conclusão

A transição de **Local para Nuvem** neste projeto não exige refatoração de código de software (nenhum script Python precisa ser modificado). O esforço foca unicamente em **trocar as peças de infraestrutura**, plugar as interfaces correspondentes e atualizar credenciais, provando a maturidade arquitetônica atingida na Fase 2.
