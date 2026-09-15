# Runbook: Deploy, Healthcheck e Rollback da Aplicação no GKE

## 1. Estratégia de Deploy (Zero-Downtime Rolling Update)
A aplicação `oficina-api` utiliza a estratégia de **Rolling Update** no Kubernetes com:
- `maxSurge: 1`
- `maxUnavailable: 0`
- Pelo menos **2 réplicas** ativas.

### Ordem de Execução do Deploy:
1. **Migrations**: Execução isolada do Job `oficina-api-migrate` (`alembic upgrade head`).
2. **Rollout da Aplicação**: Atualização da imagem do Deployment `oficina-api`.
3. **Readiness Probe**: O Kubernetes só direciona tráfego para os novos Pods após o endpoint `/health/ready` responder `200 OK` (validando conectividade ativa com o Cloud SQL).

## 2. Probes de Healthcheck
- **Liveness Probe** (`GET /health/live`): Verifica se o processo Uvicorn/FastAPI está responsivo.
- **Readiness Probe** (`GET /health/ready`): Executa `SELECT 1` no banco de dados. Se o banco falhar, o Pod para de receber tráfego temporariamente sem ser reiniciado desnecessariamente.

## 3. Estratégia de Rollback N-1 (Requisito R-07)
Todas as migrações de banco de dados adotam a estratégia **expand/contract**:
- Novas colunas são criadas como anuláveis (`nullable=True`) ou com valores `default`.
- Nenhuma coluna ou tabela é removida no mesmo release em que o código para de usá-la.

### Procedimento de Rollback no GKE:
Caso a nova versão da aplicação (`vN`) apresente instabilidade após o deploy:

1. **Reverter a versão do Deployment**:
   ```bash
   kubectl rollout undo deployment/oficina-api -n production
   ```
2. **Acompanhar o status da reversão**:
   ```bash
   kubectl rollout status deployment/oficina-api -n production
   ```
3. **Compatibilidade de Schema**:
   - A versão anterior (`vN-1`) continuará operando normalmente sobre o schema do banco (`schema N`), sem necessidade de `alembic downgrade`.
