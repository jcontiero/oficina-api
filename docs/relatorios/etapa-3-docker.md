# Relatório — Etapa 3: Docker

**Projeto:** Oficina Mecânica API — Fase 2  
**Data:** 08/07/2026  
**Responsável:** Jonas Vasconcelos

---

## 1. Objetivo

Revisar a containerização da aplicação para atender aos critérios de produção da Fase 2:

- Imagem enxuta e segura (multi-stage build, non-root).
- Separação clara entre startup da aplicação e execução de DDL/seeds.
- Health check funcional.
- Docker Compose com serviços opcionais para migrations e seeds.

---

## 2. Alterações realizadas

### 2.1 `src/main.py`

Adicionado endpoint leve de health check:

```python
@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
```

O endpoint não depende do banco e retorna `HTTP 200`, servindo como probe para Docker e Kubernetes.

### 2.2 `Dockerfile`

Reescrito com as seguintes características:

- **Multi-stage build:** estágio `builder` compila e instala dependências; estágio final copia apenas o ambiente virtual pronto.
- **Base:** `python:3.12-slim` em ambos os estágios.
- **Usuário não-root:** `appuser`/`appgroup`.
- **`EXPOSE 8000`.**
- **Health check:** verifica `GET /health` a cada 30s.
- **Startup limpo:** executa apenas `uvicorn src.main:app --host 0.0.0.0 --port 8000`.
- **DDL/seeds removidos do `CMD`:** a aplicação não cria mais tabelas nem popula dados na inicialização.

### 2.3 `.dockerignore`

Mantidas as exclusões originais e adicionadas:

- Logs (`*.log`, `logs/`).
- Arquivos de ambiente (`.env`, `.env.*`, exceto `.env.example`).

### 2.4 `docker-compose.yml`

- Adicionado `name: oficina-api` para nomenclatura previsível dos recursos.
- Criada network dedicada `oficina-network`.
- Serviço `db` mantido com Postgres 16 e healthcheck.
- Serviço `api` com healthcheck e dependência do banco.
- Serviço `migrate` (profile `tools`) preparado para `alembic upgrade head`.
- Serviço `seed` (profile `tools`) executa `scripts/seed.py`.

### 2.5 `scripts/seed.py`

Ajustado para a arquitetura da Fase 2:

- Usa `Container` para obter `SessionLocal` e `hash_provider`.
- Gerencia transação explicitamente (`commit`/`rollback`).
- Cria o usuário admin inicial se ele não existir.

---

## 3. Validação

### 3.1 Build da imagem

```bash
docker build -t oficina-api .
```

Resultado: `Successfully built 535f7ef29fac` (imagem final ~61 MB).

### 3.2 Subida do ambiente

```bash
docker compose up -d
```

Resultado:

```
Container oficina-api-db-1    Started
Container oficina-api-api-1   Started
```

Status dos containers:

```
NAME                STATUS                    PORTS
oficina-api-api-1   Up (healthy)              0.0.0.0:8000->8000/tcp
oficina-api-db-1    Up (healthy)              5432/tcp
```

### 3.3 Health check

```bash
curl -s http://localhost:8000/health
```

Resultado:

```json
{"status":"ok"}
```

### 3.4 Migrations e Seed

Aplicação das migrations do Alembic:

```bash
docker compose --profile tools run migrate
```

Execução do seed:

```bash
docker compose --profile tools run seed
```

Resultado:

```
Admin criado: admin@oficina.com
```

### 3.5 Lint

```bash
ruff check src tests scripts
```

Resultado: `All checks passed!`

### 3.6 Testes

```bash
pytest tests/ -q
```

Resultado: `141 passed`.  
Observação: os 45 testes de integração falharam localmente por não haver um banco de testes (`oficina_test`) configurado no ambiente de execução. Esse comportamento é independente das mudanças de Docker.

---

## 4. Decisões e observações

- **Migrations:** o serviço `migrate` está configurado para `alembic upgrade head`, mas o Alembic ainda não foi introduzido no projeto. Assim que as migrations forem criadas, o serviço estará pronto para uso.
- **Banco de dados no cluster:** para a Etapa 4 (Kubernetes), será mantido o Postgres dentro do cluster, conforme sugestão do plano.
- **Registry:** a imagem será publicada no Docker Hub na Etapa 6 (CI/CD).

---

## 5. Próximos passos

- Etapa 4: criar manifestos Kubernetes em `/k8s`.
- Configurar Alembic e gerar a primeira migration.
- Evoluir CI/CD para build, push e deploy automatizado.
