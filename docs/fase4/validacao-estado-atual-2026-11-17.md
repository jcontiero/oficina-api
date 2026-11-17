# Validação da implementação atual — 17/11/2026

## Parecer

A implementação atual passa nas suítes locais e no BDD integrado com provedor financeiro fake. Os checks consultados na main dos seis repositórios estão aprovados, com deploy da API ignorado nesse evento. A homologação no GCP já existe e responde às verificações de prontidão, mas apresenta problemas de configuração e processamento. Não considero o aceite operacional completo.

Esta auditoria confrontou os commits atuais da main, arquivos locais, checks do GitHub e configurações efetivas do GCP/GKE. Não foram realizados merge, apply, deploy, alterações de segredos ou operações financeiras. As consultas de prontidão podem executar a verificação técnica de escrita do próprio serviço no Firestore; não foi aberto nenhum fluxo de negócio na nuvem. A stack Docker temporária foi removida após os testes.

## Testes reproduzidos

| Repositório | Testes aprovados | Cobertura |
| --- | ---: | ---: |
| oficina-api | 220 | 88,62% |
| oficina-billing | 23 | 86,25% |
| oficina-execucao | 66 | 86,17% |
| oficina-serverless | 28 | 97,66% |

Adicionalmente: 2 cenários pytest-bdd aprovados em 25,95 segundos, com as três APIs, workers, PostgreSQL, Firestore Emulator, Pub/Sub Emulator e provedor fake. Foram usados snapshots dos commits da main, com dependências instaladas a partir dos locks usando Python 3.12. A stack foi isolada pelo nome `oficina-validacao-atual`.

O BDD valida os fluxos definidos nos scripts e suas entradas de teste. Não cobre automaticamente a configuração efetiva de homologação, todos os formatos de dados reais ou o contrato externo do Mercado Pago. A suíte local da API utiliza SQLite; o BDD inclui PostgreSQL. Esta rodada não reproduziu isoladamente todos os probes concorrentes históricos.

## Problemas que precisam de correção

### V01 — Alta: monólito legado habilitado no OS em homologação

Evidência: `oficina-api-config` contém `ENABLE_LEGACY_MONOLITH_DOMAINS=true`. O OpenAPI servido pela API em execução inclui `/servicos`, `/pecas`, suas operações por ID e `/pecas/{id}/repor-estoque`. O arquivo `oficina-api/k8s/configmap.yaml` também mantém true.

Impacto: o serviço de OS continua expondo os domínios extraídos. Não está demonstrada a garantia de escritor único por domínio no ambiente distribuído.

Correção: definir a flag como false no ambiente distribuído e ajustar o Gateway/consumidores para os donos corretos das rotas. Verificar também todos os casos de uso mutadores legados, além de catálogo/peças. Aceite: chamadas legadas mutadoras não produzem alterações e catálogo/estoque/execução são atendidos pelo serviço de Execução.

### V02 — Alta: audience OIDC da Function diverge da audience exigida pelo OS

Configuração efetiva da Function `oficina-auth-function-homolog`:

- `OS_AUTH_LOOKUP_URL=https://8.233.80.186.sslip.io/internal/clientes/autenticacao`
- `OS_AUTH_LOOKUP_AUDIENCE=https://8.233.80.186.sslip.io/internal/clientes/autenticacao`

Configuração do OS: `INTERNAL_AUTH_AUDIENCE=https://api.oficina.internal/internal/clientes/autenticacao`.

O repositório HTTP da Function usa a audience configurada para obter o ID token. O OS valida essa audience explicitamente em `src/identidade/apresentacao/rotas.py`. As duas configurações não concordam; mesmo com conectividade, o token emitido para uma audience não atende à outra. A consulta não executou autenticação com CPF real.

Correção: adotar uma única audience explícita e compatível nos dois lados; conferir URL, TLS, conectividade e allowlist da service account. Aceite: autenticação de cliente por CPF via Gateway, sem contornar a Function, com testes negativos de audience e identidade indevidas.

### V03 — Alta: Billing procura o JWKS de clientes em localhost

Evidência: ConfigMap fornece `JWKS_URL`, enquanto o campo consumido pelo Billing é `CLIENT_JWKS_URL`. A leitura de `Configuracoes()` no pod confirmou `client_jwks_url=http://localhost:8080/.well-known/jwks.json`. Não há chaves públicas estáticas alternativas configuradas. O JWKS administrativo aponta corretamente para o OS.

Impacto: a autenticação de clientes no Billing consulta um endereço local incorreto, impedindo o fluxo normal de decisão do orçamento.

Correção: configurar `CLIENT_JWKS_URL` com o endpoint público de clientes por ambiente e validar assinatura/issuer/audience. Aceite: cliente aprova seu próprio orçamento; outro cliente recebe 403; token inválido recebe 401.

### V04 — Alta: worker do Billing registra falhas repetidas

Evidência: a amostra consultada continha 195 linhas de erro em 200 linhas recentes do worker. As cinco últimas mensagens repetiam `Erro ao processar comando no Billing: badly formed hexadecimal UUID string`.

Isso confirma falha recorrente de processamento, mas não identifica sozinho a origem do campo inválido, a quantidade de mensagens distintas ou a efetividade da DLQ. Não se deve atribuir o problema a uma mensagem específica sem investigação.

