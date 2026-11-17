# ADR-016: Padrão Saga Orquestrado Persistente, Fluxo de Estados e Barreira de Compensação

- **Data:** 2026-11-16
- **Status:** Aceito (Fase 4 — Etapa P1)
- **Contexto:** O processo de atendimento de uma Ordem de Serviço (diagnóstico, geração de orçamento, aprovação pelo cliente, reserva de peças, cobrança via Mercado Pago e execução do reparo) abrange três microsserviços independentes com bancos distintos. É obrigatório aplicar o Saga Pattern com rollback/compensação segura em caso de falha em qualquer etapa e justificar a escolha entre orquestração e coreografia.

## Decisão

1. **Escolha: Saga Orquestrada Persistente dentro do OS Service (`oficina-api`):**
   - **Justificativa frente à Coreografia:** O fluxo possui ramificações críticas (recusa de orçamento que reinicia rodada de diagnóstico, falta de estoque, expiração de pagamento, falha de enfileiramento após pagamento confirmado e disputa concorrente entre início de reparo e cancelamento). Na coreografia, a máquina de estados e a ordem de compensação ficariam espalhadas nos três serviços, dificultando auditoria, timeouts e a barreira obrigatória antes do estorno financeiro. Um orquestrador persistente dentro do próprio `oficina-api` (executado em worker dedicado compartilhando o banco do OS) centraliza a máquina de estados sem introduzir um quarto microsserviço.

2. **Ordem de Negócio (Cobrança antes da Fila de Execução):**
   - Fluxo de avanço por rodada (`saga_id` único por rodada da OS):
     `ABERTA` → `DIAGNOSTICO` → `GERANDO_ORCAMENTO` → `AGUARDANDO_APROVACAO` → `RESERVANDO_PECAS` → `CRIANDO_COBRANCA` → `AGUARDANDO_PAGAMENTO` → `ENFILEIRANDO` → `EM_EXECUCAO` → `CONCLUIDA`.
   - Reservar as peças e confirmar o pagamento no Mercado Pago **antes** de enfileirar a OS para reparo garante que a oficina não inicie trabalho sem cobertura financeira/material e permite demonstrar de forma determinística a compensação financeira (`EstornarPagamento.v1`) + liberação de peças (`LiberarReserva.v1`) caso o enfileiramento na Execução falhe ou seja rejeitado.

3. **Separação entre Estado Técnico da Saga e Status Público da OS (`StatusOS`):**
   - `StatusOS` recebe os novos estados públicos: `AGUARDANDO_PAGAMENTO`, `AGUARDANDO_EXECUCAO`, `COMPENSACAO_PENDENTE` e `CANCELADA`.
   - Prioridade de listagem operacional (excluindo `FINALIZADA`, `ENTREGUE` e `CANCELADA`):
     `EM_EXECUCAO` (1) → `AGUARDANDO_EXECUCAO` (2) → `AGUARDANDO_PAGAMENTO` (3) → `AGUARDANDO_APROVACAO` (4) → `AGUARDANDO_ORCAMENTO` / `EM_DIAGNOSTICO` (5) → `RECEBIDA` (6), ordenadas das mais antigas para as mais recentes (`criada_em ASC`).

4. **Ordem Obrigatória de Compensação (Barreira de Bloqueio da Execução):**
   - Sempre que uma compensação for acionada após reserva ou pagamento, a Saga **nunca** dispara estorno ou liberação de estoque diretamente. Ela percorre obrigatoriamente os subestados persistidos:
     1. **`COMPENSANDO_BLOQUEIO_EXECUCAO` (Barreira):** O Orquestrador emite `CancelarExecucao.v1` para o serviço de Execução e aguarda `ExecucaoCancelada.v1`. Na Execução, `CancelarExecucao.v1` grava atomicamente um *tombstone* terminal em `controle_saga/{saga_id}` na mesma disputa transacional usada por `iniciar_reparo` e `enfileirar_execucao`.
        - Se o reparo físico já tiver sido iniciado pelo mecânico, a Execução responde `ExecucaoCancelamentoRecusado.v1` (`motivo: REPARO_INICIADO`). Nesse caso, a Saga transiciona para **`INTERVENCAO_MANUAL`** (OS permanece em `COMPENSACAO_PENDENTE`) e **não** estorna o pagamento nem repõe peças já consumidas.
     2. **`COMPENSANDO_EFEITOS`:** Somente após receber e persistir `ExecucaoCancelada.v1` (carregando `execucao_cancelada_event_id` para auditoria), o Orquestrador emite os comandos aplicáveis:
        - `LiberarReserva.v1` → aguarda `ReservaLiberada.v1`;
        - `CancelarOrcamento.v1` → aguarda `OrcamentoCancelado.v1`;
        - `CancelarCobranca.v1` (se cobrança pendente/desconhecida) → aguarda `CobrancaCancelada.v1`; ou
        - `EstornarPagamento.v1` (se pagamento confirmado) → aguarda `PagamentoEstornado.v1`.
     3. **`COMPENSADA`:** Somente quando todos os efeitos esperados forem confirmados pelos respectivos serviços donos a Saga encerra como `COMPENSADA` e atualiza a OS para `CANCELADA` (ou `EM_DIAGNOSTICO` em caso de recusa de orçamento/falta de peça antes de pagamento).

5. **Tratamento de Pagamento Tardio Pós-Cancelamento:**
   - Se o provedor confirmar um pagamento após a Saga estar `COMPENSADA`/`CANCELADA`, o Billing registra o fato financeiro e emite `PagamentoConfirmado.v1`. O Orquestrador não reabre a execução: verifica a barreira confirmada, abre tarefa financeira de estorno (`compensacao_financeira_status = PENDENTE`), emite `EstornarPagamento.v1` e só marca `compensacao_financeira_status = CONCLUIDA` após `PagamentoEstornado.v1`.

## Consequências

- **Positivas:** Impossibilidade de corrida onde o cliente recebe estorno enquanto o mecânico inicia o reparo; rastreabilidade completa em `saga_instances` e `saga_steps`; recuperação segura após queda de pod ou falha transitória de rede.
- **Trade-offs:** Maior número de mensagens por compensação devido à etapa de barreira (`CancelarExecucao.v1` → `ExecucaoCancelada.v1`).
