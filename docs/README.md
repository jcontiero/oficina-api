# Documentação da Oficina Fase 4

A aplicação foi dividida em três microsserviços: OS e orquestração da Saga, Billing e Execução. Este índice reúne as decisões, contratos e instruções de operação da arquitetura distribuída.

## Arquitetura e contratos

- [Divisão dos microsserviços](adr/ADR-014-divisao-microsservicos-fase4.md).
- [Bancos por serviço SQL e NoSQL](adr/ADR-015-bancos-por-servico-sql-nosql.md).
- [Saga orquestrada e compensações](adr/ADR-016-saga-orquestrada-e-compensacoes.md).
- [Outbox Inbox e idempotência](adr/ADR-017-mensageria-outbox-inbox-idempotencia.md).
- [Mercado Pago Orders e QR dinâmico](adr/ADR-018-integracao-mercadopago-orders-qr.md).
- [OpenAPI dos contratos](contratos/openapi-fase4-contratos-v1.json), [envelope](contratos/schemas/envelope-v1.schema.json), [comandos](contratos/schemas/comandos-saga-v1.schema.json) e [eventos](contratos/schemas/eventos-saga-v1.schema.json).
- [Fixtures do fluxo e compensação](contratos/fixtures/fluxo-feliz-e-compensacao-v1.json).

## Operação e qualidade

- [Infraestrutura e instruções de implantação](https://github.com/jcontiero/oficina-k8s-infra).
- [Cobertura e evidências de testes](relatorios/relatorio-cobertura-testes.md).


## Organização

| Diretório | Conteúdo |
| --- | --- |
| `adr/` | Decisões arquiteturais e propostas da evolução do sistema |
| `contratos/` | OpenAPI JSON Schemas e fixtures |
| `diagramas/` | Diagramas históricos anteriores à divisão de domínios |
| `modelagem/` | Fontes Excalidraw de contexto domínio e event storming |
| `aux/` | Exemplos HTTP e requisitos das fases anteriores |
| `relatorios/` | Cobertura de testes e relatórios de segurança |

## Responsabilidades de domínio

| Domínio | Serviço responsável | Persistência |
| --- | --- | --- |
| Clientes veículos OS histórico e Saga | oficina-api | PostgreSQL exclusivo de OS |
| Orçamento aprovação cobrança e estorno | oficina-billing | PostgreSQL exclusivo de Billing |
| Catálogo peças reservas diagnóstico e reparo | oficina-execucao | Firestore Native exclusivo de Execução |

Os serviços usam REST para operações síncronas e Pub/Sub para comandos e eventos. Nenhum serviço acessa diretamente o banco de outro. OS e Billing compartilham a instância física Cloud SQL, com bancos lógicos e usuários isolados. As fontes das decisões atuais são os ADRs 014 a 018; os documentos das fases anteriores devem ser lidos como histórico.
