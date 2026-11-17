# ADR-015: Bancos de Dados por Serviço — Isolamento Poliglota SQL (PostgreSQL) e NoSQL (Firestore)

- **Data:** 2026-11-16
- **Status:** Aceito (Fase 4 — Etapa P1)
- **Contexto:** A Fase 4 exige que cada microsserviço possua banco de dados próprio, sendo obrigatório o uso de pelo menos um banco relacional (SQL) e pelo menos um banco não relacional (NoSQL), sem qualquer acesso direto ao banco de outro serviço. Ao mesmo tempo, o projeto roda em conta acadêmica/desafio na GCP, exigindo contenção de custos de infraestrutura.

## Decisão

1. **Persistência Poliglota por Serviço e Ambiente (`homolog` e `production`):**
   - **OS Service (`oficina-api`) → SQL (PostgreSQL 16):**
     - Databases exclusivos: `oficina_os_homolog` e `oficina_os_production`.
     - Usuário dedicado: `oficina_os_user_{env}` com `CONNECT` e `GRANT` restritos exclusivamente ao seu banco lógico.
     - Tabelas: `clientes`, `veiculos`, `usuarios`, `ordens_de_servico`, `historico_os`, `saga_instances`, `saga_steps`, `inbox_eventos`, `outbox_eventos`.
   - **Billing Service (`oficina-billing`) → SQL (PostgreSQL 16):**
     - Databases exclusivos: `oficina_billing_homolog` e `oficina_billing_production`.
     - Usuário dedicado: `oficina_billing_user_{env}` sem permissão de conexão ao banco do OS.
     - Tabelas: `orcamentos`, `orcamento_itens`, `pagamentos`, `provider_operations`, `webhook_inbox`, `saga_tombstones`, `inbox_eventos`, `outbox_eventos`. Sem chaves estrangeiras para tabelas do OS.
   - **Execução Service (`oficina-execucao`) → NoSQL (Google Cloud Firestore Native Mode):**
     - Bancos Firestore nomeados exclusivos: `oficina-execucao-homolog` e `oficina-execucao-production`.
     - Service Account exclusiva (`oficina-execucao-sa-{env}`) com papel IAM restrito ao Firestore do respectivo ambiente.
     - Coleções: `servicos/{id}`, `pecas/{id}`, `diagnosticos/{os_id_rodada}`, `reservas/{saga_id}`, `execucoes/{os_id_rodada}`, `controle_saga/{saga_id}`, `inbox/{consumer_event_id}`, `outbox/{event_id}`.

2. **Interpretação de "Infraestrutura Própria" com Custo Contido:**
   - "Infraestrutura própria" de cada microsserviço é atendida por Deployments, Services, HPAs, ConfigMaps, Secrets, Service Accounts (Workload Identity), pipelines CI/CD, states Terraform e bancos de dados lógicos/nomeados exclusivos por serviço.
   - O cluster GKE (`oficina-gke-cluster`) e a instância gerenciada Cloud SQL (`oficina-postgres-db`) atuam como plataforma compartilhada na conta GCP, evitando triplicar o custo fixo de instâncias de VM/SQL. Caso seja exigido isolamento físico de instâncias SQL, basta apontar o `DATABASE_URL` do serviço para outra instância sem qualquer alteração de código ou contrato.

3. **Transações Atômicas no Firestore e Representação Monetária:**
   - No Firestore (`oficina-execucao`), a verificação de documento de controle (`controle_saga/{saga_id}`), dedução/reserva de saldo em `pecas/{id}`, gravação de `reservas/{saga_id}`, registro em `inbox` e enfileiramento em `outbox` ocorrem dentro de uma única transação Firestore (`@firestore.transactional`), sem chamadas externas (HTTP/PubSub) dentro da função transacional.
   - Valores monetários em todos os novos contratos e tabelas de Billing são armazenados como inteiros em centavos (`total_centavos`, `preco_unitario_centavos`) com moeda explícita (`BRL`), convertidos via `Decimal` apenas na fronteira HTTP com o Mercado Pago.

## Consequências

- **Positivas:** Atendimento estrito ao requisito SQL + NoSQL; garantia criptográfica/IAM e de credenciais de banco impedindo acesso cruzado; transações ACID tanto nos bancos relacionais quanto nas reservas de estoque multi-documento do Firestore.
- **Trade-offs:** Proibição de `JOIN` SQL entre OS, Orçamento e Catálogo/Estoque, exigindo envio de snapshots imutáveis nos eventos da Saga.
