"""
Script de verificação do spike Mercado Pago Orders API (QR Dinâmico).
- Sem credenciais remotas: executa o ciclo completo determinístico (QR -> Webhook -> Consulta -> Refund e Cancel).
- Com MP_ACCESS_TOKEN e MP_EXTERNAL_POS_ID definidos no ambiente: testa criação, consulta e cancelamento no Sandbox real.
"""

import os
from uuid import uuid4

from spikes.mercadopago_qr.adaptador import (
    FakeMercadoPagoOrdersProvider,
    MercadoPagoOrdersClient,
    StatusPagamentoProvedor,
    validar_assinatura_webhook_mp,
    validar_confirmacao_cobranca,
)


def executar_spike_local() -> None:
    fake = FakeMercadoPagoOrdersProvider(webhook_secret="segredo-webhook-teste")
    pagamento_id = str(uuid4())

    # 1. Criação idempotente de QR Dinâmico
    ordem = fake.criar_cobranca(
        pagamento_id=pagamento_id,
        total_centavos=30000,
        moeda="BRL",
        descricao="OS Oficina - Revisão de Freios",
        idempotency_key=f"create:{pagamento_id}",
    )
    assert ordem.status == StatusPagamentoProvedor.PENDENTE
    assert ordem.qr_data is not None

    # 2. Simulação de pagamento e validação de webhook assinado
    headers, body = fake.simular_pagamento_aprovado(ordem.provider_order_id)
    assinatura_ok = validar_assinatura_webhook_mp(
        x_signature=headers["x-signature"],
        x_request_id=headers["x-request-id"],
        data_id=body["data"]["id"],
        webhook_secret="segredo-webhook-teste",
    )
    assert assinatura_ok is True

    # 3. Consulta ativa no provedor e validação de integridade da cobrança
    consultada = fake.consultar(ordem.provider_order_id)
    validar_confirmacao_cobranca(
        consultada,
        pagamento_id_esperado=pagamento_id,
        total_centavos_esperado=30000,
    )
    assert consultada.status == StatusPagamentoProvedor.CONFIRMADO

    # 4. Estorno integral (compensação pós-pagamento)
    estornada = fake.estornar(
        ordem.provider_order_id, idempotency_key=f"refund:{pagamento_id}"
    )
    assert estornada.status == StatusPagamentoProvedor.ESTORNADO
    print("[OK] Spike local (FakeMercadoPagoOrdersProvider) validado com sucesso.")


def executar_spike_sandbox_se_configurado() -> None:
    token = os.getenv("MP_ACCESS_TOKEN")
    pos_id = os.getenv("MP_EXTERNAL_POS_ID")
    if not token or not pos_id:
        print(
            "[PENDENTE] Variáveis MP_ACCESS_TOKEN / MP_EXTERNAL_POS_ID não definidas. "
            "Aceite contra o Sandbox real permanece pendente para a Etapa P5."
        )
        return

    client = MercadoPagoOrdersClient(access_token=token, external_pos_id=pos_id)
    pagamento_id = str(uuid4())
    ordem = client.criar_cobranca(
        pagamento_id=pagamento_id,
        total_centavos=1500,
        moeda="BRL",
        descricao="Teste Spike Fase 4 QR Dinamico",
        idempotency_key=f"sandbox-create:{pagamento_id}",
    )
    print(f"[OK] Order criada no Sandbox: {ordem.provider_order_id}")
    cancelada = client.cancelar(
        ordem.provider_order_id, idempotency_key=f"sandbox-cancel:{pagamento_id}"
    )
    print(f"[OK] Order cancelada no Sandbox: status={cancelada.raw_status}")


if __name__ == "__main__":
    executar_spike_local()
    executar_spike_sandbox_se_configurado()
