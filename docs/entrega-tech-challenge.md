# Tech Challenge - Fase 3
## Sistema Integrado de Atendimento e Execução de Serviços (Oficina Mecânica)

**Aluno(a):** Jonas Contiero Vasconcellos
**Usuário de Avaliação Adicionado:** `soat-architecture` (Convidado nos 4 repositórios)

---

## 1. Repositórios de Código

O sistema monolítico foi fragmentado de acordo com as melhores práticas de domínio e operação, resultando nos seguintes 4 repositórios (cada um contendo sua própria pipeline de CI/CD):

1. **Aplicação Principal (API e Worker)**: [https://github.com/jcontiero/oficina-api](https://github.com/jcontiero/oficina-api)
2. **Infraestrutura GKE e Datadog (Terraform)**: [https://github.com/jcontiero/oficina-k8s-infra](https://github.com/jcontiero/oficina-k8s-infra)
3. **Infraestrutura Cloud SQL e Secrets (Terraform)**: [https://github.com/jcontiero/oficina-database-infra](https://github.com/jcontiero/oficina-database-infra)
4. **Serverless Auth, Notificações e Gateway**: [https://github.com/jcontiero/oficina-serverless](https://github.com/jcontiero/oficina-serverless)

---

## 2. Vídeo de Demonstração

O vídeo contendo a demonstração de ponta-a-ponta (autenticação por CPF, pipeline CI/CD de homolog/prod, GKE com HPA, mensageria serverless, e dashboards do Datadog) pode ser acessado no link abaixo:

🔗 **Link do Vídeo (YouTube):** `[COLE_O_LINK_DO_SEU_VIDEO_AQUI]`

---

## 3. Documentação Arquitetural e Decisões

As justificativas técnicas e diagramas foram consolidadas nos seguintes documentos no repositório da aplicação principal:

### 3.1. Desenhos Arquiteturais e Modelagem
- **[Diagrama de Componentes (Cloud, APIs, Monitoramento)](https://github.com/jcontiero/oficina-api/blob/main/docs/diagrama-componentes.md)**
- **[Diagrama de Sequência (Autenticação e Abertura de OS)](https://github.com/jcontiero/oficina-api/blob/main/docs/diagrama-sequencia.md)**
- **[Diagrama ER, Modelagem Relacional e Justificativa de BD](https://github.com/jcontiero/oficina-api/blob/main/docs/diagrama-er.md)**

### 3.2. Registros de Decisões Arquiteturais (ADRs)
- [ADR-004: GKE e topologia dos ambientes](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-004-gke.md)
- [ADR-005: Cloud SQL PostgreSQL](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-005-cloud-sql-postgresql.md)
- [ADR-006: Assinatura e rotação de JWT RS256](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-006-jwt-rs256-kms-jwks.md)
- [ADR-007: Autorização por Principal](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-007-autorizacao-por-principal.md)
- [ADR-008: Histórico Append-only](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-008-historico-status.md)
- [ADR-009: Padrão Outbox e Pub/Sub](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-009-outbox-pubsub.md)
- [ADR-010: HPA e Disponibilidade](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-010-hpa-e-disponibilidade.md)
- [ADR-011: Observabilidade Datadog](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-011-datadog.md)
- [ADR-012: State Terraform GCS](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/ADR-012-state-terraform.md)

### 3.3. Request for Comments (RFCs de Faseamento)
- [RFC-001: Justificativa GCP](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/RFC-001-provedor-gcp.md)
- [RFC-002: Autenticação CPF e Mitigação](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/RFC-002-autenticacao-cpf.md)
- [RFC-003: API Gateway GKE](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/RFC-003-api-gateway-gke.md)
- [RFC-004: Separação de Repositórios](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/RFC-004-separacao-repositorios.md)
- [RFC-005: Notificações Serverless (Outbox)](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/RFC-005-notificacoes-serverless.md)
- [RFC-006: Retenção e Sampling de Observabilidade](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/RFC-006-observabilidade-datadog.md)
- [RFC-007: Migração e Downtime Mínimo DB](https://github.com/jcontiero/oficina-api/blob/main/docs/adr/RFC-007-migracao-cloud-sql.md)

---
