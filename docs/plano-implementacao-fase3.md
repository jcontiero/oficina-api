# Plano de implementação da Fase 3

**Projeto:** Sistema Integrado de Atendimento e Execução de Serviços  
**Objetivo:** orientar a implementação da Fase 3 por outro modelo, com tarefas pequenas, dependências explícitas e critérios verificáveis.  
**Baseline analisado:** repositório da Fase 2 em 14 de setembro de 2026.  
**Documentos normativos:** `docs/aux/requisitos-fase1.md`, `docs/aux/requisitos-fase2.md` e `docs/aux/requisitos-fase3.md`.

---

> **Revisão incorporada em 14 de setembro de 2026.**  
> Um modelo revisor independente executou análise estática deste plano confrontando-o com o código, os requisitos e a documentação oficial do GCP. Dez achados foram levantados. A tabela abaixo registra cada um, o diagnóstico e onde a correção foi incorporada. Nenhum arquivo de código foi alterado nessa revisão; apenas este plano foi atualizado.

| ID-Rev | Severidade | Achado | Diagnóstico | Incorporação |
|---|---|---|---|---|
| R-01 | Alta | Cloud Armor bypassável pela URL nativa do Gateway | Correto. A URL `*.gateway.dev` não pode ser desativada; a seção 4.1 já documentava isso. O plano não exigia explicitamente testes pela URL nativa nos critérios de aceite do Pacote 8. | Critério de aceite do Pacote 8 e seção 9.1 reforçados. |
| R-02 | Alta | JWT administrativo quebraria acesso de funcionários sem migração conjunta | Correto. O emissor atual (`casos_de_uso.py:24`) só emite `sub`, `perfil` e `exp`. A seção 5.2.1 já endereçava o problema, mas a instrução estava implícita. | Seção 5.2.1 expandida; tarefa do Pacote 2 tornada mais explícita. |
| R-03 | Alta | Remover commits pode quebrar CRUDs existentes se a Unit of Work não cobrir todos os casos de uso | Correto. A tarefa 8 do Pacote 0 já descrevia esse risco, mas não era suficientemente imperativa. | Tarefa 8 do Pacote 0 e critérios de aceite tornados mais explícitos. |
| R-04 | Alta | Caminho de rede da Function ao banco privado não especificado nem atribuído | Correto. O Serverless VPC Access connector estava listado no `oficina-k8s-infra` mas sem responsável explícito no Pacote 7 e sem referência cruzada ao Pacote 4. | Tarefa do Pacote 4 e tarefa 2 do Pacote 7 atualizadas com referência explícita ao connector e ao ADR de mecanismo. |
| R-05 | Alta | Semântica da deduplicação de notificações não declarava a janela residual de duplicação | Parcialmente correto. O Pacote 9 já definia deduplicação, retry e DLQ, mas a janela residual entre envio e registro estava implícita. | Pacote 9 expandido com semântica declarada explicitamente. |
| R-06 | Alta | Fluxo da ação por e-mail sem tarefa de implementação do link real | Correto. Os botões de aprovação/recusa têm `href="#"` atualmente e nenhuma tarefa exigia gerar e validar a credencial de ação. | Tarefa 7 adicionada ao Pacote 9; critério de aceite end-to-end reescrito. |
| R-07 | Alta | Rollback não condicionado à compatibilidade da migration | Incorreto como achado: a estratégia expand/contract e o smoke test da imagem N-1 já estavam na seção 11.2. O achado identifica a ausência de critério de aceite formal no Pacote 6. | Critério de aceite do Pacote 6 reforçado com referência explícita à seção 11.2. |
| R-08 | Média | Pipeline Terraform com `init -backend=false` confuso | Incorreto como achado: a seção 11.3 já separava Job 1 (validação estática) e Job 2 (plan autenticado). O formato dos blocos `bash` pode ter gerado ambiguidade. | Comentários nos blocos de código da seção 11.3 tornados mais explícitos. |
| R-09 | Média | Métricas não cobriam ciclos repetidos nem transições intermediárias na abertura | Correto. A seção 6.5 definia acumulação por ciclo, mas os testes obrigatórios estavam genéricos. | Regras de agregação da seção 6.5 e testes da seção 3.4 expandidos. |
| R-10 | Média | Dependências circulares ou futuras na ordem dos pacotes (CI/CD chega tarde, spike antes da infraestrutura) | Parcialmente correto. A tabela de ordem tinha dependências corretas, mas não detalhava como pacotes anteriores operam sem CI/CD final. | Pacote 3 reforçado com CI mínimo obrigatório desde o início; nota adicionada à seção 16. |



## 1. Como usar este documento

Este plano é a fonte de execução da Fase 3. O modelo implementador deve:

1. Ler este documento e os três arquivos de requisitos antes de alterar código.
2. Executar os pacotes na ordem indicada na seção 16.
3. Criar um branch e um Pull Request por pacote ou subpacote coeso.
4. Não misturar correções de fases anteriores com provisionamento cloud no mesmo PR.
5. Começar cada pacote pelos testes ou critérios de aceite correspondentes.
6. Não executar `terraform apply` em produção sem plano revisado e aprovação humana.
7. Não criar recursos cloud enquanto os identificadores, região, domínio, orçamento e credenciais não estiverem configurados.
8. Não registrar CPF, JWT, senhas, chaves ou strings de conexão em logs.
9. Não introduzir dependências de FastAPI, SQLAlchemy ou SDKs GCP nas camadas `dominio` e `aplicacao`.
10. Atualizar este documento quando uma decisão proposta for substituída por uma decisão aprovada.

Os estados usados nas matrizes são:

- **Atendido:** existe evidência estática suficiente no repositório.
- **Parcial:** há implementação, mas faltam garantias ou partes obrigatórias.
- **Não atendido:** o requisito está ausente ou não funciona de ponta a ponta.
- **Não comprovado:** há configuração, mas falta evidência operacional.

## 2. Decisões e propostas

### 2.1 Decisões confirmadas pelo responsável

Estas escolhas foram confirmadas pelo responsável do projeto e devem ser tratadas como fixas:

| Tema | Decisão |
|---|---|
| Provedor cloud | Google Cloud Platform (GCP) |
| Ambientes | Homologação e produção |
| Autenticação de cliente | CPF conforme o enunciado, com mitigação de enumeração e abuso |
| Observabilidade | Datadog |

### 2.2 Propostas técnicas deste plano

As escolhas abaixo foram propostas por este documento, não pelo responsável. O modelo implementador pode substituí-las se o spike ou a validação de custos justificar, registrando a mudança em ADR:

| Tema | Proposta |
|---|---|
| Banco | PostgreSQL 16 gerenciado no Cloud SQL |
| Kubernetes | Google Kubernetes Engine (GKE) |
| Serverless | Cloud Run functions, anteriormente chamadas Cloud Functions 2nd gen |
| API Gateway | GCP API Gateway, condicionado ao spike da seção 4.1 e à correção do achado da seção 4.2 |
| CI/CD | GitHub Actions |
| IaC | Terraform |
| Registro de imagens | Artifact Registry |
| Assinatura do JWT do cliente | RS256 com chave privada protegida no Cloud KMS e chave pública em JWKS |
| Eventos de notificação | Outbox transacional, Pub/Sub e Function consumidora |
| Proteção de borda | HTTPS Load Balancer com Cloud Armor, com os cuidados da seção 9.1 |

### 2.3 Decisões ainda pendentes

Estas decisões devem ser confirmadas antes do primeiro `terraform apply`:

| Decisão | Recomendação inicial | Consequência |
|---|---|---|
| Região GCP | `southamerica-east1` | Menor latência no Brasil, mas validar disponibilidade e preço dos serviços |
| Organização de projetos | Um projeto para homologação e outro para produção | Isolamento de IAM, quota, billing e impacto de falhas |
| Domínios | `api-homolog.<dominio>` e `api.<dominio>` | Necessários para TLS, issuer e URLs de demonstração |
| PF e PJ | Login por CPF somente para pessoa física | CNPJ exige conceito de representante, fora do requisito atual |
| Status de cliente | `ATIVO` e `INATIVO` | Deve ser criado no domínio e no banco |
| Resposta de acesso cruzado | `404` | Evita revelar a existência de OS de outro cliente |
| Expiração do JWT | 15 minutos | Reduz o impacto de token obtido indevidamente; não haverá refresh token nesta fase |
| E-mail | SendGrid ou provedor já contratado | GCP não oferece serviço transacional equivalente ao SES como requisito do projeto |
| Retenção Datadog | Definir por ambiente e orçamento | Logs podem ser o maior componente variável de custo |
| Topologia de homologação | GKE e Cloud SQL menores, sem HA regional | Reduz custo; produção mantém alta disponibilidade |
| Múltiplas unidades | Não criar `unidade_id` sem regra de negócio aprovada | O requisito contextual cita expansão, mas não define segregação funcional |

## 3. Resumo da auditoria das Fases 1 e 2

A aplicação possui os principais endpoints, uma estrutura próxima de Clean Architecture, testes, Docker, manifestos Kubernetes e Terraform local. Entretanto, há falhas de segurança e integridade anteriores que devem ser corrigidas antes da exposição pública na Fase 3.

### 3.1 Achados bloqueadores

