# Correções do aceite em homologação — 17/11/2026

As correções desta rodada tratam as divergências encontradas entre os testes locais e a configuração real do GCP. O Firestore Native permanece como banco exclusivo de Execução; OS e Billing mantêm PostgreSQL com bancos e usuários próprios.

## Alterações

- OS: desativação dos domínios legados no ambiente distribuído, identidade correta da Function, BDD obrigatório no deploy manual, verificação dos checks para o SHA exato e versão correta nos logs.
- Billing: CLIENT_JWKS_URL, provedor fake compartilhado e transacional, idempotência persistida entre pods/reinícios, remoção da inferência de estado do provedor a partir da tabela de pagamentos, autorização ADMIN nas simulações e claim de outbox com bloqueio de linhas.
- Execução: rejeição de IDs inválidos no diagnóstico antes da publicação e manutenção do Firestore Native.
- Serverless: audience OIDC alinhada ao OS, catálogo/estoque encaminhados para Execução, correção da rota de reprocessar estorno, rotas de entrega e consulta com JWT obrigatório nos serviços.
- Mensageria: permissão do service agent para consumir subscriptions e publicar nas DLQs; subscriptions de retenção por sete dias. Esses nove recursos foram aplicados em homologação por planos salvos, sem alterações ou exclusões de outros recursos.
- APM: extração e ativação do contexto real de trace nos três consumidores, propagação do contexto HTTP para eventos e restauração após cada mensagem. Agent com chart oficial fixado, chave sensível, requests dimensionados e falha explícita quando a chave não estiver disponível.

## Validação local

| Serviço | Testes aprovados | Cobertura |
| --- | ---: | ---: |
| OS/API | 222 | 88,73% |
| Billing | 30 | 87,91% |
| Execução | 70 | 87,33% |

As simulações financeiras exigem ADMIN. Os três endpoints novos do Gateway retornaram 401 sem JWT nos testes diretos contra as APIs locais. O provedor fake tem testes de concorrência e recuperação por outra instância após reinício. O BDD usa o mesmo PostgreSQL e os emuladores Firestore/PubSub da stack integrada.

## Publicação e pendências operacionais

As correções foram publicadas em PRs para revisão pelos checks obrigatórios. Atualização dos workloads e aceite em homologação devem usar um manifesto de commits/digests consistente. Nenhuma implantação de produção faz parte desta rodada.

Instalação e comprovação de recebimento no Datadog dependem de DATADOG_API_KEY válido. O aceite externo do Mercado Pago depende de credenciais de teste válidas e do webhook público. O provedor fake, mesmo compartilhado, não comprova o contrato externo.

PRs: oficina-billing #14, oficina-execucao #10, oficina-serverless #9 e oficina-k8s-infra #9. Registrar os resultados finais de CI, deploy e aceite quando concluídos; não apresentar os estados ainda pendentes como aprovados.

## Evidências adicionais

O teste em PostgreSQL real executou 16 chamadas concorrentes com uma mesma chave e criou uma única ordem; outra instância consultou o estado após reinício e repetiu o estorno de forma idempotente. As migrations do Billing foram aplicadas do zero em um banco PostgreSQL local descartável até 20261117_fake_provider.

A reexecução do BDD sem limpar dados revelou uma colisão nos IDs fixos de webhook do fake. A correção gera IDs estáveis por ordem e ação. Após a correção, os dois cenários passaram novamente sobre os dados persistidos (27,31 segundos). O CI passa a executar as duas rodadas sobre a mesma stack.

O Ingress existente não possuía HTTPS. Foi criado o ManagedCertificate oficina-homolog-cert e adicionada a referência ao mesmo Ingress, preservando IP e backends. Aguardar status Active e verificar TLS antes de aplicar a configuração HTTPS do Gateway. A infraestrutura não deve ser declarada pronta apenas por esse recurso ter sido criado.

## Promoção aprovada da main para homologação

O SonarCloud retornou `Organization is not allowed to access data from non main branches` nas análises diretas de homolog. A decisão adotada é implantar o SHA exato da main com CI/Sonar/BDD aprovados no GitHub Environment homolog. Os workflows desta rodada têm destino fixo homolog e aceitam somente a main protegida; não possuem opção para implantar produção. A política do Environment homolog permite essa origem protegida. Limites e exclusões do Sonar permanecem iguais, e análises de main e PRs continuam bloqueantes.

O aceite externo autorizado identificou a dependência requests ausente na Function. Foi declarada a extra `google-auth[requests]` no manifesto do pacote de produção e no pyproject, com atualização dos locks e teste do transporte OIDC padrão. O aceite deve ser reexecutado após o deploy dessa correção.

Comandos de deploy após aprovação dos checks do SHA da main:

```sh
gh workflow run deploy.yml --repo jcontiero/oficina-api --ref main -f confirm_deploy=true
gh workflow run deploy.yml --repo jcontiero/oficina-billing --ref main -f confirm_deploy=true
gh workflow run deploy.yml --repo jcontiero/oficina-execucao --ref main -f confirm_deploy=true
```

Os comandos acima têm destino exclusivamente em homologação. O deploy Serverless usa confirm_cloud_apply=true e backend services/oficina-serverless/homolog. A instalação do Agent é uma operação separada na plataforma compartilhada, limitada ao módulo Datadog e dependente da chave configurada no GitHub.
