# Validação da implementação — fases P0 a P6 e preparação da P7

Data: 17/11/2026. Revisão dos seis repositórios integrados em `main`, com execução independente de testes e consulta aos checks do GitHub.

## Parecer

A base distribuída existe e os dois cenários BDD passam. Entretanto, a implementação ainda apresenta falhas de atomicidade, ordenação de eventos, compensação financeira e regras de execução/estoque. **Não recomendo iniciar o provisionamento antes de corrigir os bloqueadores locais deste relatório.**

A aprovação anterior dos PRs e do BDD é válida para os checks e cenários executados. Ela não comprova os comportamentos de falha adicionais reproduzidos nesta revisão. Além disso, os runs posteriores ao merge em `main` de Billing e Execução estão reprovados no Quality Gate.

## 1. Base e método

| Repositório | Commit inspecionado |
|---|---|
| oficina-api | `2de79b7bf3a7f659237a6325d875fe0bf64f34cf` |
| oficina-billing | `59b4efa67e23b1d37670c978d09f17a971036447` |
| oficina-execucao | `2d4dc44141a3d30a45fb84d22b48d0ac64613c5f` |
| oficina-serverless | `9698c6c259b6a44820c2518eec1e41b66d905a28` |
| oficina-k8s-infra | `16a4553ff355254a5810f7b7da71c72963715217` |
| oficina-database-infra | `08ae43d4f62e4ff9e56fc975b3f72182063856cd` |

- Criadas cópias temporárias dos arquivos versionados por `git archive HEAD`, preservando os checkouts.
- Dependências instaladas dos `uv.lock`, com `uv sync --frozen --all-extras`, em ambientes temporários.
- Testes locais executados com Python 3.14.5. O CI usa Python 3.12; os números locais não substituem a medição nesse runtime.
- Testes SQL das suítes usam SQLite conforme os fixtures/CI; o BDD usa PostgreSQL e os emuladores Firestore/Pub/Sub.
- Stack Docker exclusiva `oficina-auditoria`, com fontes dos commits inspecionados montadas sobre imagens locais já disponíveis. Não foi revalidada nesta execução a resolução de dependências de um build limpo das imagens.
- Consultados os checks atuais de `main` dos seis repositórios e logs de falha de Billing/Execução.
- Não foram executados bootstrap, Terraform apply, migração de state, deploy em nuvem ou pagamento externo. Não houve inspeção autenticada de recursos GCP/Datadog nem teste de invasão abrangente.
- Arquivos não versionados com sufixo `2` foram encontrados em Billing e Execução. Foram preservados e excluídos dos snapshots de teste. O workspace completo não está limpo, embora os arquivos versionados estejam nos commits informados.

## 2. Resultados efetivamente executados

| Suíte | Resultado local | Cobertura local |
|---|---|---|
| OS: unitários + integração | 209 aprovados | 87,92% |
| Billing: unitários + integração + contrato | 16 aprovados | 85,24% |
| Execução: unitários + integração + contrato | 63 aprovados | 83,94% |
| Serverless | 28 aprovados | 97,59% |
| BDD, três APIs + três workers + PostgreSQL + emuladores | 2 cenários aprovados, 44,99 s, sem skips | Não medida nesta execução |

Os testes serverless exigem `PYTHONPATH=src`, como sua organização de imports prevê. A primeira coleta sem esse ajuste falhou; a execução corrigida passou.

O BDD confirmou o fluxo de abertura até entrega e a compensação por pagamento recusado com retomada após reinício. Não cobre sozinho os bloqueadores seguintes.

### Checks de main na consulta desta revisão

| Repositório | Resultado |
|---|---|
| oficina-api | validate, SonarQube, SonarCloud e bdd-integrado aprovados; deploy skipped |
| oficina-serverless | lint-test, SonarQube e SonarCloud aprovados |
| oficina-k8s-infra | validate, SonarQube e SonarCloud aprovados |
| oficina-database-infra | validate, SonarQube e SonarCloud aprovados |
| oficina-billing | validate reprovado no Sonar; SonarCloud Code Analysis neutral |
| oficina-execucao | validate reprovado no Sonar; SonarCloud Code Analysis neutral |