Correção: identificar evento/comando e campo inválido com IDs correlacionados; validar o contrato de entrada; confirmar retry, encaminhamento à DLQ e recuperação controlada. Evitar exclusão indiscriminada de mensagens. Aceite: mensagem inválida tem destino diagnosticável, mensagens válidas continuam processando e o worker deixa de repetir o mesmo erro continuamente.

### V05 — Alta: fake financeiro em memória não é compartilhado entre os pods

Evidência: Billing em homologação usa `MP_PROVIDER_MODE=fake` e `mp_fake_state_file` vazio. Existem três réplicas da API e um worker. O adaptador fake mantém ordens e cache de idempotência em memória quando não há persistência configurada.

Impacto inferido do código e da topologia: processos distintos não veem as mesmas ordens e o estado é perdido ao reiniciar. O sucesso do Compose, que usa persistência compartilhada do fake, não comprova o mesmo comportamento no GKE.

Correção: para demonstração fake distribuída, usar um provedor fake acessível por HTTP com armazenamento compartilhado e operações concorrentes seguras. Para o aceite externo, configurar o adaptador real com credenciais de teste. Não presumir que um arquivo local por pod resolve compartilhamento ou concorrência.

### V06 — Média: Datadog ainda não demonstrado no cluster

Evidência: nenhum namespace, pod, Deployment ou DaemonSet com nome Datadog foi encontrado no inventário consultado. Aplicações têm `DD_TRACE_ENABLED=true`, o que por si só não comprova entrega de traces. Não foi consultado o Datadog para procurar um destino externo alternativo.

Correção: concluir a instalação/configuração do Agent prevista no plano ou comprovar o destino alternativo, conectividade e recebimento. Aceite: trace de uma Saga atravessando os três serviços, com logs correlacionados, ambiente e versão corretos.

### V07 — Média: versão implantada não corresponde a um manifesto único aprovado

Billing está com imagem `0dc029d`, correspondente ao PR #12 ainda aberto na consulta; a main auditada é `f9fa846...`. Execução usa uma imagem na API e outra no worker. Os valores `DD_VERSION` nos três serviços também não correspondem às tags implantadas.

Uma diferença de SHA entre branch e commit de merge não prova diferença de conteúdo. Porém, não se pode apresentar o BDD da main como evidência direta dessas imagens sem comparar os conteúdos/digests.

Correção: integrar as correções aprovadas, gerar manifesto de release com commits e digests, verificar API/worker e propagar a versão correta à telemetria. Reexecutar o aceite com esse manifesto.

### V08 — Média: deploy manual da API não depende do BDD nessa execução

Na main consultada, `build-push-deploy` depende apenas de `validate`; `bdd-integrado` só executa em push/pull_request. O workflow_dispatch permite deploy sem executar o BDD nesse mesmo evento. Os checks consultados na main estão verdes, mas essa condição não é garantida pelo job de deploy para qualquer execução futura.

Correção: exigir evidências aprovadas para o SHA exato antes do deploy, incluindo BDD e Quality Gate, ou organizar as dependências para executar as verificações no fluxo manual. Preservar o controle de autorização enquanto o aceite estiver pendente.

## Situação real da infraestrutura

No projeto `fiap-project-514922` existem GKE, Cloud SQL, Functions, API Gateway e Firestore. O cluster `oficina-gke-cluster` estava RUNNING, com dois nós. Cloud SQL `oficina-postgres-db` estava RUNNABLE. As três APIs responderam HTTP 200 em `/health/ready`; Execução informou Firestore `oficina-execucao-homolog` conectado. O JWKS administrativo retornou o mesmo hash nas três réplicas consultadas da API.

Há workloads de negócio em `oficina-homolog`; não foi identificado ambiente de produção equivalente. Assim, os relatos antigos de zero provisionamento descrevem uma etapa anterior, e não o estado atual. Esta auditoria não provisionou recursos.

## Pendências para aceite

1. Corrigir V01–V05 e estabilizar o processamento de mensagens em homologação.
2. Unificar release/API/worker e evidências por commit/digest; concluir PR Billing #12 conforme checks e revisão.
3. Demonstrar autenticação de cliente e fluxo completo pelo Gateway na homologação corrigida, com autorização, cancelamento/estorno e recuperação após reinício.
4. Concluir Datadog APM e correlação efetiva entre serviços (R11 operacional).
5. Executar aceite externo do Mercado Pago com credenciais de teste e webhook HTTPS, preservando idempotência e compensações. O modo fake atual não substitui esse aceite.
6. Confirmar distribuição/rotação das chaves RS256 e controles por ambiente. A estabilidade do JWKS administrativo entre réplicas é um sinal positivo, mas não valida toda a operação de segredos nem a Function de clientes.
7. Concluir ambientes, documentação, diagramas, runbooks, vídeo e demais itens de entrega conforme o HTML/enunciado. Esta rodada não auditou o vídeo nem encerrou esses itens.

## Evidências e limites

Os arquivos em `evidencias-validacao-atual-2026-11-17/` contêm manifesto de commits, checks retornados pelo GitHub, resumos/JUnit dos testes e configurações selecionadas sem valores de segredos. Logs completos da stack temporária ficaram em `/tmp/oficina-validacao-atual/`, sujeitos à limpeza do sistema.

A validação fez leitura de configurações e execução local. Não criou OS, reservas, pagamentos ou cancelamentos na nuvem. Os impactos de configuração foram fundamentados no código e no estado observado; os fluxos afetados ainda precisam do aceite em homologação após correção. Não foi feita auditoria exaustiva de IAM, de todos os recursos Terraform ou de todas as combinações concorrentes.