| ID | Severidade | Achado | Evidência principal | Consequência |
|---|---|---|---|---|
| REV-01 | Crítica | Aprovação e recusa de orçamento são públicas | `src/atendimento/apresentacao/rotas.py:319-337` e `:476-502` | Alteração não autorizada de status e estoque |
| REV-02 | Crítica | Repositórios executam `commit()` individualmente | `src/atendimento/infraestrutura/repositorios.py:38-48`, `:99-118`, `:156-179` | Abertura e aprovação deixam estado parcial quando falham |
| REV-03 | Crítica | Reserva de estoque não possui controle de concorrência | `src/atendimento/aplicacao/casos_de_uso.py:683-690` | Duas réplicas podem consumir o mesmo saldo |
| REV-04 | Crítica | Quantidade negativa é aceita | `src/atendimento/apresentacao/schemas.py:99-101` e `src/estoque/dominio/entidades.py:15-22` | Estoque aumenta e orçamento diminui |
| REV-05 | Alta | Orçamento inicial não é persistido | `src/atendimento/infraestrutura/repositorios.py:165-174` | POST retorna valor que desaparece no GET |
| REV-06 | Alta | Veículo existente não é comparado ao cliente da abertura | `src/atendimento/aplicacao/casos_de_uso.py:637-641` | Uma OS pode misturar cliente e veículo de proprietários diferentes |
| REV-07 | Alta | Estados ativos estão incompletos | `src/atendimento/infraestrutura/repositorios.py:25-31` | Pode existir mais de uma OS ativa para o veículo |
| REV-08 | Alta | O fluxo unificado não envia o orçamento | `src/atendimento/aplicacao/casos_de_uso.py:602-604` | A OS fica aguardando aprovação sem notificação |
| REV-09 | Alta | Webhook de status não possui produtor do token/link | `src/atendimento/aplicacao/casos_de_uso.py:727-753` | Fluxo por e-mail não funciona de ponta a ponta |
| REV-10 | Alta | Perfis não estão corretamente restringidos | `src/catalogo/apresentacao/rotas.py` e `src/estoque/apresentacao/rotas.py` | MECANICO pode alterar preço e estoque |
| REV-11 | Alta | Deploy atual ocorre em `kind` efêmero no GitHub runner | `.github/workflows/build.yml:212-265` | Pipeline verde não representa ambiente ativo |
| REV-12 | Alta | Terraform não provisiona o PostgreSQL efetivo | `infra/modules/database/main.tf` | Requisito de banco via IaC ficou parcial |
| REV-13 | Alta | Migration Job tem nome fixo | `k8s/job-migrate.yaml` e `.github/workflows/build.yml:254-265` | Deploy seguinte pode não executar a migration |
| REV-14 | Alta | Imagem `latest` com `IfNotPresent` | `.github/workflows/build.yml:201-208` e `k8s/deployment.yaml` | Um rollout pode manter imagem antiga |
| REV-15 | Alta | Healthcheck não verifica dependências | `src/main.py:52-54` | Pod pode ficar pronto sem banco funcional |
| REV-16 | Alta (evolução Fase 3) | Não há histórico de status da OS | modelo e migration atuais | Não é não conformidade das fases 1-2; é pré-requisito novo para os dashboards da Fase 3 |
| REV-17 | Alta (evolução Fase 3) | Não há autorização por propriedade | `src/shared/dependencias.py` | Não é não conformidade das fases 1-2 (consulta pública era o contrato do MVP); é risco de segurança a resolver com a autenticação por CPF da Fase 3 |

### 3.2 Matriz da Fase 1

| Requisito | Estado | Observação |
|---|---|---|
| Identificação por CPF/CNPJ | Parcial | Existe, mas a abertura pode associar veículo de outro cliente |
| Cadastro de veículo | Atendido | Placa, marca, modelo e ano existem |
| Serviços na OS | Atendido | Itens são copiados do catálogo |
| Peças e insumos | Parcial | Falta validar quantidade positiva e garantir reserva atômica |
| Orçamento automático | Parcial | É calculado, mas não persistido na inserção inicial |
| Envio para aprovação | Parcial | Existe no fluxo legado, não na abertura unificada |
| Estados da OS | Parcial | Estados exigidos existem, acompanhados de estados internos adicionais |
| Mudança automática de estado | Atendido | Há transições de domínio |
| Consulta pelo cliente | Atendido no contrato da Fase 1 | Endpoint público por UUID existia por decisão do MVP; a autenticação por CPF da Fase 3 substituirá esse contrato e os testes que o consolidam |
| CRUD de clientes | Parcial | Remoção com histórico pode causar erro de integridade |
| CRUD de veículos | Parcial | Remoção com histórico pode causar erro de integridade |
| CRUD de serviços | Atendido | Falta revisar autorização e remoção em uso |
| CRUD de peças e estoque | Parcial | Falta consistência transacional e concorrência |
| Listagem e detalhamento de OS | Parcial | Listagem atual não cobre consulta histórica administrativa completa |
| Tempo médio de execução | Parcial | Cálculo atual inclui espera, diagnóstico e aprovação |
| JWT administrativo | Atendido | Login de funcionário por e-mail/senha existe |
| Validação CPF/CNPJ/placa | Atendido | Value objects possuem validação |
| Testes unitários e integração | Parcial | Há testes, mas faltam segurança, concorrência, rollback e migrations |
| Monólito em camadas | Atendido | Estrutura modular presente |
| Swagger | Atendido | Gerado pelo FastAPI |
| Dockerfile e Compose | Atendido estaticamente | Operação não foi reexecutada nesta auditoria |
| Cobertura mínima de 80% | Não comprovado nesta auditoria | Configuração e CI exigem 80%, mas este plano não reexecutou a suíte |

### 3.3 Matriz da Fase 2

| Requisito | Estado | Observação |
|---|---|---|
| Clean Architecture/Hexagonal | Parcial | Dependências internas estão razoavelmente isoladas; falta Unit of Work |
| Testes de fluxos críticos | Parcial | Faltam os cenários dos achados bloqueadores |
| Abertura unificada | Parcial | Endpoint existe, mas não é atômico |
| Consulta de status | Atendido | Contrato externo mapeia os estados |
| Aprovação/recusa externa | Parcial | Existe, mas é pública e não atômica |
| Listagem ordenada | Atendido | Prioridade e idade estão implementadas |
| Exclusão de finalizadas/entregues | Atendido | A listagem ativa também exclui canceladas |
| Atualização via e-mail | Parcial | Endpoint existe sem geração/envio do token |
| Docker | Atendido estaticamente | Multi-stage, usuário não-root e healthcheck estão presentes |
| Manifestos Kubernetes | Atendido estaticamente | Deployment, Services, ConfigMap, Secret e HPA existem |
| Terraform para cluster | Parcial | Apenas `kind` local |
| Terraform para banco | Não atendido efetivamente | O banco é aplicado por YAML fora do módulo Terraform |
| CI/CD completa | Parcial | Executa em ambiente efêmero e possui falhas de imagem/migration |

### 3.4 Testes ausentes que devem ser acrescentados

- POST seguido de GET preserva `valor_orcamento`.
- Quantidade zero ou negativa retorna `422`.
- Veículo de outro cliente é rejeitado.
- Falha após criar cliente/veículo desfaz toda a abertura.
- Falha na segunda peça desfaz a reserva da primeira.
- Aprovação repetida não reserva novamente.
- Duas aprovações concorrentes não deixam estoque negativo nem perdem atualização.
- MECANICO recebe `403` ao alterar catálogo ou estoque.
- Cliente A não consulta, aprova ou lista OS do cliente B.
- Token expirado, issuer incorreto, audience incorreta e assinatura inválida retornam `401`.
- Alembic sobe um banco vazio e o downgrade/upgrade imediato funciona.
- Readiness falha quando o banco está indisponível.
- Mudança de status e histórico são persistidos na mesma transação.
- Falha de publicação mantém o evento na outbox.
- Mensagem Pub/Sub duplicada não envia notificação duplicada (mesma mensagem publicada duas vezes gera um único envio).
- **[R-09] OS com duas recusas de orçamento**: dois ciclos de `EM_DIAGNOSTICO` acumulados corretamente na métrica (soma dos dois intervalos fechados, não apenas o último).
- **[R-09] Dois eventos com timestamp idêntico**: ordem preservada por `sequencia`, não por `ocorrido_em`.
- **[R-09] Abertura unificada**: todos os eventos intermediários (RECEBIDA → EM_DIAGNOSTICO → AGUARDANDO_ORCAMENTO → AGUARDANDO_APROVACAO) estão presentes no histórico, na ordem correta, na mesma transação.
- **[R-09] Intervalo aberto**: OS no status corrente não entra na média histórica; aparece apenas no painel "tempo parado agora".
- **[R-03] CRUDs compartilhados (cliente, veículo, peça) persistem alterações** verificadas em nova sessão de banco; a fixture de integração não pode mascarar a regressão reutilizando a mesma sessão entre escrita e leitura.


### 3.5 Rastreabilidade dos requisitos da Fase 3

