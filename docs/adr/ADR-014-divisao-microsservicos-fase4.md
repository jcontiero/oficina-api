# ADR-014: Divisão em Três Microsserviços de Negócio e Fronteiras de Autenticação (Fase 4)

- **Data:** 2026-11-16
- **Status:** Aceito (Fase 4 — Etapa P1)
- **Contexto:** O enunciado da Fase 4 exige refatorar a aplicação em no mínimo 3 microsserviços independentes, cada um com seu próprio repositório, infraestrutura, pipeline de CI/CD e banco de dados exclusivo, proibindo o acesso direto de um serviço ao banco de dados de outro. Na Fase 3, embora existissem 4 repositórios (`oficina-api`, `oficina-serverless`, `oficina-k8s-infra` e `oficina-database-infra`), as regras de negócio de atendimento, orçamento e execução permaneciam concentradas em `oficina-api` e a Cloud Function de autenticação consultava diretamente a tabela `clientes` do PostgreSQL.

## Decisão

1. **Três Microsserviços de Negócio Independentes:**
   - **OS Service (`oficina-api`):** Responsável pelo cadastro de clientes, veículos, usuários administrativos, abertura e ciclo de vida público da Ordem de Serviço (`OrdemDeServico`, `HistoricoOS`), projeções de leitura de orçamento/execução, relatórios sobre histórico local e **Orquestrador da Saga** (`saga_instances`, `saga_steps`). Único escritor do status público da OS.
   - **Billing Service (`oficina-billing` — novo repositório):** Responsável pela geração e versionamento de orçamentos com preços congelados em centavos (`total_centavos`), decisão do cliente (aprovação/recusa), criação de cobranças QR dinâmico no Mercado Pago, recebimento e validação de webhooks (`x-signature`), reconciliação ativa e estorno/cancelamento financeiro.
   - **Execução e Produção Service (`oficina-execucao` — novo repositório):** Responsável pelo catálogo de serviços, estoque de peças, reservas atômicas por `saga_id`, fila de execução, diagnóstico/laudo técnico, apontamento de tarefas pelos mecânicos e comunicação de início/conclusão de reparos.

2. **Componentes de Suporte (Não Contabilizados entre os 3 Microsserviços):**
   - Os repositórios de infraestrutura (`oficina-k8s-infra` e `oficina-database-infra`) e o repositório `oficina-serverless` (Cloud Functions de Autenticação CPF/JWKS e Notificações por e-mail + API Gateway) permanecem como suporte operacional.

3. **Eliminação do Acesso Cruzado na Autenticação e Contrato RS256 Unificado:**
   - A Cloud Function `oficina-auth-function` deixa de acessar o PostgreSQL (`DATABASE_URL` removido) e passa a consultar `POST /internal/clientes/autenticacao` no OS Service via VPC Connector + Internal Load Balancer HTTPS, autenticada com Google OIDC ID Token da Service Account dedicada.
   - **Emissão Assimétrica RS256 para Clientes e Funcionários:**
     - Clientes: JWT RS256 emitido pela Function (`iss=oficina-auth-{env}`, JWKS público em `/.well-known/jwks.json`).
     - Funcionários (`ADMIN`/`MECANICO`): login mantido em `POST /auth/login` no OS Service, migrando de `HS256` para `RS256` (`iss=oficina-admin-{env}`, JWKS público em `/.well-known/admin-jwks.json`).
     - Audience única por ambiente: `aud=oficina-backend-{env}`.
     - `oficina-billing` e `oficina-execucao` recebem apenas as URLs/chaves públicas JWKS configuradas estaticamente por emissor, sem compartilhamento de `SECRET_KEY` simétrica.

## Consequências

- **Positivas:** Desacoplamento real de deploy, escalabilidade e persistência por contexto delimitado (DDD); eliminação total de queries SQL cruzadas entre serviços e funções; revogação e rotação de chaves via `kid` sem segredo simétrico compartilhado.
- **Trade-offs:** Consistência eventual entre os três serviços coordenada via Saga e eventos versionados no Pub/Sub; necessidade de manter adaptadores/rotas de compatibilidade durante a transição.
