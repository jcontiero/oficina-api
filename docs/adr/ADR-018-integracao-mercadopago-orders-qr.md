# ADR-018: Integração com Mercado Pago via Orders API (QR Dinâmico, Webhook Assinado e Resolução do Endpoint de Estorno)

- **Data:** 2026-11-16
- **Status:** Aceito (Fase 4 — Etapa P1)
- **Contexto:** O enunciado da Fase 4 determina que o Billing Service se integre ao Mercado Pago para geração e verificação de pagamentos. O link histórico presente no PDF do desafio aponta para a documentação antiga de QR Code dinâmico, que foi sucedida pela **Orders API (`/v1/orders`)** na documentação vigente do Mercado Pago. Além disso, durante o planejamento foi identificada uma divergência documental entre exemplos textuais que mencionavam `/refunds` (plural, herdado da Payments API) e a referência de API de Orders que expõe `/v1/orders/{order_id}/refund` (singular).

## Decisão

1. **Adoção da Orders API com QR Dinâmico (`type = "qr"`, `mode = "dynamic"`):**
   - Não substituir o QR dinâmico por Checkout Pro de redirecionamento.
   - O Billing Service cria cobranças via `POST https://api.mercadopago.com/v1/orders` enviando:
     - Header `Authorization: Bearer <MP_ACCESS_TOKEN>` e `X-Idempotency-Key: <UUID estável por operação>`.
     - Corpo com `type: "qr"`, `external_reference: "<pagamento_id>"`, `total_amount: "<valor formatado com 2 casas decimais via Decimal>"`, `config.qr: {"pos_id": "<external_pos_id>", "mode": "dynamic"}` e `transactions.payments: [{"amount": "<valor>"}]`.
   - O QR Code dinâmico (`qr_data`) retornado em `type_response.qr_data` é persistido e exposto ao cliente na consulta do pagamento.

2. **Resolução Definitiva da Divergência de Cancelamento vs. Reembolso (`cancel` vs. `refund`):**
   - Com base na referência oficial vigente da Orders API do Mercado Pago e validação de contrato realizada na Etapa P1 (`spikes/mercadopago_qr/`):
     - **Cancelamento de Order Pendente (`created` / `action_required`):**
       - Endpoint: **`POST https://api.mercadopago.com/v1/orders/{order_id}/cancel`**
       - Headers: `Authorization: Bearer <TOKEN>`, `X-Idempotency-Key: <UUID estável>`
       - Corpo: vazio (`{}`)
       - Resposta esperada: `200 OK` (status da order passa a `canceled`).
     - **Reembolso Integral de Order Paga/Processada (`processed`):**
       - Endpoint canônico da Orders API: **`POST https://api.mercadopago.com/v1/orders/{order_id}/refund`** *(singular; o path `/refunds` no plural pertence à API legada `/v1/payments/{id}/refunds` e não deve ser usado para `/v1/orders`)*.
       - Headers: `Authorization: Bearer <TOKEN>`, `X-Idempotency-Key: <UUID estável>`
       - Corpo para reembolso total: vazio (`{}`)
       - Resposta esperada: `201 Created` (status da order passa a `refunded`).

3. **Persistência Prévia de Operações (`provider_operations`) e Reconciliação antes de Cancelar:**
   - Antes de qualquer chamada HTTP ao Mercado Pago (`CRIAR_ORDER`, `CANCELAR_ORDER`, `ESTORNAR_ORDER`), o Billing grava um registro em `provider_operations` com `idempotency_key` determinística (ex.: `create-order:{saga_id}:{rodada}` ou `refund-order:{pagamento_id}`) e status `PENDENTE`.
   - Um timeout HTTP ou erro 5xx na criação ou estorno **nunca** é tratado como evidência de que a operação não ocorreu: o worker de reconciliação consulta `GET /v1/orders/{order_id}` ou reenvia a requisição com a mesma `X-Idempotency-Key` antes de responder `CobrancaCancelada.v1` ou `PagamentoEstornado.v1`.

4. **Validação Criptográfica do Webhook (`x-signature`) e Confirmação Ativa:**
   - O endpoint `POST /webhooks/mercadopago` extrai `ts` e `v1` do cabeçalho `x-signature`, reconstrói o manifesto oficial `id:{data_id};request-id:{x_request_id};ts:{ts};` e valida o HMAC-SHA256 com `MP_WEBHOOK_SECRET` usando comparação em tempo constante (`hmac.compare_digest`).
   - Assinaturas inválidas retornam `401 Unauthorized`. Notificações válidas são gravadas em `webhook_inbox` e respondidas com `200 OK`, disparando a consulta ativa `GET /v1/orders/{order_id}` no provedor para conferir `external_reference`, moeda (`BRL`), `total_amount` em centavos e `status == "processed"` antes de emitir `PagamentoConfirmado.v1`.

5. **Uso de Adaptador Real vs. Fake Determinístico:**
   - Testes unitários, de contrato e a suíte BDD em CI utilizam `FakeMercadoPagoOrdersProvider` (que implementa a mesma porta `ProvedorPagamento` e gera assinaturas HMAC válidas).
   - O aceite de integração da Etapa P5/P7 utiliza o cliente HTTP real (`MercadoPagoOrdersClient`) apontando para o ambiente de testes do Mercado Pago com credenciais injetadas via Secret Manager.

## Consequências

- **Positivas:** Conformidade com o modelo atual de QR Dinâmico (Orders API) do Mercado Pago; eliminação do risco de chamadas 404 no estorno por uso do path legado `/refunds`; proteção contra webhooks forjados e contra cobranças/estornos duplicados.
- **Trade-offs:** Requer provisionamento prévio de Caixa/POS (`external_pos_id`) e credenciais de teste na conta de desenvolvedor do Mercado Pago para o teste de ponta a ponta em nuvem.
