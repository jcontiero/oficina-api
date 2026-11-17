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
| Billing | 29 | 87,89% |
| Execução | 70 | 87,33% |

As simulações financeiras exigem ADMIN. Os três endpoints novos do Gateway retornaram 401 sem JWT nos testes diretos contra as APIs locais. O provedor fake tem testes de concorrência e recuperação por outra instância após reinício. O BDD usa o mesmo PostgreSQL e os emuladores Firestore/PubSub da stack integrada.

## Publicação e pendências operacionais

As correções foram publicadas em PRs para revisão pelos checks obrigatórios. Atualização dos workloads e aceite em homologação devem usar um manifesto de commits/digests consistente. Nenhuma implantação de produção faz parte desta rodada.

Instalação e comprovação de recebimento no Datadog dependem de DATADOG_API_KEY válido. O aceite externo do Mercado Pago depende de credenciais de teste válidas e do webhook público. O provedor fake, mesmo compartilhado, não comprova o contrato externo.

PRs: oficina-billing #14, oficina-execucao #10, oficina-serverless #9 e oficina-k8s-infra #9. Registrar os resultados finais de CI, deploy e aceite quando concluídos; não apresentar os estados ainda pendentes como aprovados.