Evidências remotas dos dois bloqueios: [Billing, run 44120217636](https://github.com/jcontiero/oficina-billing/actions/runs/44120217636) e [Execução, run 44120269186](https://github.com/jcontiero/oficina-execucao/actions/runs/44120269186). Ambos registram `QUALITY GATE STATUS: FAILED` para `branch=main`; o upload da análise foi realizado. Não é o erro anterior de autenticação. Consultar as condições exatas nos dashboards e corrigir seus apontamentos, sem presumir que sejam os mesmos dos PRs.

## 3. Bloqueadores locais reproduzidos

### R01 — Commit antecipado quebra a atomicidade da Saga e da Outbox/Inbox

**Prioridade: crítica.**

OS: `oficina-api/src/atendimento/apresentacao/rotas.py:607` chama `AbrirOrdemDeServico.executar`, cujo decorador em `src/shared/aplicacao/unit_of_work.py:30` confirma a transação antes de `iniciar_saga_abertura`.

Reprodução: forçar falha ao iniciar a Saga depois de criar a OS. Resultado: HTTP 500, **1 OS persistida, 0 Sagas e 0 eventos de outbox**. Uma nova tentativa pode encontrar o veículo com OS ativa, sem fluxo que a processe.

Billing: `oficina-billing/src/orcamentos/infraestrutura/repositorios.py:61` e `:140` fazem commit dentro de `salvar` e `registrar_tombstone_barreira`. `BillingConsumidor.processar_comando` chama `salvar` antes de gravar a resposta na outbox.

Reprodução: interromper `_publicar_outbox` em GerarOrcamento. Após rollback da sessão: **1 inbox e 1 orçamento persistidos, 0 eventos de resposta**. Reentregar o comando retorna `DUPLICADO`. A Saga pode ficar esperando indefinidamente.

Correção: um único dono da transação por operação de aplicação. Repositórios devem fazer flush, não commit independente; abrir OS + Saga + outbox em um commit; consumir comando + inbox + efeito + resposta em um commit. Operações externas de pagamento precisam de intenção durável antes da chamada ao provedor, com recuperação após interrupção.

Aceite: os dois cenários de falha acima não deixam recursos parciais ou inbox confirmada sem a resposta correspondente; executar também contra PostgreSQL.

### R02 — Execução permite iniciar reparo sem pagamento e sem reserva

**Prioridade: crítica.**

Referências: `oficina-execucao/src/execucao/apresentacao/rotas.py:172` e `src/execucao/dominio/entidades.py:82`.

O diagnóstico cria um documento de execução. O endpoint `/iniciar` aceita controle ATIVO, não exige EM_FILA e prossegue mesmo sem reserva e sem pagamento_id.

Reprodução: registrar diagnóstico e chamar `/iniciar`, sem aprovação, cobrança ou enfileiramento. Resultado: **HTTP 200, status EM_EXECUCAO, pagamento_id ausente e reserva inexistente**.

Correção: iniciar somente execução enfileirada por comando válido da Saga, com controle EM_FILA, referência financeira e reserva válida (incluindo reserva lógica de lista vazia). Diagnóstico não é autorização para reparo. Repetir início não deve duplicar evento ou alterar os timestamps originais.

Aceite: o início antecipado retorna conflito; o fluxo aprovado continua passando. Testar com Firestore Emulator e a disputa entre cancelar/iniciar.

### R03 — Billing confirma compensação mesmo sem conseguir cancelar no provedor

**Prioridade: crítica.**

Referência: `oficina-billing/src/mensageria/consumidor.py:332` e `:349`.

No ramo de pagamento pendente, falhas de consulta/cancelamento são capturadas e ignoradas. O código marca CANCELADO e emite PagamentoEstornado com resultado CANCELADO_SEM_COBRANCA mesmo quando o provedor está indisponível. PENDENTE_RECONCILIACAO também pode ser finalizado sem esclarecer se uma cobrança foi criada.

Reprodução: pagamento local PENDENTE; consulta e cancelamento sempre falham. Resultado: **status local CANCELADO e evento PagamentoEstornado.v1 emitido**.

Correção: guardar resultado desconhecido e reconciliar; somente confirmar cancelamento/estorno depois de comprovação do provedor. Cancelamento precisa de operação persistida e chave estável. Não concluir a compensação por ausência de resposta.

Aceite: indisponibilidade não produz falso sucesso; após recuperação, cancela ou estorna conforme o estado financeiro real.

### R04 — Evento fora de ordem é descartado definitivamente

**Prioridade: alta.**

Referência: `oficina-api/src/saga/aplicacao/orquestrador.py:253` e `:589`.

A inbox é confirmada mesmo quando o estado atual ainda não permite aplicar o evento. Não existe fila persistida de eventos diferidos ou reavaliação posterior.

Reprodução: PagamentoConfirmado chega enquanto a Saga está CRIANDO_COBRANCA; depois chega CobrancaCriada; por fim o pagamento é reentregue. Resultados: **IGNORADO_PRECONDICAO → PROCESSADO → DUPLICADO**. Estado final AGUARDANDO_PAGAMENTO, apesar da confirmação recebida.

Correção: distinguir evento obsoleto de evento válido adiantado. Persistir o evento adiantado como pendente e reavaliá-lo quando a pré-condição chegar; a deduplicação não pode impedir sua primeira aplicação útil.

Aceite: permutações de ordem de confirmação/cobrança/enfileiramento convergem sem perda de informação ou transições repetidas.

### R05 — Liberação lógica repetida aumenta o estoque indevidamente

**Prioridade: alta.**

Referências: `oficina-execucao/src/execucao/dominio/entidades.py:128` e `src/mensageria/consumidor.py:428`.

Uma reserva já LIBERADA retorna ReservaLiberada novamente; o consumidor repõe as peças de novo. A inbox cobre event_id repetido, mas não duas mensagens distintas da mesma operação de compensação.

Reprodução: saldo inicial 10; reserva de 2; duas liberações para a mesma saga/compensação com event_ids diferentes. Resultado: **saldo 10 após a primeira liberação e 12 após a segunda**.

Correção: idempotência de negócio por reserva/compensação, além de event_id. Repor somente na transição ATIVA → LIBERADA; a repetição responde com o resultado já conhecido e não muda saldo.

Aceite: estoque retorna a 10 e permanece em 10 em qualquer quantidade de repetições/reentregas.

### R06 — Estorno de pagamento tardio não encerra a pendência financeira

**Prioridade: alta.**

Referência: `oficina-api/src/saga/aplicacao/orquestrador.py`, ramos de PagamentoConfirmado tardio e PagamentoEstornado.

A Saga COMPENSADA aceita pagamento tardio e gera estorno, mas a resposta PagamentoEstornado é tratada apenas em COMPENSANDO_EFEITOS.

Reprodução: COMPENSADA com barreira válida → pagamento tardio → confirmação de estorno. Resultado: **resposta IGNORADO_PRECONDICAO e compensacao_financeira_status permanece PENDENTE**.

Correção: acompanhar tarefa financeira mesmo em estado operacional terminal. Processar respostas de estorno e falha para a mesma operação sem reabrir o reparo.

Aceite: a tarefa financeira converge para CONCLUIDA após confirmação, mantendo o estado operacional cancelado.

### R07 — Tokens falham entre réplicas com a configuração atual sem chave persistida

**Prioridade: alta antes do deploy.**

Referências: `oficina-api/src/identidade/infraestrutura/jwt_provider.py:17`, `src/config.py:13`, `k8s/secret.yaml`; comportamento equivalente em `oficina-serverless/src/auth/keys.py`.

Sem chave PEM, cada instância gera uma chave aleatória com o mesmo kid. Os manifests existentes não configuram a chave administrativa persistida. O campo do OS é admin_jwt_private_key_pem, portanto a variável correspondente é ADMIN_JWT_PRIVATE_KEY_PEM; a documentação cita JWT_PRIVATE_KEY_PEM, que pertence à Function e não ao mesmo campo.

Reprodução: token emitido por uma instância do provider falha na segunda com **Signature verification failed**.

Correção: chaves persistidas por emissor/ambiente, nomes de configuração alinhados, rotação/kid coerentes e erro de startup em homolog/production se faltar chave. Testes locais podem gerar chave temporária explicitamente.

Aceite: login, JWKS e validação funcionam cruzando réplicas e após reinício, tanto para funcionários quanto para clientes.

## 4. Lacunas adicionais encontradas por inspeção

Estes itens foram confirmados pela leitura do código/configuração, mas não por ensaio completo concorrente ou em nuvem nesta revisão.

### R08 — Timeouts e controle concorrente da Saga ainda incompletos

**Prioridade: alta.**

- deadline_at é preenchido na criação; não foi encontrado varredor de deadlines no worker nem atualização dos prazos por etapa. Saga sem resposta pode ficar parada, sem compensação automática.
- SagaInstance.version é incrementado, mas não é usado como condição de atualização nem está configurado como version_id_col. A leitura da Saga não usa lock de linha. Eventos diferentes simultâneos podem disputar transições e efeitos_confirmados_json.
- SagaStepModel é criado para os comandos, mas as respostas não atualizam seu resultado/status; causation_id, orcamento_id/versão e aggregate_version não são confrontados de forma completa antes do avanço.
- Os publicadores selecionam e atribuem lease sem claim atômico; múltiplas réplicas podem reivindicar o mesmo lote. Lease único de 30 s para até 50 publicações de 10 s pode vencer antes do fim do lote.

Correção: implementar locks/versionamento efetivos, varredura de prazo, efeitos/etapas auditáveis e claims atômicos com renovação apropriada. Aceite com PostgreSQL/Firestore reais ou emulador e duas instâncias, incluindo duas confirmações de compensação simultâneas.

### R09 — Reconciliação financeira perde itens e contorna validações da confirmação

**Prioridade: alta.**

`oficina-billing/src/mensageria/consumidor.py:_reconciliar_pagamento_pendente` emite PagamentoConfirmado com itens_servico e itens_peca vazios e versão de orçamento fixa em 1; não chama a mesma validação de valor/referência/moeda usada no webhook. O caminho de criação reconciliada também pode marcar o pagamento confirmado sem emitir o evento financeiro correspondente.

A Execução já possui snapshot do diagnóstico em alguns fluxos, o que pode esconder a perda no teste feliz; esse snapshot não substitui o orçamento aprovado. Corrigir para um caminho único de confirmação e snapshots/versões consistentes. Testar divergência financeira no caminho de reconciliação, não apenas no webhook.

### R10 — Rodada após recusa e comandos de cancelamento incompletos

**Prioridade: alta para preservar o fluxo de negócio do plano.**

OrcamentoRecusado encerra a Saga em RECUSADA e põe a OS em diagnóstico, mas não foi encontrado endpoint/caso de uso que crie a rodada seguinte daquela OS e reinicie o diagnóstico. A criação nova usa rodada 1 por padrão.

CancelarCobranca.v1 aparece no contrato central, mas não possui ramo de execução no consumidor Billing. Há estados/eventos de compensação pendente/recusa de liberação sem tratamento correspondente completo no orquestrador. A rota HTTP cancelar-barreira usa leituras e escritas fora da transação compartilhada com iniciar, podendo furar a proteção de concorrência obtida no consumidor.

Correção: definir e implementar a continuação após recusa, completar ou retirar contratos não suportados e fazer o cancelamento HTTP passar pelo mesmo fluxo protegido. Testar nova rodada, orçamento antigo e comandos tardios.

### R11 — Observabilidade ainda não comprova correlação distribuída em runtime

**Prioridade: completar antes do aceite P7.**

Campos JSON e ddtrace estão presentes. Porém, os workers apenas repassam traceparent à outbox; não foi encontrado ponto explícito que extraia/ative esse contexto ao consumir a mensagem. Nos helpers de logs, correlacao_ctx é lido, mas não foi encontrado preenchimento por requisição/consumo. O worker OS usa um formatter reduzido. Não foi executada exportação ao Datadog.

Correção: teste de propagação HTTP → outbox → Pub/Sub → consumidor, com spans e campos de negócio efetivamente preenchidos; depois prova no Datadog com Agent instalado por Terraform. Não considerar presença dos nomes dos campos prova de correlação.

### R12 — Contrato Mercado Pago precisa de ajuste antes do aceite externo

**Prioridade: alta antes de testar externamente.**

O adaptador em `oficina-billing/src/pagamentos/infraestrutura/mercadopago.py:270` envia config.qr.pos_id; o guia oficial consultado exige config.qr.external_pos_id. Os testes MockTransport atuais não detectam essa divergência.

A busca de reconciliação usa apenas external_reference e assume o primeiro resultado, enquanto o roteiro local já cita janela begin_date/end_date. Revisar filtros suportados, paginação, igualdade exata da referência e respostas reais. Não presumir que o primeiro resultado corresponde à cobrança.

Fonte: [guia oficial de processamento QR](https://www.mercadopago.com.br/developers/pt/docs/qr-code/payment-processing), consultado em 17/11/2026. Validar assinatura a partir de amostras reais e preservar também o aceite de beneficiário/valor/moeda. O aceite externo permanece pendente; não foram enviados pagamentos nesta revisão.

## 5. P7 ainda exige implementação, além de autorização

### Infraestrutura e backend

- Os backends dos três repositórios de suporte ainda apontam para pos-fiap-2026-tf-state. Isso é histórico preservado, mas não é configuração pronta para apply no projeto novo.
- O bootstrap atual cria `${project_id}-tf-state`; o plano cita `fiap-project-514922-tfstate`. Unificar o nome antes de gerar o plan.
- O bucket atual não tem lifecycle prevent_destroy, embora o plano o prometa. Versionamento e force_destroy=false não equivalem a essa configuração.
- A service account de CI recebe roles/owner; revisar para permissões necessárias. As relações de impersonação listam somente os quatro repositórios originais; faltam Billing/Execução. A condição do provider só restringe o proprietário, sem o filtro de contexto de deploy previsto no plano.
- APIs de Firestore/PubSub/Gateway/Eventarc e demais dependências precisam ser conferidas na lista do bootstrap: o arquivo atual ainda não expressa toda a lista necessária.
- `oficina-billing/infra/main.tf` e `oficina-execucao/infra/main.tf` contêm apenas providers/variáveis/outputs, sem recursos de banco, conta ou subscription. Não há root Terraform de serviço no OS.
- O Terraform de banco ainda cria os bancos legados e usuário comum. Não implementa ainda os bancos/usuários SQL exclusivos definidos para a fase 4.
- O módulo Pub/Sub serverless ainda cria somente os tópicos legados de notificação e DLQ. A topologia da Saga implementada em integration/init_pubsub.py ainda precisa de equivalente Terraform.

### Deploys, manifests e migrations

- Os workflows de deploy de Billing e Execução terminam após autenticar no GCP; não fazem build, push, migration ou rollout.
- Seus k8s/ têm apenas Deployment da API e Service; faltam workers, ConfigMaps/Secrets e políticas/configurações por ambiente.
- Billing não contém estrutura Alembic/migrations. create_all no startup de homolog não substitui migração versionada; em production o startup não cria as tabelas.
- No OS, bdd-integrado é ignorado em workflow_dispatch e build-push-deploy depende desse job. Nas condições atuais, o deploy manual tende a ser ignorado por depender de job skipped. Corrigir a relação de execução sem eliminar o gate de qualidade.
- Os parâmetros Kubernetes do OS ainda usam JWKS de gateway antigo, defaults de homolog para audience/issuer e flag legada ativa por padrão; a parametrização precisa de overlays/configuração explícita.
- Os Dockerfiles instalam dependências com pip a partir de intervalos do pyproject, sem usar o uv.lock do CI. A imagem não garante a mesma resolução de dependências validada nos testes.
- Restaurar os gatilhos de deploy automatizado, mantendo os gates necessários, é requisito do aceite final. O bloqueio manual atual é temporário, conforme decisão anterior.

### Gateway, autenticação serverless e notificações

- O gateway.yaml ainda roteia para endpoints monolíticos; não contém as rotas novas dos três serviços nem webhook financeiro e JWKS administrativo.
- A Function precisa de chave privada persistida, ENVIRONMENT/issuer/audience por ambiente, service account de runtime e endpoint interno HTTPS/DNS/certificado validado. O Terraform atual não entrega essa configuração completa.
- Notificações ainda usam formato legado de mensagem, atributo tipo_evento e leitura direta de status_novo; os eventos da Saga usam envelope e event_type. O handler não está alinhado à estrutura Pub/Sub CloudEvent v2 recebida pelo wrapper. O código apenas registra simulação de envio; não demonstra envio real.
- Datadog está reativado no Terraform, mas instalação, coleta e tracing reais continuam pendentes. Fixar chart e revisar tratamento da chave antes de aplicar.

Essas lacunas não são evidência de falha em um deploy realizado: o deploy nunca foi executado. São trabalho restante da P7, que precisa de PRs e validação antes do apply.

## 6. Pendências de qualidade, documentação e entrega

1. Corrigir os Quality Gates atuais de main de Billing e Execução, preservando critérios. Os PRs verdes anteriores não comprovam main verde após o merge.
2. Alinhar a medição de cobertura do Sonar da API com a do pytest: sonar-project.properties ainda exclui apresentação, infraestrutura, container, main e worker, enquanto o plano prevê medir código de produção com poucas exceções justificadas. O pytest local passou acima de 80% com seu escopo atual.
3. Atualizar docs/planejamento-p7-gcp-sem-apply.md: ainda descreve P6 bloqueada por token e PRs por integrar; esses estados são históricos e já mudaram. Corrigir também nomes de secrets administrativos/Datadog e estimativas com dimensionamento concreto.
4. Revisar índices/queries, grants SQL, IAM Firestore por banco, autenticação entre ambientes e runtime identities no aceite da P7; o emulador não comprova IAM de produção.
5. Executar aceite externo Mercado Pago com credenciais de teste e webhook HTTPS. Não utilizar pagamento de produção para validar o desafio.
6. Concluir P8: READMEs de execução/deploy por serviço, diagramas finais coerentes com código, Swagger/collection, evidências de cobertura/CI, vídeo até 15 minutos, PDF de entrega e confirmação do acesso do avaliador.
7. Verificar as cópias locais não versionadas com sufixo `2`, sem removê-las automaticamente nem incluí-las em commits.

## 7. Sequência recomendada

1. **Correções locais antes da nuvem:** R01–R06, R08–R10, com testes que reproduzam os defeitos. Incorporar também a configuração de chave persistida e seus testes de réplica (R07).
2. **Qualidade integrada:** gates de main verdes; BDD feliz + compensação; novos cenários de falha; testes de concorrência PostgreSQL/Firestore; manifesto dos SHAs corrigidos.
3. **Implementar a configuração da P7 em PRs:** backend/bootstrap, infraestrutura por serviço, migrations, manifests completos, Gateway, identidades/chaves e instrumentação efetiva. Revisar Terraform plan salvo, sem apply.
4. **Autorizar bootstrap de escopo limitado**, depois das correções e da revisão concreta. Não usar o Terraform atual sem ajustes apenas porque o documento de planejamento foi aprovado.
5. **Deploy homolog e aceites externos/Datadog**, promoção controlada e P8.

## 8. Evidências locais da auditoria

Os arquivos de reprodução e logs estão em `/tmp/oficina-auditoria-completa/` nesta sessão:

- `probe_os.py`, `probe_os.py.log`: evento fora de ordem e estorno tardio.
- `probe_os_atomicidade.py`: criação de OS sem Saga após falha.
- `probe_billing.py`, `probe_billing.py.log`: commit parcial e falso cancelamento financeiro.
- `probe_execucao.py`, `probe_execucao.py.log`: início sem pagamento e liberação repetida de estoque.
- `probe-jwt.log`: assinatura inválida entre providers com chaves geradas separadamente.
- `*-pytest.log`, `*-coverage.json`, `*-junit.xml`: suítes existentes.
- `bdd-auditoria.log` e `bdd-auditoria.xml`: execução integrada.
- `github-main-checks.json` e `*-main-ci-failure.log`: resultados consultados no GitHub.

Esses diretórios temporários podem ser limpos pelo sistema. As reproduções, resultados e critérios de correção essenciais foram descritos neste relatório. Nenhum arquivo de produção foi alterado para corrigir os defeitos durante esta auditoria.

## 9. Rodada de correções locais (PRs abertos, sem merge)

As correções para R01–R12 e os apontamentos de SonarCloud foram implementados com TDD (teste reproduzindo a falha antes da correção) nos três serviços:

- **oficina-billing** (`fix/audit-r01-r03-r09-r10-r12-sonar`, commit `09747e075c5ff56ce0524a135d199cccda6858d5`, PR #5):
  - **R01:** removidos `db.commit()` internos em `OrcamentoRepositorioSql.salvar` e `registrar_tombstone_barreira`; transação única entre inbox, domínio e outbox.
  - **R03:** confirmação no provedor antes de declarar estorno/cancelamento; emissão de `PagamentoEstornoPendente.v1` em estado desconhecido (`DESCONHECIDO`).
  - **R09:** validação e população de versão e itens reais do orçamento em `PagamentoConfirmado.v1` via helper compartilhado `confirmar_pagamento_aprovado`.
  - **R10:** tratamento de `CancelarCobranca.v1`.
  - **R12:** `external_pos_id` e correspondência exata de `external_reference` na consulta ao Mercado Pago.
  - **SonarCloud:** redução de complexidade cognitiva (`S3776`) em `consumidor.py` e `rotas.py`, constante compartilhada (`S1192`) e asserções simples (`S9073`).
- **oficina-execucao** (`fix/audit-r02-r05-r10-sonar`, commit `ddcfe6a31ba84955c723d2ce869d6f5b385f10f0`, PR #5):
  - **R02:** `iniciar_reparo` e `POST /v1/execucoes/{id}/iniciar` exigem `EM_FILA`, `pagamento_id` e reserva `ATIVA`, bloqueando início prematuro ou duplicado.
  - **R05:** `liberar_apos_barreira` retorna `repor_estoque=False` (`JA_LIBERADA`) em reentrega de `LiberarReserva.v1`, impedindo reposição dupla de estoque.
  - **R10:** `cancelar-barreira` executado dentro de `executar_em_transacao`, sincronizando `status=CANCELADA` no documento de execução.
  - **SonarCloud:** refatoração de `processar_comando` (`S3776`), PEP 695 generics em `firestore_store.py` (`S6796`) e `logger.exception` em `worker.py` (`S8572`).
- **oficina-api** (`fix/audit-r01-r04-r06-r07-r08-r10-r11`):
  - **R01:** `AbrirOrdemDeServico.preparar_abertura` sem commit interno; OS, Saga, `SagaStep` e Outbox confirmados em uma única transação em `abrir_os_v1`.
  - **R04:** `PagamentoConfirmado.v1` aceito também em `CRIANDO_COBRANCA`.
  - **R06:** `PagamentoEstornado.v1`, `PagamentoEstornoFalhou.v1` e `PagamentoEstornoPendente.v1` tratados após conclusão da barreira (`COMPENSADA`, `RECUSADA`, `INTERVENCAO_MANUAL`).
  - **R07:** `JwtTokenProvider` exige `ADMIN_JWT_PRIVATE_KEY_PEM` em `homolog`/`production` (exceto quando `allow_ephemeral_admin_jwt_key=True`); `k8s/secret.yaml` atualizado para placeholders RS256.
  - **R08:** atualização de `SagaStepModel` em respostas, `expirar_sagas_vencidas` e claim atômico de outbox no worker.
  - **R10:** `reabrir_nova_rodada` e `POST /v1/ordens-servico/{id}/nova-rodada` após `RECUSADA`.
  - **R11:** propagação de `traceparent` no outbox/worker.

### Itens ainda pendentes (fora do escopo desta rodada local)

- Merges dos PRs abertos (aguardando autorização).
- Provisionamento P7 em nuvem (`bootstrap`, `terraform apply`, migração de state, deploy, Gateway/Functions/Cloud SQL/GKE/Datadog).
- Aceite externo real com Mercado Pago (credenciais de teste e URL HTTPS de webhook).
- Limpeza/inspeção manual dos arquivos não versionados com sufixo `2`.