| Requisito obrigatório | Implementação prevista | Responsável principal | Evidência de aceite |
|---|---|---|---|
| API Gateway | Seções 4.1, 8 e Pacote 8 | `oficina-serverless` e `oficina-k8s-infra` | URL pública, OpenAPI, testes de JWT e bloqueio de acesso direto |
| Rotas sensíveis protegidas | Seção 5 e Pacote 2 | `oficina-api` | Matriz CLIENTE/MECANICO/ADMIN automatizada |
| Function valida CPF | Seção 5.1 e Pacote 7 | `oficina-serverless` | Testes de CPF válido e inválido |
| Function consulta existência e status | Seções 5.1, 6.1 e Pacote 7 | `oficina-serverless` e `oficina-api` | Cliente ativo autentica; inexistente/inativo recebe resposta genérica |
| Function gera JWT | Seção 5.2 e Pacote 7 | `oficina-serverless` | Token RS256 validado pelo Gateway e pela API |
| Quatro repositórios | Seção 7 e Pacote 3 | Todos | URLs e READMEs dos quatro repositórios |
| CI/CD em todos os repositórios | Seção 11 e Pacote 11 | Todos | Workflows verdes de PR, homologação e produção |
| Branch principal protegida | Seção 11.1 | Todos | Screenshots/configuração da proteção |
| Pull Request obrigatório | Seção 11.1 | Todos | Push direto rejeitado |
| Deploy automático de homologação e produção | Seções 11.1-11.3 | Todos | Runs e deployments registrados por ambiente |
| Banco gerenciado | Seções 6, 8 e Pacote 5 | `oficina-database-infra` | Cloud SQL privado, backup e PITR |
| Kubernetes escalável | Seção 8 e Pacote 6 | `oficina-k8s-infra` e `oficina-api` | HPA funcional e teste de carga |
| Terraform | Seções 8.4 e 11.3 | Repositórios de infraestrutura e serverless | Plan/apply e state remoto separados |
| Datadog | Seção 10 e Pacote 10 | Plataforma, API e serverless | Integrações e dashboards ativos |
| Latência das APIs | Seção 10.4 | `oficina-api` | Dashboard p50/p95/p99 |
| CPU e memória do Kubernetes | Seção 10.4 | `oficina-k8s-infra` | Dashboard de recursos e HPA |
| Healthchecks e uptime | Seções 10.3-10.5 | `oficina-api` | Probes e teste sintético |
| Alerta de falha de OS | Seção 10.5 | `oficina-api` | Falha controlada dispara alerta |
| Logs JSON correlacionados | Seções 10.1-10.2 | API e serverless | Busca por correlation ID sem dados sensíveis |
| Volume diário de OS | Seção 10.4 | `oficina-api` | Dashboard comparado à query de referência |
| Tempo médio por status | Seções 6.2-6.5 e 10.4 | `oficina-api` | Dashboard de Diagnóstico, Execução e Finalização |
| Erros de integração | Seções 10.4-10.5 | API e serverless | Dashboard e monitores de banco, Pub/Sub e e-mail |
| Diagrama de componentes | Pacote 12 | `oficina-api` como índice central | Diagrama publicado e coerente com deploy |
| Sequências de autenticação e abertura de OS | Pacote 12 | `oficina-api` e `oficina-serverless` | Dois diagramas publicados |
| RFCs e ADRs | Seção 13 | Todos conforme decisão | Documentos versionados e interligados |
| Justificativa do banco e diagrama ER | Seções 6, 7.3 e 13 | `oficina-database-infra` | ADR, ER e dicionário de dados |
| Dockerfiles quando aplicáveis | Seção 7 | API e serverless se houver imagem customizada | Build reproduzível no CI |
| README por repositório | Pacotes 3 e 12 | Todos | Propósito, stack, execução, deploy, diagrama e links |
| Swagger/Postman | Pacotes 8 e 12 | `oficina-api` | URL do Swagger e collection apontando para o Gateway |
| Vídeo de até 15 minutos | Seção 15 | Entrega | Link público ou não listado |
| PDF único | Pacote 12 | Entrega | PDF com repositórios, vídeo, documentação e confirmação do usuário |

## 4. Arquitetura-alvo

```text
Internet
   |
   v
Global HTTPS Load Balancer + Cloud Armor
   |
   v
GCP API Gateway
   |---------------------------------------|
   |                                       |
   v                                       v
Cloud Run function Auth              Backend HTTPS do GKE
CPF -> Cloud SQL -> JWT                    |
                                             v
                                      FastAPI no GKE
                                             |
                             |---------------|---------------|
                             v                               v
                     Cloud SQL PostgreSQL             Outbox transacional
                                                             |
                                                             v
                                                    Publicador -> Pub/Sub
                                                             |
                                                             v
                                                  Function de notificação
                                                             |
                                                             v
                                                   Provedor de e-mail

Datadog recebe métricas, logs e traces do Gateway, Functions, GKE, FastAPI,
Cloud SQL e Pub/Sub. O correlation_id atravessa os componentes.
```

### 4.1 Limitação conhecida: URL nativa do API Gateway

