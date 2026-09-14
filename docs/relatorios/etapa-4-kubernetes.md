# Relatório — Etapa 4: Kubernetes

**Projeto:** Oficina Mecânica API — Fase 2  
**Data:** 08/07/2026  
**Responsável:** Jonas Vasconcelos

---

## 1. Objetivo

Criar os manifestos Kubernetes em `/k8s` para orquestrar a API e o banco de dados PostgreSQL no cluster, seguindo as boas práticas de produção definidas no plano da Fase 2.

---

## 2. Estrutura criada

```
k8s/
├── namespace.yaml
├── configmap.yaml
├── secret.yaml
├── deployment.yaml
├── service.yaml
├── hpa.yaml
├── job-migrate.yaml
├── pvc.yaml
├── postgres-deployment.yaml
├── postgres-service.yaml
└── ingress.yaml
```

---

## 3. Detalhes dos manifestos

### 3.1 `namespace.yaml`

Namespace isolado `oficina-api` para agrupar todos os recursos da aplicação.

### 3.2 `configmap.yaml`

Variáveis não sensíveis:

- `ALGORITHM`, `TOKEN_EXPIRE_HORAS`
- `SMTP_HOST`, `SMTP_PORT`
- `EMAIL_REMETENTE`, `EMAIL_ADMIN`
- `ADMIN_EMAIL`

### 3.3 `secret.yaml`

Variáveis sensíveis codificadas em base64 (placeholders):

- `DATABASE_URL` apontando para o serviço `postgres:5432`
- `SECRET_KEY`
- `SMTP_USER`, `SMTP_PASSWORD`
- `ADMIN_SENHA`

> **Atenção:** os valores são placeholders e devem ser substituídos por secrets reais antes do deploy em produção.

### 3.4 `pvc.yaml`

PersistentVolumeClaim de 5Gi para persistência dos dados do PostgreSQL.

### 3.5 `postgres-deployment.yaml` e `postgres-service.yaml`

- PostgreSQL 16 rodando no cluster.
- Volume montado em `/var/lib/postgresql/data`.
- Probes de liveness e readiness com `pg_isready`.
- Service ClusterIP chamado `postgres` na porta 5432.

### 3.6 `deployment.yaml`

Deployment da API com:

- `replicas: 2`
- Estratégia `RollingUpdate` com `maxUnavailable: 0`
- Imagem `oficina-api:v0.2.0` (tag fixa)
- `securityContext` com usuário não-root
- `resources` (requests e limits)
- `livenessProbe` e `readinessProbe` em `/health`
- Variáveis vindas do ConfigMap e do Secret

### 3.7 `service.yaml`

Service ClusterIP `oficina-api` expondo a porta 80 e direcionando para a porta 8000 dos pods.

### 3.8 `hpa.yaml`

HorizontalPodAutoscaler com:

- `minReplicas: 2`
- `maxReplicas: 10`
- Escalonamento por CPU (70%) e memória (80%)
- Janela de estabilização de 300s no scale down

### 3.9 `job-migrate.yaml`

Job para execução das migrations com `alembic upgrade head`. O job utiliza a mesma imagem e variáveis da API.

> **Observação:** o Alembic ainda não foi introduzido no projeto. O job está preparado para quando as migrations forem criadas.

### 3.10 `ingress.yaml`

Manifesto opcional e comentado, pronto para ser habilitado quando houver um Ingress Controller no cluster.

---

## 4. Validação

### 4.1 Validação sintática (dry-run)

```bash
kubectl apply -f k8s/ --dry-run=client
```

Resultado: todos os 9 manifestos validados com sucesso.

### 4.2 Aplicação no cluster

Cluster utilizado: minikube profile `oficina` (Kubernetes v1.35.1).

```bash
kubectl apply -f k8s/
```

Resultado:

```
namespace/oficina-api created
deployment.apps/postgres created
service/postgres created
persistentvolumeclaim/postgres-pvc created
secret/oficina-api-secret created
service/oficina-api created
configmap/oficina-api-config created
deployment.apps/oficina-api created
horizontalpodautoscaler.autoscaling/oficina-api-hpa created
job.batch/oficina-api-migrate created
```

### 4.3 Status dos pods

```
NAME                          READY   STATUS    RESTARTS   AGE
oficina-api-674cccf84-65r8x   1/1     Running   0          16s
oficina-api-674cccf84-ktcfh   1/1     Running   0          16s
postgres-6b5cd7d954-6swhc     1/1     Running   0          2m31s
```

### 4.4 Health check

```bash
kubectl port-forward -n oficina-api svc/oficina-api 8080:80
curl -s http://localhost:8080/health
```

Resultado:

```json
{"status":"ok"}
```

### 4.5 Job de migrate

O job foi criado corretamente, mas falhou ao executar porque o comando `alembic` ainda não está disponível na imagem (Alembic não configurado). O erro esperado foi:

```
exec: "alembic": executable file not found in $PATH
```

Assim que o Alembic for adicionado ao projeto e à imagem, o job funcionará.

---

## 5. Decisões e observações

- **Banco de dados:** mantido dentro do cluster (PostgreSQL), conforme sugestão do plano para ambiente local/kind.
- **Imagem:** utilizada tag fixa `v0.2.0`. A pipeline de CI/CD (Etapa 6) deverá buildar e publicar essa imagem no Docker Hub.
- **Secrets:** valores são placeholders base64. Em produção, deve-se usar um gerenciador de secrets ou injeção via CI/CD.
- **Ingress:** deixado comentado para evitar dependência de um Ingress Controller específico.

---

## 6. Próximos passos

- Etapa 5: criar infraestrutura como código em `/infra` com Terraform.
- Configurar Alembic e gerar a primeira migration.
- Evoluir CI/CD para build, push e deploy automatizado.