O GCP API Gateway publica uma URL gerada pelo serviço (`*.gateway.dev`) e **não permite desativá-la nem restringir seu ingresso**. Colocar um HTTPS Load Balancer com Cloud Armor na frente do Gateway protege apenas o caminho do domínio customizado; quem conhecer a URL nativa chama o Gateway diretamente, contornando Cloud Armor. Referência: [Load balancing for API Gateway](https://docs.cloud.google.com/api-gateway/docs/gateway-load-balancing).

Consequências obrigatórias:

1. A URL nativa do Gateway deve ser tratada como endpoint de produção equivalente ao domínio customizado: todo controle de abuso, rate limit e teste de segurança deve ser executado **nos dois caminhos**.
2. Cloud Armor não pode ser a única proteção contra abuso do login por CPF. O rate limit do login precisa ser aplicado também na Function (por IP de origem recebido via header confiável do Gateway) ou por meio de quota do API Gateway com API key, se a opção for aceita.
3. Se nenhum desses controles for suficiente, o fallback Kong no GKE (seção 4.3) passa a ser a opção recomendada, pois elimina a URL nativa bypassável.
4. Nunca divulgar a URL nativa em README, vídeo ou documentação de entrega; ainda assim, não confiar nela como segredo.

### 4.2 Spike obrigatório: Gateway até GKE

Antes de implementar todas as rotas, criar um experimento mínimo com apenas `/health/live` e uma rota protegida. O objetivo é provar a proteção do backend GKE.

Opção preferida a validar:

```text
API Gateway -> HTTPS Load Balancer com IAP -> GKE
```

Critérios do spike:

1. O Gateway invoca o backend usando sua service account.
2. Chamada direta ao Load Balancer sem identidade autorizada é rejeitada.
3. Healthcheck do Load Balancer continua funcional.
4. JWT do cliente chega à aplicação de forma documentada e verificável.
5. A aplicação não confia em header que possa ser forjado por acesso direto.

O GCP API Gateway pode substituir `Authorization` quando `x-google-backend` usa autenticação do backend. Nesse caso, o token original pode aparecer em `X-Forwarded-Authorization`, e o resultado verificado pode aparecer em `X-Apigateway-Api-Userinfo`. O implementador deve confirmar o comportamento com teste de integração, não apenas copiar headers da documentação. Como a aplicação também valida o JWT (defesa em profundidade), o caminho preferido é a aplicação ler o token original do header encaminhado e validá-lo por conta própria, usando os headers do Gateway apenas como contexto.

### 4.3 Fallback documentado

Se a proteção Gateway -> IAP -> GKE não funcionar de forma suportada, registrar o resultado em RFC e adotar o fallback:

```text
Global HTTPS Load Balancer + Cloud Armor -> Kong Gateway no GKE -> FastAPI
```

O fallback cumpre o requisito de API Gateway (o enunciado aceita Kong ou Traefik) e elimina a URL nativa bypassável da seção 4.1, mas substitui o produto gerenciado GCP API Gateway. Não deixar o backend GKE público aceitando apenas um header secreto como prova de origem.

Referências oficiais para o spike:

- [JWT no GCP API Gateway](https://docs.cloud.google.com/api-gateway/docs/authenticating-users-jwt)
- [Extensão x-google-backend](https://docs.cloud.google.com/api-gateway/docs/oasv2-extensions)
- [Proteção de backends](https://docs.cloud.google.com/api-gateway/docs/securing-backend-services)
- [API Gateway atrás de Load Balancer e Cloud Armor](https://docs.cloud.google.com/api-gateway/docs/gateway-load-balancing)

## 5. Contratos de autenticação e autorização

### 5.1 Autenticação por CPF

Endpoint proposto:

```http
POST /auth/cpf
Content-Type: application/json

{"cpf": "52998224725"}
```

Resposta de sucesso:

```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Resposta para CPF inválido, inexistente ou cliente inativo:

```http
401 Unauthorized
{"detail": "Não foi possível autenticar o cliente"}
```

Não informar qual das três condições ocorreu. A métrica interna pode diferenciar o motivo por tag de baixa cardinalidade, sem CPF.

### 5.2 Claims do JWT

```json
{
  "sub": "<cliente_uuid>",
  "cliente_id": "<cliente_uuid>",
  "actor_type": "CLIENTE",
  "roles": ["CLIENTE"],
  "iss": "https://auth.<dominio>",
  "aud": "oficina-api",
  "iat": 0,
  "nbf": 0,
  "exp": 0,
  "jti": "<uuid>"
}
```

Regras:

- Assinar com RS256 no Cloud KMS.
- Publicar apenas a chave pública em `/.well-known/jwks.json`.
- Usar `kid` para permitir rotação.
- Aceitar a chave atual e a anterior durante a janela de rotação. Atenção: o API Gateway faz cache do JWKS por cerca de 5 minutos; a rotação deve manter a chave anterior válida por um período maior que esse cache.
- Não incluir CPF, nome, e-mail ou telefone.
- Não criar refresh token nesta fase.

### 5.2.1 Estratégia do JWT administrativo

> **R-02:** O emissor atual (`src/identidade/aplicacao/casos_de_uso.py:24-26`) emite apenas `sub`, `perfil` e `exp`. Se o validador novo passar a exigir `actor_type`, `iss` e `aud` sem que o emissor seja atualizado no mesmo deploy, **todos os funcionários perderão o acesso imediatamente após o deploy**. A solução obrigatória é evoluir emissor e validador de forma atômica, nunca separadamente.

O login administrativo atual emite apenas `sub`, `perfil` e `exp` (`src/identidade/aplicacao/casos_de_uso.py:24-26`). O novo validador exige `actor_type`, `iss` e `aud`; aplicar essas exigências sem alterar o emissor quebraria o acesso de funcionários. Portanto:

1. O Pacote 2 deve **evoluir emissor e validador juntos, no mesmo PR**: o `JwtTokenProvider` passa a emitir `actor_type` (`FUNCIONARIO`), `perfil`, `iss` e `aud` próprios para funcionários, mantendo HS256 nesta fase. **Não dividir esse trabalho em dois PRs.**
2. Os dois tipos de token têm validadores distintos na aplicação: HS256/HS-claims para `actor_type=FUNCIONARIO`, RS256/JWKS para `actor_type=CLIENTE`. Token de um tipo nunca é aceito como o outro.
3. No Gateway, configurar uma segunda security definition para o issuer administrativo apenas nas rotas administrativas/técnicas, ou declarar explicitamente que rotas administrativas são protegidas somente pela validação da aplicação. A decisão e seu motivo devem ser registrados no RFC-003.
4. A política para tokens antigos (sem os novos claims) é rejeição: a migração de emissor/validador ocorre no mesmo deploy, e usuários fazem login novamente. Documentar isso nas release notes.
5. Critério de aceite obrigatório: teste de integração `login administrativo real -> ação ADMIN` e `login MECANICO real -> ação técnica`, ambos com assertions reais (não mocks de token); corrigir ou substituir o teste E2E atual, que retorna sucesso mesmo quando o login falha.

### 5.3 Matriz de autorização

| Ação | CLIENTE | MECANICO | ADMIN | SISTEMA |
|---|---:|---:|---:|---:|
| Abrir OS | Não (Fase 3) | Não | Sim | Não |
| Consultar própria OS | Sim | Sim | Sim | Sim |
| Listar próprias OS | Sim | Sim | Sim | Sim |
| Consultar OS de outro cliente | Não | Sim | Sim | Conforme caso de uso |
| Aprovar/recusar próprio orçamento | Sim | Não | Sim | Não |
| Atualizar etapa técnica | Não | Sim | Sim | Conforme evento |
| CRUD de clientes e veículos | Não | Não | Sim | Não |
| Alterar serviço, preço ou estoque | Não | Não | Sim | Conforme integração |
| Consultar relatórios gerais | Não | Não | Sim | Leitura técnica específica |

Regras complementares:

- **Abertura de OS permanece operação ADMIN na Fase 3.** Hoje `POST /ordens-de-servico` já exige ADMIN e pode criar cliente/veículo a partir do payload. O primeiro cadastro de um cliente novo é, portanto, feito pelo atendente, e só depois disso o cliente consegue autenticar por CPF. Se no futuro CLIENTE puder abrir OS, a identidade deverá vir do principal autenticado, nunca do CPF livre do payload; essa mudança exige ADR novo.
- Toda rota pública deve ser listada explicitamente. A ausência de uma dependência de autenticação não pode ser usada implicitamente como decisão de segurança.

## 6. Modelagem relacional alvo

### 6.1 Cliente

Adicionar:

```text
status: ATIVO | INATIVO
status_alterado_em: timestamptz
```

Não adicionar data de nascimento, senha ou OTP enquanto a estratégia escolhida for CPF literal.

### 6.2 Histórico de status da OS

Criar tabela append-only `historico_status_os`:

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `os_id` | UUID | FK obrigatória |
| `sequencia` | integer | Ordem por OS, única com `os_id`; resolve desempate de timestamps |
| `status_anterior` | enum/string | Nulo somente no evento inicial |
| `status_novo` | enum/string | Obrigatório |
| `ocorrido_em` | timestamptz | UTC, obrigatório |
| `ator_id` | UUID | Pode ser nulo para migração inicial |
| `ator_tipo` | string | CLIENTE, MECANICO, ADMIN, SISTEMA ou MIGRACAO |
| `origem` | string | API, WEBHOOK, JOB ou BACKFILL |
| `motivo` | text | Opcional |
| `correlation_id` | UUID/string | Obrigatório em operações novas |

Índice mínimo: `(os_id, ocorrido_em)`.

Regras de captura:

- Cada transição de status gera exatamente um registro, na mesma transação da mudança de estado.
- A abertura unificada executa várias transições antes do primeiro `INSERT` da OS; o caso de uso deve coletar todos esses eventos e gravá-los juntos, na ordem correta, não apenas o par estado-inicial/estado-final.
- Um campo `sequencia` (inteiro por OS) resolve o desempate de eventos com o mesmo timestamp e preserva a ordem real das transições automáticas.

### 6.3 Outbox

Criar `outbox_eventos`:

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | Identificador e chave de idempotência |
| `aggregate_type` | string | Ex.: `ORDEM_DE_SERVICO` |
| `aggregate_id` | UUID | `os_id` |
| `event_type` | string | Ex.: `ORCAMENTO_DISPONIVEL` |
| `payload` | JSONB | Sem CPF/token/senha |
| `ocorrido_em` | timestamptz | UTC |
| `publicado_em` | timestamptz | Nulo enquanto pendente |
| `tentativas` | integer | Não negativo |
| `ultimo_erro` | text | Sanitizado e limitado |

Índice parcial recomendado nos eventos em que `publicado_em IS NULL`.

### 6.4 Constraints e índices

Criar migrations para:

- `CHECK` garantindo exatamente um entre CPF e CNPJ.
- `CHECK quantidade > 0` nos itens de peça.
- `CHECK estoque >= 0`.
- `CHECK preco >= 0`.
- Índices em `ordens_de_servico(cliente_id)`, `(veiculo_id)`, `(status)`, `(criada_em)` e `(status, criada_em)`.
- Política explícita de exclusão para cliente/veículo com histórico; preferir inativação, não exclusão física.
- Avaliar FK de `itens_servico.servico_id` e `itens_peca.peca_id`. Se os itens forem snapshots históricos que sobrevivem à remoção do catálogo, documentar e usar `ON DELETE SET NULL` com coluna anulável ou manter a ausência de FK por ADR.

### 6.5 Métricas por status

Definições propostas:

| Métrica | Início | Fim |
|---|---|---|
| Diagnóstico | Entrada em `EM_DIAGNOSTICO` | Entrada em `AGUARDANDO_ORCAMENTO` |
| Execução | Entrada em `EM_EXECUCAO` | Entrada em `SERVICOS_CONCLUIDOS` |
| Finalização | Entrada em `SERVICOS_CONCLUIDOS` | Entrada em `FINALIZADA` |

Essas definições devem ser aprovadas antes de criar dashboards. O backfill das OS existentes não deve inventar timestamps: registrar apenas o status conhecido com `origem=MIGRACAO`, deixando métricas históricas anteriores à implantação marcadas como indisponíveis.

Regras de agregação:

- A OS pode voltar a `EM_DIAGNOSTICO` após recusa de orçamento, gerando vários ciclos no mesmo status. A métrica padrão é **tempo acumulado por OS por status**: soma de todos os intervalos fechados do par (entrada, próxima saída). A média exposta no dashboard é `soma dos intervalos / quantidade de OS com intervalo fechado`.
- Intervalos ainda abertos (status corrente) não entram na média histórica; podem aparecer em painel separado de "tempo parado agora".
- O pareamento é feito na ordem de `ocorrido_em, sequencia`, nunca pela primeira entrada e última saída (isso incluiria a espera por aprovação no diagnóstico).
- Transições automáticas na abertura (RECEBIDA -> EM_DIAGNOSTICO -> AGUARDANDO_ORCAMENTO -> AGUARDANDO_APROVACAO no mesmo request) produzem intervalos de duração mínima e devem ser identificáveis (origem `API` + `sequencia`), para não distorcer a média de diagnóstico; se a média operacional ficar distorcida, avaliar consolidar essas transições sintéticas na modelagem e registrar a decisão em ADR.
- Testes obrigatórios: OS com duas recusas (dois ciclos de diagnóstico somados corretamente), dois eventos com timestamp idêntico (ordem por `sequencia`) e abertura unificada (todos os eventos presentes na ordem).

## 7. Divisão dos quatro repositórios

### 7.1 Repositório `oficina-serverless`

Responsabilidades:

- Function de autenticação por CPF.
- Endpoint JWKS.
- Function de notificação.
- Topics, subscriptions, retries e dead-letter topic do Pub/Sub.
- Cloud KMS para JWT.
- OpenAPI e Terraform do API Gateway após o spike.
- Integração Datadog das Functions.

Estrutura sugerida:

```text
README.md
pyproject.toml
uv.lock
src/auth/handler.py
src/auth/cpf.py
src/auth/repository.py
src/auth/token_issuer.py
src/auth/jwks.py
src/notifications/handler.py
src/notifications/provider.py
src/notifications/templates/
tests/unit/
tests/integration/
tests/contract/
openapi/gateway.yaml
terraform/modules/functions/
terraform/modules/api-gateway/
terraform/modules/pubsub/
terraform/modules/kms/
terraform/environments/homolog/
terraform/environments/prod/
docs/diagramas/
.github/workflows/ci.yml
.github/workflows/terraform-plan.yml
.github/workflows/deploy-homolog.yml
.github/workflows/deploy-prod.yml
```

### 7.2 Repositório `oficina-k8s-infra`

Responsabilidades:

- Bootstrap dos backends Terraform.
- APIs GCP necessárias.
- VPC, subnets, ranges secundários, private service access e NAT.
- Serverless VPC Access connector para as Functions alcançarem o Cloud SQL por IP privado.
- GKE e node pools.
- Artifact Registry.
- Workload Identity e service accounts da plataforma.
- Load Balancer, IAP, Cloud Armor, DNS e certificados conforme o spike.
- Componentes Kubernetes de plataforma.
- Datadog Agent e Cluster Agent.

Fronteira com `oficina-serverless`: este repositório é dono da rede, do connector e do Load Balancer; o repositório serverless é dono das Functions, do KMS, do Pub/Sub e da configuração OpenAPI do Gateway. O connector e o nome da VPC são entregues como outputs/valores estáveis para o Terraform serverless consumir por data source ou variável, sem `terraform_remote_state` amplo.

Estrutura sugerida:

```text
README.md
bootstrap/
terraform/modules/project-services/
terraform/modules/network/
terraform/modules/gke/
terraform/modules/artifact-registry/
terraform/modules/load-balancer/
terraform/modules/iam/
terraform/modules/datadog/
terraform/environments/homolog/
terraform/environments/prod/
k8s/platform/base/
k8s/platform/overlays/homolog/
k8s/platform/overlays/prod/
.github/workflows/validate.yml
.github/workflows/terraform-plan.yml
.github/workflows/deploy-homolog.yml
.github/workflows/deploy-prod.yml
```

Não mover os manifests atuais de PostgreSQL/PVC para produção cloud.

### 7.3 Repositório `oficina-database-infra`

Responsabilidades:

- Cloud SQL PostgreSQL 16.
- IP privado, parâmetros, manutenção e proteção contra exclusão.
- Alta disponibilidade de produção.
- Backup, PITR, logs e Query Insights.
- Secret Manager para credenciais de conexão.
- Monitores técnicos do banco.

Estrutura sugerida:

```text
README.md
terraform/modules/cloud-sql/
terraform/modules/secrets/
terraform/modules/monitoring/
terraform/environments/homolog/
terraform/environments/prod/
docs/diagrama-er.md
docs/dicionario-de-dados.md
docs/runbook-backup-restore.md
.github/workflows/validate.yml
.github/workflows/terraform-plan.yml
.github/workflows/deploy-homolog.yml
.github/workflows/deploy-prod.yml
```

O repositório provisiona o serviço. As migrations Alembic e a propriedade do schema permanecem no repositório da aplicação.

### 7.4 Repositório `oficina-api`

Recebe a maior parte do repositório atual:

```text
src/
tests/
alembic.ini
Dockerfile
docker-compose.yml
pyproject.toml
uv.lock
docs/
scripts/
```

Responsabilidades adicionais:

- Unit of Work e consistência transacional.
- Validação dos JWTs de cliente e funcionário.
- Autorização por propriedade e perfil.
- Histórico de status.
- Outbox e publicador.
- Healthchecks reais.
- Logs JSON, métricas e tracing.
- Manifestos específicos da aplicação.
- Migrations e deploy por imagem imutável.

Novos caminhos sugeridos:

```text
src/shared/autorizacao/principal.py
src/shared/autorizacao/policies.py
src/shared/observabilidade/logging.py
src/shared/observabilidade/middleware.py
src/shared/observabilidade/metricas.py
src/shared/observabilidade/tracing.py
src/shared/eventos/outbox.py
src/shared/infraestrutura/unit_of_work.py
src/atendimento/dominio/historico_status.py
src/atendimento/infraestrutura/outbox_repositorio.py
src/atendimento/infraestrutura/publicador_pubsub.py
tests/contract/test_jwt_serverless.py
tests/integration/test_autorizacao_propriedade.py
tests/integration/test_historico_status.py
tests/integration/test_healthchecks.py
tests/integration/test_outbox.py
k8s/base/
k8s/overlays/homolog/
k8s/overlays/prod/
```

## 8. Provisionamento GCP

### 8.1 Pré-requisitos administrativos

- Billing account ativa.
- IDs dos projetos de homologação e produção.
- Região aprovada.
- Domínio e acesso ao DNS.
- Organização/pastas GCP, se disponíveis.
- Organização GitHub e nomes definitivos dos quatro repositórios.
- Grupo de administradores e revisores de produção.
- Conta Datadog e chaves guardadas como secrets.
- Provedor de e-mail e credenciais.

### 8.2 Recursos por ambiente

| Categoria | Homologação | Produção |
|---|---|---|
| Projeto | Projeto isolado | Projeto isolado |
| GKE | Capacidade reduzida | Regional, múltiplas zonas e autoscaling |
| Cloud SQL | Instância menor, sem HA se custo exigir | Regional HA, backup, PITR e proteção contra exclusão |
| Functions | Min instances 0 ou baixo | Min instances conforme SLO |
| Gateway | Endpoint de homologação | Endpoint de produção |
| Pub/Sub | Topic, subscription e DLQ | Topic, subscription e DLQ com alertas |
| Datadog | Retenção e sampling menores | APM, logs e monitores conforme SLO |
| DNS | `api-homolog.<dominio>` | `api.<dominio>` |
| Terraform state | Bucket/prefixo próprio | Bucket/prefixo próprio, versionamento e acesso restrito |

### 8.3 APIs GCP prováveis

Validar a lista com os recursos Terraform efetivamente usados:

```text
serviceusage.googleapis.com
compute.googleapis.com
container.googleapis.com
artifactregistry.googleapis.com
sqladmin.googleapis.com
servicenetworking.googleapis.com
vpcaccess.googleapis.com
secretmanager.googleapis.com
cloudkms.googleapis.com
run.googleapis.com
cloudfunctions.googleapis.com
cloudbuild.googleapis.com
pubsub.googleapis.com
apigateway.googleapis.com
servicemanagement.googleapis.com
servicecontrol.googleapis.com
iam.googleapis.com
iamcredentials.googleapis.com
sts.googleapis.com
iap.googleapis.com
logging.googleapis.com
monitoring.googleapis.com
```

### 8.4 State e dependências entre repositórios

- Usar backend GCS com versionamento e acesso mínimo.
- Separar state por repositório e ambiente.
- Não compartilhar um único state entre os quatro repositórios.
- Evitar leitura ampla de `terraform_remote_state`, pois ela concede acesso ao state completo.
- Preferir nomes estáveis, data sources GCP, outputs publicados como GitHub Environment variables e Secret Manager para valores sensíveis.
- Aplicar `concurrency` por ambiente nos workflows.
- Definir dependência operacional: plataforma -> banco -> aplicação -> serverless/gateway.
- Não destruir plataforma automaticamente quando outro repositório ainda depende dela.

### 8.5 Principais custos

Não registrar estimativas fixas sem consultar a calculadora GCP e o plano Datadog na data do provisionamento. Os maiores vetores são:

- GKE regional e número mínimo de nós.
- Cloud SQL regional HA.
- Cloud NAT e tráfego de saída.
- Load Balancer, Cloud Armor e IAP.
- Retenção e volume de logs Datadog.
- Min instances das Functions.
- Query Insights e volume de armazenamento/backups.

Criar orçamento e alertas de billing antes dos ambientes persistentes. Homologação pode usar capacidade menor e agenda de desligamento quando tecnicamente possível.

## 9. Segurança

### 9.1 CPF como autenticação

CPF é identificador pessoal, não segredo. O requisito será implementado literalmente, mas o risco deve constar em RFC/ADR. Controles mínimos:

- Resposta indistinguível para CPF inválido, inexistente e inativo.
- Rate limit aplicado nos dois caminhos de entrada (ver seção 4.1): Cloud Armor no domínio customizado e, adicionalmente, controle na Function de autenticação por IP de origem confiável, com limite conservador.
- Timeout curto e limite de payload.
- Métrica de tentativas, sem CPF.
- Token com 15 minutos de validade.
- JWT sem dados pessoais.
- TLS obrigatório.
- Logs com redaction.
- Alerta de volume anormal de tentativas.

Quota do API Gateway baseada em consumidor/API key não substitui proteção por IP para um endpoint público de CPF, pois o login não pode exigir API key distribuída aos clientes. Cloud Armor protege somente o caminho do domínio customizado; a URL nativa do Gateway permanece alcançável e por isso a Function precisa de defesa própria (seção 4.1).

### 9.2 Segredos

- Não versionar `Secret` Kubernetes concreto.
- Usar Secret Manager e External Secrets Operator ou Secret Manager CSI.
- Não armazenar service account keys no GitHub.
- Usar GitHub OIDC/Workload Identity Federation.
- Rotacionar qualquer segredo real que já tenha entrado no histórico Git.
- Separar senha de banco, credencial administrativa e chave de e-mail.
- Nunca expor segredo em output Terraform.

### 9.3 Kubernetes

- `runAsNonRoot: true`.
- UID/GID explícitos e coerentes com o Dockerfile.
- `readOnlyRootFilesystem: true` quando validado.
- `allowPrivilegeEscalation: false`.
- Drop de capabilities.
- `seccompProfile: RuntimeDefault`.
- ServiceAccount dedicada com Workload Identity.
- NetworkPolicy de ingress e egress.
- PDB e distribuição por zona/nó.
- Requests e limits obrigatórios.
- Imagem por digest ou SHA, nunca `latest`.

## 10. Observabilidade

### 10.1 Padrão de logs

Cada log de requisição deve ser JSON e conter, quando aplicável:

```json
{
  "timestamp": "2026-09-14T00:00:00Z",
  "level": "INFO",
  "service": "oficina-api",
  "env": "homolog",
  "version": "<git_sha>",
  "message": "request_completed",
  "correlation_id": "<uuid>",
  "trace_id": "<trace_id>",
  "span_id": "<span_id>",
  "http_method": "GET",
  "http_route": "/ordens-de-servico/{id}",
  "http_status": 200,
  "duration_ms": 12.3,
  "actor_type": "CLIENTE"
}
```

Não registrar body de autenticação, CPF, token, `Authorization`, cookies, senha ou connection string.

### 10.2 Correlation ID

- Aceitar `X-Correlation-ID` somente se tiver formato e tamanho válidos; caso contrário, gerar UUID.
- Devolver o valor no response header.
- Propagar em chamadas Pub/Sub como atributo e no payload da outbox.
- Incluir em logs e traces.
- Não usar correlation ID como credencial ou chave de idempotência.

### 10.3 Healthchecks

| Endpoint | Finalidade | Dependências |
|---|---|---|
| `/health/live` | Processo está vivo | Nenhuma dependência externa |
| `/health/ready` | Pode receber tráfego | Conexão ao banco e versão mínima de migration |
| `/health/startup` | Inicialização terminou | Configuração carregada e recursos locais prontos |

Liveness não deve falhar porque o banco caiu, evitando reinícios em cascata. Readiness deve retirar o Pod do tráfego quando a aplicação não puder operar.

### 10.4 Dashboards Datadog

Criar dashboards versionados para:

- Latência HTTP p50, p95 e p99.
- Requests por segundo e volume diário.
- Taxa de 4xx e 5xx.
- CPU, memória, restarts, réplicas e HPA.
- Healthcheck e uptime sintético.
- Conexões, CPU, storage e latência do Cloud SQL.
- Invocações, duração, cold starts e erros das Functions.
- Backlog, idade da mensagem, retry e DLQ do Pub/Sub.
- Volume diário de OS.
- Tempo médio em Diagnóstico, Execução e Finalização.
- Erros de integração por tipo.

### 10.5 Monitores mínimos

- P95 acima do SLO por janela sustentada.
- Taxa de 5xx acima do limite.
- Todas as réplicas indisponíveis.
- Reinícios excessivos de Pods.
- Readiness falhando.
- Erro de processamento de OS.
- Evento parado na outbox.
- Idade da mensagem Pub/Sub elevada.
- DLQ não vazia.
- Function com erro ou timeout.
- Cloud SQL com conexões, CPU ou storage em nível crítico.
- Falha de teste sintético autenticar -> consultar OS.

Os limiares devem ser definidos após baseline em homologação, não inventados pelo implementador.

## 11. CI/CD e governança

### 11.1 Branches

Padrão recomendado:

```text
feature/* -> Pull Request -> homologacao -> deploy automático em homologação
homologacao -> Pull Request -> main -> aprovação do environment -> deploy automático em produção
```

Configuração externa obrigatória em cada repositório:

- Proibir push direto em `main`.
- Exigir Pull Request.
- Exigir checks de CI.
- Exigir branch atualizada antes do merge.
- Exigir pelo menos um revisor.
- Proibir force push e exclusão da branch.
- Criar GitHub Environments `homolog` e `production`.
- Exigir revisão humana no environment de produção.
- Adicionar o usuário `soat-architecture`.

### 11.2 Pipeline da aplicação

PR:

1. `ruff check .`.
2. `black --check .`.
3. Testes unitários.
4. Testes de integração com PostgreSQL 16.
5. Teste de migration em banco vazio.
6. Cobertura de domínio/aplicação >= 80%.
7. SonarQube/SonarCloud.
8. Scan de dependências, secrets e imagem.
9. Build do Dockerfile sem push.
10. Validação de manifests.

Merge de ambiente:

1. Build uma vez.
2. Publicar imagem por SHA e obter digest.
3. Executar migration Job com nome contendo release/SHA.
4. Aguardar migration.
5. Atualizar Deployment com o mesmo digest.
6. Aguardar rollout.
7. Executar smoke tests.
8. Marcar deployment no Datadog.
9. Fazer rollback se smoke test falhar.

Regras de compatibilidade migration x rollback:

- Toda migration deve ser compatível com a **versão anterior da aplicação** (estratégia expand/contract): colunas novas anuláveis ou com default, constraints adicionadas de forma não bloqueante, remoções somente no release seguinte ao que deixou de usar a estrutura antiga.
- O rollback da imagem nunca executa `alembic downgrade` automaticamente. O schema novo deve continuar funcionando com a imagem anterior durante a janela de rollback.
- Smoke test obrigatório em homologação: imagem N-1 executando contra o schema N antes de promover a produção.
- Downgrades destrutivos são manuais, documentados no runbook e fora da pipeline.

### 11.3 Pipelines Terraform

PR com dois jobs:

Job 1 — validação estática (sem credenciais cloud):

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
tflint
```

Job 2 — plan autenticado (OIDC, sem expor segredos no log):

```bash
terraform init   # backend GCS do ambiente de homologação
terraform plan -out=tfplan
```

Escolher **uma** ferramenta de análise de segurança (`checkov`, recomendado) e executá-la no job 1; não deixar alternativas em aberto dentro de scripts. O plan do job 2 deve ser anexado ao PR como artefato/comentário sem valores sensíveis. Merge em `homologacao` aplica homologação. Merge em `main`, após aprovação do environment, aplica produção. Usar `concurrency` para impedir dois applies simultâneos no mesmo ambiente.

### 11.4 Supply chain

- Versionar `uv.lock` e `.terraform.lock.hcl`.
- Fixar Actions por SHA quando possível.
- Fixar imagens-base por digest após validar processo de atualização.
- Gerar SBOM da imagem.
- Assinar imagem ou, no mínimo, registrar digest usado no deploy.
- Promover o mesmo artefato validado; não reconstruir silenciosamente uma versão com o mesmo identificador.

## 12. Pacotes de implementação

### Pacote 0: estabilização das Fases 1 e 2

Objetivo: eliminar falhas que seriam amplificadas por múltiplas réplicas e exposição pública.

Arquivos principais:

- `src/atendimento/apresentacao/schemas.py`
- `src/atendimento/apresentacao/rotas.py`
- `src/atendimento/aplicacao/casos_de_uso.py`
- `src/atendimento/infraestrutura/repositorios.py`
- `src/estoque/dominio/entidades.py`
- `src/estoque/infraestrutura/repositorios.py`
- `src/shared/dependencias.py`
- testes correspondentes.

Tarefas:

1. Impedir quantidade menor que 1 no schema e no domínio.
2. Persistir `valor_orcamento` no INSERT.
3. Rejeitar veículo existente cujo `cliente_id` difira do cliente da abertura.
4. Corrigir a definição de OS ativa.
5. Proteger aprovação/recusa e remover equivalentes públicos inseguros.
6. Restringir catálogo, estoque e relatórios ao perfil correto.
7. Criar uma porta `UnitOfWork` na aplicação e adapter SQLAlchemy na infraestrutura.
8. **[R-03] Inventariar TODOS os casos de uso que escrevem via repositórios** com `commit()` embutido (clientes, veículos, OS, peças e estoque) e migrar cada um para a Unit of Work, com dono explícito da transação. **Remover os commits dos repositórios somente junto com essa migração total** — remover os commits apenas da abertura/aprovação e deixar os demais sem modificação fará com que `CadastrarCliente`, `AtualizarVeiculo` e equivalentes respondam `200 OK` sem persistir nada, pois o container fecha a sessão sem commit automático (`src/container.py:92-97`). Essa regressão silenciosa é o risco mais grave do pacote.
9. Executar abertura e aprovação em transação única.
10. Reservar estoque com lock pessimista ou UPDATE condicional.
11. Validar estado da OS antes de reservar peças.
12. Tornar aprovação idempotente.
13. Padronizar mapeamento de exceções para HTTP.

Critérios de aceite:

- Todos os testes da seção 3.4 relativos ao pacote passam.
- CRUDs compartilhados (cliente, veículo, peça) persistem alterações verificadas em **nova sessão** de banco; a fixture de integração não pode mascarar a regressão reutilizando a mesma sessão entre a escrita e a leitura.
- Nenhum caso de uso de abertura/aprovação deixa alteração parcial.
- Repositórios não encerram uma transação que pertence ao caso de uso.
- `uv run pytest`, `uv run ruff check .` e `uv run black --check .` passam.

### Pacote 1: status do cliente, histórico e integridade relacional

Tarefas:

1. Adicionar `StatusCliente` no domínio.
2. Adicionar campos ao modelo e schema.
3. Criar entidade/porta de histórico.
4. Persistir transição e histórico na mesma Unit of Work.
5. Criar migrations aditivas.
6. Fazer backfill conservador.
7. Criar índices e constraints da seção 6.
8. Alterar remoção física de cliente/veículo para política compatível com histórico.

Critérios de aceite:

- A consulta de cliente por CPF exposta para a Function (porta na aplicação) retorna status, e um cliente `INATIVO` é distinguido de `ATIVO` em teste de integração. A autenticação end-to-end com a Function é validada apenas no Pacote 7 — não cobrar aqui o que ainda não existe.
- Toda transição nova possui exatamente um registro de histórico, incluindo as transições intermediárias da abertura unificada, na ordem definida por `sequencia`.
- OS com duas recusas acumula corretamente dois ciclos de diagnóstico na métrica (regras da seção 6.5).
- Rollback remove simultaneamente transição e histórico.
- Migration funciona em banco vazio e em cópia do schema atual.
- Downgrade imediato é testado quando seguro.

### Pacote 2: principal e autorização por propriedade

Tarefas:

1. Criar objeto `Principal` independente de FastAPI.
2. Evoluir **emissor e validador juntos**, conforme a seção 5.2.1: o login administrativo passa a emitir `actor_type=FUNCIONARIO`, `perfil`, `iss` e `aud` próprios; tokens antigos passam a ser rejeitados (login novo exigido).
3. Criar adapters para JWT de funcionário (HS256) e cliente (RS256/JWKS), com validadores distintos.
4. Validar `iss`, `aud`, `exp`, `nbf`, assinatura e `actor_type`.
5. Aplicar a matriz da seção 5.3, incluindo a linha de abertura de OS.
6. Filtrar listagem de OS por `cliente_id` para CLIENTE.
7. Comparar propriedade no detalhe, status e aprovação.
8. Retornar `404` para acesso cruzado do cliente.
9. Documentar rotas públicas.

Critérios de aceite:

```text
cliente A -> OS A = 200
cliente A -> OS B = 404
cliente A -> abrir OS = 403
cliente A -> estoque/relatório = 403
mecânico -> ação técnica = 200
mecânico -> abrir OS = 403
mecânico -> preço/estoque administrativo = 403
admin -> abrir OS = 200
admin -> ação administrativa = 200
login administrativo real -> ação ADMIN = 200
login MECANICO real -> ação técnica = 200
token sem actor_type ou audience correta = 401
token HS256 de funcionário usado como CLIENTE = 401
token antigo sem novos claims = 401 (com re-login orientado na mensagem)
```

### Pacote 3: separação dos repositórios

Tarefas manuais e GitHub:

1. Criar os quatro repositórios privados ou públicos conforme entrega.
2. Mover arquivos conforme a seção 7, preservando histórico quando viável.
3. Criar README inicial em cada repositório.
4. Criar em cada repositório o **CI mínimo** (lint + testes + validação estática do que existir) já no primeiro PR, para que os deploys automatizados dos pacotes seguintes tenham base; os workflows de deploy completos chegam no Pacote 11.
5. Configurar branch protection e environments.
6. Adicionar `soat-architecture`.
7. Atualizar links cruzados.
8. Garantir que nenhum secret, state ou kubeconfig seja copiado.

Não apagar o repositório original antes de validar os quatro destinos.

### Pacote 4: bootstrap e plataforma GCP

Tarefas:

1. Criar projetos/selecionar projetos existentes.
2. Criar buckets de state com versionamento.
3. Configurar Workload Identity Federation para GitHub Actions.
4. Habilitar APIs GCP.
5. Provisionar rede, GKE e Artifact Registry.
6. **[R-04] Provisionar o Serverless VPC Access connector** na mesma região das Functions, com faixa de IP dedicada (`/28` mínimo), e publicar seu nome e a VPC como outputs estáveis para o repositório `oficina-serverless` consumir. Sem esse connector, a Function de autenticação não alcança o Cloud SQL por IP privado. A escolha entre Serverless VPC Access e Cloud SQL connector direto (`ipTypes=PRIVATE`) deve ser registrada em ADR — escolher **antes** de implementar o Pacote 7, não durante.
7. Configurar service accounts e IAM mínimo.
8. Instalar componentes de plataforma.
9. Criar orçamento e alertas de billing.

Critérios de aceite:

- Terraform plan limpo após apply.
- CI autentica sem chave JSON.
- GKE possui nós prontos e Workload Identity funcional.
- State de cada ambiente está isolado.
- Nenhum endpoint de banco foi criado nesta etapa.

### Pacote 5: Cloud SQL

Tarefas:

1. Provisionar PostgreSQL 16 com IP privado.
2. Configurar HA conforme ambiente.
3. Configurar backup, PITR e janela de manutenção.
4. Criar database e usuários separados por função: `oficina_migrator` (dono do schema, usado pelo Alembic), `oficina_app` (CRUD das tabelas de negócio) e `oficina_auth_ro` (somente leitura das colunas necessárias de `clientes`, para a Function).
5. Guardar credenciais no Secret Manager, um secret por usuário.
6. Habilitar Query Insights e exportação de logs.
7. Criar monitores Datadog/Cloud Monitoring.
8. Documentar backup e restauração.

Critérios de aceite:

- Banco não possui acesso público.
- Conexão exige canal seguro.
- Pod autorizado conecta; origem externa não autorizada falha.
- Backup é visível e restauração é ensaiada em homologação.
- Produção possui `prevent_destroy` e aprovação humana.

### Pacote 6: deploy base da aplicação no GKE

Tarefas:

1. Converter manifests em base/overlays.
2. Remover PostgreSQL/PVC do deploy cloud.
3. Integrar Secret Manager.
4. Criar ServiceAccount com Workload Identity.
5. Criar probes separadas.
6. Adicionar PDB, NetworkPolicy e distribuição.
7. Corrigir migration Job para nome por release.
8. Usar digest imutável.
9. Executar smoke test pós-deploy.

Critérios de aceite:

- Pelo menos duas réplicas de produção distribuídas.
- HPA possui métricas e escala em teste controlado.
- Readiness falha sem banco e liveness continua saudável.
- Migration executa uma vez por release antes do rollout.
- **[R-07] Rollback documentado**: toda migration aplicada neste pacote é compatível com a versão anterior da aplicação (estratégia expand/contract da seção 11.2). Antes de promover para produção, executar em homologação o smoke test com a **imagem N-1 contra o schema N** e confirmar que a versão anterior opera sem erros.

### Pacote 7: Function de autenticação e JWKS

Tarefas:

1. Extrair/reimplementar a validação de CPF sem importar o monólito.
2. **[R-04] Consultar cliente por CPF** normalizado e status, usando o usuário `oficina_auth_ro` e o **Serverless VPC Access connector provisionado no Pacote 4** (ou Cloud SQL connector com `ipTypes=PRIVATE`, conforme ADR decidido antes deste pacote). **Não implementar este pacote sem o connector funcional**: testar conectividade da Function ao Cloud SQL antes de qualquer lógica de autenticação.
3. Assinar JWT via Cloud KMS.
4. Expor JWKS com cache apropriado, mantendo a chave anterior disponível por período superior ao cache de ~5 minutos do Gateway.
5. Implementar resposta anti-enumeração.
6. Implementar rate limit próprio por IP de origem (defesa do caminho da URL nativa, seção 4.1).
7. Instrumentar logs, métricas e traces.
8. Limitar pool/conexões ao Cloud SQL (máximo de conexões por instância configurado e documentado).
9. Criar testes unitários, integração e contrato.

Critérios de aceite:

- CPF válido e ativo retorna JWT válido.
- Outros casos retornam a mesma resposta `401`.
- Chave privada não sai do KMS.
- Gateway e aplicação validam o mesmo token via JWKS.
- Rotação de `kid` funciona sem indisponibilidade.

### Pacote 8: API Gateway e proteção de origem

Executar primeiro o spike da seção 4.1. Somente depois criar o OpenAPI completo.

Tarefas:

1. Declarar security definitions: RS256/JWKS para clientes e a definição administrativa decidida na seção 5.2.1, cada uma restrita às rotas corretas.
2. Marcar apenas login e healthcheck apropriado como públicos.
3. Configurar backends da Function e GKE.
4. Provar autenticação Gateway -> backend.
5. Posicionar Load Balancer/Cloud Armor conforme o spike.
6. Implementar rate limit do login por CPF nos dois caminhos (Cloud Armor no domínio e limite na Function).
7. Testar headers encaminhados e spoofing.
8. Registrar fallback em RFC se o desenho preferido falhar.

Critérios de aceite:

- Token ausente, expirado, adulterado ou com audience/issuer incorretos é rejeitado.
- Backend GKE não pode ser contornado por URL direta.
- O teste de abuso do login é executado **tanto pelo domínio customizado quanto pela URL nativa do Gateway** (seção 4.1), e ambos são limitados.
- Swagger/Postman usa apenas o domínio público customizado.

### Pacote 9: notificações serverless

Tarefas:

1. Criar outbox no mesmo commit da mudança da OS, incluindo o evento `ORCAMENTO_DISPONIVEL` na abertura unificada (que hoje não notifica).
2. Criar o relay de publicação: **Cloud Scheduler → Function relay** que lê pendências da outbox com lock (`SELECT ... FOR UPDATE SKIP LOCKED`), publica no Pub/Sub e marca `publicado_em`. Alternativa aceita: worker no GKE; a escolha e o motivo entram no RFC-005. Não usar thread em background dentro do processo web da API.
3. Criar a Function consumidora.
4. **[R-05] Implementar deduplicação** com tabela `entregas_notificacao` (`event_id` único) ou chave idempotente do provedor de e-mail. Declarar explicitamente qual semântica é entregue (ver quadro abaixo). Não prometer exatamente uma vez se a implementação não garantir isso.
5. Configurar retry e DLQ.
6. Migrar templates de e-mail com escape de HTML.
7. **[R-06] Implementar o fluxo completo da ação por e-mail**: ao gerar `ORCAMENTO_DISPONIVEL`, emitir credencial de ação com escopo (`os_id`, ação permitida: `APROVACAO` ou `RECUSA`), expiração curta e destinatário autorizado (o `cliente_id` da OS); montar o link **real** no template (os botões atualmente têm `href="#"`); o endpoint de ação valida a credencial, o destinatário, a não-expiração e o estado atual da OS antes de executar a transição. Sem esse fluxo, o requisito da Fase 2 continua incompleto.
8. Criar observabilidade e replay da DLQ.

**[R-05] Semântica de entrega declarada (documentar no RFC-005 e no README):**

- Pub/Sub entrega **pelo menos uma vez**; não prometer exatamente uma vez.
- Com deduplicação no banco (`entregas_notificacao`): gravar o início do processamento por `event_id` **antes** de chamar o provedor, e o sucesso **depois**. Consequências:
  - Se a Function morrer **após o envio mas antes do registro**: existe uma **janela residual de duplicação**. O destinatário pode receber o e-mail duas vezes.
  - Se a Function morrer **antes do envio**: a tentativa seguinte reenvia corretamente.
- Se o provedor de e-mail oferecer chave idempotente nativa, usá-la fecha a janela residual.
- **A janela residual de duplicação deve ser declarada explicitamente** na documentação do RFC-005 e no README do repositório serverless. Nunca esconder essa limitação.
- O critério de aceite "duplicata não gera dois envios" vale para o caminho implementado e testado com a mesma mensagem publicada duas vezes no Pub/Sub, não para a janela residual.

Critérios de aceite:

- Falha do e-mail não desfaz a OS.
- Falha antes da publicação mantém outbox pendente, e o relay a recupera.
- Mensagem duplicada no Pub/Sub é deduplicada por `event_id` (teste com a mesma mensagem publicada duas vezes).
- Falha definitiva chega à DLQ e dispara alerta.
- Replay é documentado e demonstrado.
- **[R-06] Fluxo end-to-end**: abertura → e-mail com link real → clique no link sem fabricar token manualmente → credencial validada → status atualizado. O teste não pode montar a credencial de ação diretamente; deve obtê-la pelo fluxo de geração.

### Pacote 10: Datadog e observabilidade da aplicação

Tarefas:

1. Implementar middleware de correlation ID.
2. Configurar logs JSON e redaction.
3. Instrumentar FastAPI, SQLAlchemy, Pub/Sub e Functions.
4. Propagar contexto nos eventos.
5. Instalar Datadog no GKE.
6. Integrar projeto GCP ao Datadog.
7. Criar dashboards e monitores da seção 10.
8. Criar testes sintéticos.
9. Marcar versões/deployments com `env`, `service` e `version`.

Critérios de aceite:

- Uma requisição pode ser localizada pelo correlation ID.
- Trace conecta Gateway, aplicação, banco e publicação quando suportado.
- Logs não contêm CPF/token.
- Dashboards exibem os três indicadores de negócio obrigatórios.
- Falha controlada de processamento de OS gera métrica, log e alerta.

### Pacote 11: CI/CD dos quatro repositórios

Tarefas:

1. Implementar workflows da seção 11.
2. Configurar OIDC e IAM mínimo.
3. Separar homologação e produção.
4. Adicionar concurrency e approvals.
5. Remover defaults inseguros de senha.
6. Publicar evidências do plan/deploy.
7. Adicionar badges e links aos READMEs.

Critérios de aceite:

- PR sem checks não pode ser mesclado.
- Push direto em `main` é bloqueado.
- Merge em homologação realiza deploy automático.
- Merge aprovado em `main` realiza deploy de produção.
- Nenhum workflow usa chave GCP estática ou imagem `latest`.

### Pacote 12: documentação e entrega

Criar:

- Diagrama de componentes cloud.
- Diagrama de sequência da autenticação.
- Diagrama de sequência da abertura de OS.
- Diagrama de sequência das notificações.
- Diagrama ER atualizado.
- Fluxo de CI/CD entre os quatro repositórios.
- Dicionário de dados.
- Runbooks de deploy, rollback, migration, backup, restauração, DLQ e incidentes.
- RFCs e ADRs da seção 13.
- README completo em cada repositório.
- Roteiro e evidências para o vídeo.
- Documento final para conversão em PDF.

Cada README deve conter propósito, tecnologias, pré-requisitos, execução local, deploy, diagrama específico, variáveis sem valores secretos, troubleshooting, link do Swagger/Postman quando aplicável e links dos ambientes ativos. Quando um repositório não expuser API, deve apontar para a documentação central e marcar Swagger como não aplicável, em vez de inventar um endpoint.

## 13. RFCs e ADRs

### 13.1 RFCs

| Arquivo | Conteúdo |
|---|---|
| `RFC-001-provedor-gcp.md` | Alternativas, custos, serviços e justificativa do GCP |
| `RFC-002-autenticacao-cpf.md` | Risco do CPF como credencial, mitigação e alternativas descartadas |
| `RFC-003-api-gateway-gke.md` | Resultado do spike, proteção de origem e fallback |
| `RFC-004-separacao-repositorios.md` | Ownership, dependências e releases |
| `RFC-005-notificacoes-serverless.md` | Outbox, Pub/Sub, idempotência, retry e DLQ |
| `RFC-006-observabilidade-datadog.md` | Coleta, sampling, retenção e custos |
| `RFC-007-migracao-cloud-sql.md` | Migração, downtime, rollback e validação |

### 13.2 ADRs

| Arquivo | Decisão permanente |
|---|---|
| `ADR-004-gke.md` | GKE e topologia dos ambientes |
| `ADR-005-cloud-sql-postgresql.md` | Banco gerenciado e ownership do schema |
| `ADR-006-jwt-rs256-kms-jwks.md` | Assinatura e rotação de JWT |
| `ADR-007-autorizacao-por-principal.md` | CLIENTE, MECANICO, ADMIN e SISTEMA |
| `ADR-008-historico-status.md` | Histórico append-only |
| `ADR-009-outbox-pubsub.md` | Comunicação assíncrona |
| `ADR-010-hpa-e-disponibilidade.md` | Autoscaling, PDB e distribuição |
| `ADR-011-datadog.md` | Observabilidade |
| `ADR-012-state-terraform.md` | Backend GCS e isolamento |
| `ADR-013-migrations.md` | Alembic no repositório da aplicação |

ADRs antigos devem ser atualizados ou substituídos explicitamente, nunca editados como se a decisão histórica não tivesse existido.

## 14. Validação final

### 14.1 Aplicação

```bash
uv sync --all-extras
uv run ruff check .
uv run black --check .
uv run pytest
```

O comando de CI deve usar `black --check`, não `black .`, para não modificar arquivos durante validação.

### 14.2 Terraform

Em cada repositório e ambiente:

```bash
terraform fmt -check -recursive
terraform init
terraform validate
terraform plan
```

### 14.3 Kubernetes

```bash
kubeconform -strict k8s/
kubectl rollout status deployment/oficina-api -n oficina-api
kubectl get hpa -n oficina-api
kubectl get pdb -n oficina-api
```

### 14.4 Cenário ponta a ponta

1. Criar cliente ativo (via fluxo ADMIN) e sua OS.
2. Autenticar administrador com o novo contrato de claims e executar uma ação administrativa.
3. Autenticar por CPF no Gateway pelo domínio customizado.
4. Repetir uma chamada autenticada e uma tentativa de abuso pela URL nativa do Gateway, confirmando que o rate limit também se aplica a ela.
5. Consultar a própria OS.
6. Tentar consultar OS de outro cliente e receber `404`.
7. Aprovar orçamento próprio.
8. Confirmar reserva atômica de estoque.
9. Atualizar estados até finalização.
10. Confirmar histórico (incluindo ciclos repetidos) e métricas por status.
11. Confirmar outbox, Pub/Sub, notificação e o link de ação do e-mail funcionando.
12. Encontrar trace e logs pelo correlation ID no Datadog.
13. Forçar falha controlada e confirmar monitor.
14. Executar novo deploy e comprovar imagem/migration pelo mesmo SHA.
15. Validar rollback: smoke test da imagem N-1 contra o schema N em homologação.

### 14.5 Evidências a guardar

- URLs dos quatro repositórios.
- Screenshots das branch protections.
- Execuções de CI/CD de homologação e produção.
- URL do Gateway e Swagger.
- `terraform plan` sem segredos.
- Pods, HPA e rollout.
- Cloud SQL privado, backup e PITR.
- Dashboard, trace, logs e alerta Datadog.
- Teste de cliente A versus cliente B.
- Notificação e replay de DLQ.
- Confirmação de `soat-architecture` nos quatro repositórios.

## 15. Roteiro do vídeo de até 15 minutos

| Tempo | Demonstração |
|---|---|
| 0:00-1:00 | Arquitetura e quatro repositórios |
| 1:00-3:00 | Autenticação por CPF e conteúdo não sensível do JWT |
| 3:00-5:00 | Consumo de APIs protegidas e autorização por propriedade |
| 5:00-7:00 | Pipeline em PR e deploy automático |
| 7:00-9:00 | GKE, HPA e Cloud SQL gerenciado |
| 9:00-11:00 | Processamento serverless de notificação |
| 11:00-14:00 | Datadog: dashboard, logs, correlation ID, trace e alerta |
| 14:00-15:00 | Links, documentação e conclusão |

Não mostrar secrets, CPF real, tokens completos ou dados pessoais no vídeo.

## 16. Ordem, dependências e estimativa

| Ordem | Pacote | Dependência | Estimativa |
|---:|---|---|---:|
| 1 | Pacote 0: estabilização | Nenhuma | 3-5 dias |
| 2 | Pacote 1: modelagem/histórico | Pacote 0 | 2-4 dias |
| 3 | Pacote 2: autorização | Pacotes 0-1 | 2-3 dias |
| 4 | Pacote 3: repositórios | Baseline estável | 1-2 dias |
| 5 | Pacote 4: plataforma GCP | Decisões cloud e repositórios | 3-5 dias |
| 6 | Pacote 5: Cloud SQL | Rede pronta | 2-3 dias |
| 7 | Pacote 6: aplicação GKE | GKE e Cloud SQL | 2-4 dias |
| 8 | Pacote 7: autenticação | Cloud SQL, KMS e VPC connector | 2-4 dias |
| 9 | Pacote 8: Gateway | Aplicação e Function disponíveis | 2-4 dias |
| 10 | Pacote 9: notificações | Outbox e Pub/Sub | 3-5 dias |
| 11 | Pacote 10: observabilidade | Serviços implantados | 3-5 dias |
| 12 | Pacote 11: CI/CD final | Todos os repositórios | 2-4 dias |
| 13 | Pacote 12: documentação | Arquitetura estabilizada | 2-3 dias |
| 14 | Validação e vídeo | Todos os pacotes | 2-3 dias |

> **[R-10] Nota sobre CI incremental e dependências:** o Pacote 11 contém os workflows completos de deploy, mas os pacotes anteriores **não devem operar sem nenhum CI**. O Pacote 3 exige a criação do CI mínimo (lint + testes + validação estática) em cada repositório desde o primeiro PR. O spike do Pacote 8 exige que a infraestrutura de rede (Pacote 4) e o Cloud SQL (Pacote 5) existam antes da Function (Pacote 7). Pacotes anteriores ao Pacote 11 usam workflow local/manual para deploys e o CI mínimo para validação; os workflows de deploy automático chegam no Pacote 11, mas não podem ser o único ponto de controle.


Estimativa sequencial total: 31 a 54 dias úteis, dependendo da experiência com GCP, disponibilidade de domínio/contas e resultado do spike do Gateway. Atividades documentais e de observabilidade podem ocorrer em paralelo, mas a ordem das dependências técnicas deve ser preservada.

## 17. Definição de pronto da Fase 3

A entrega só deve ser declarada concluída quando houver evidência de que:

- Existem quatro repositórios com README, CI/CD e proteção de branch.
- Homologação e produção possuem deploy automatizado.
- O usuário `soat-architecture` foi adicionado aos quatro repositórios.
- O Gateway é a entrada pública e o backend não pode ser contornado.
- Cliente ativo autentica por CPF; inválido, inexistente e inativo não autenticam.
- JWT possui assinatura assimétrica, issuer, audience, expiração e rotação documentada.
- Cliente acessa somente seus dados e suas OS.
- Aprovação de orçamento é autenticada, idempotente e transacional.
- Estoque permanece consistente sob falha e concorrência.
- Aplicação roda no GKE com escalabilidade demonstrada.
- Banco roda no Cloud SQL privado com backup e PITR.
- Terraform provisiona a infraestrutura e usa state remoto isolado.
- Notificações são processadas por solução serverless com retry e DLQ.
- Logs são JSON e possuem correlação sem dados sensíveis.
- Datadog mostra latência, recursos, uptime, volume de OS, tempos por status e erros de integração.
- Existe alerta demonstrável para falha de processamento de OS.
- Diagramas, RFCs, ADRs e modelo ER correspondem ao ambiente implantado.
- O vídeo e o PDF final contêm todos os links exigidos.

## 18. Pontos de parada obrigatórios para o modelo implementador

O modelo deve parar e pedir confirmação humana quando:

- A região, IDs dos projetos ou domínio ainda não estiverem definidos.
- Um `terraform plan` indicar destruição ou substituição de banco, cluster, rede ou state.
- O spike do API Gateway não impedir acesso direto ao GKE.
- Uma migration exigir perda ou transformação irreversível de dados.
- O custo estimado ultrapassar o orçamento informado.
- Uma decisão sobre múltiplas unidades, CNPJ, OTP ou retenção de dados alterar o escopo.
- Houver segredo real versionado ou indício de vazamento.
- Alterações concorrentes de outro colaborador entrarem em conflito com o pacote atual.

Fora desses casos, o modelo deve concluir cada pacote com implementação, testes, documentação e evidências antes de iniciar o próximo.
