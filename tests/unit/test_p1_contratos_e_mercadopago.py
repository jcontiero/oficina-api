import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from spikes.mercadopago_qr import (
    ErroComunicacaoProvedorError,
    ErroDivergenciaConfirmacaoError,
    ErroOperacaoProvedorError,
    FakeMercadoPagoOrdersProvider,
    MercadoPagoOrdersClient,
    StatusPagamentoProvedor,
    centavos_para_decimal_str,
    decimal_str_para_centavos,
    gerar_assinatura_webhook_mp,
    mapear_status_order_mp,
    validar_assinatura_webhook_mp,
    validar_confirmacao_cobranca,
)
from src.atendimento.dominio.value_objects import (
    PRIORIDADE_LISTAGEM_FASE2,
    TRANSICOES_VALIDAS,
    StatusOS,
    StatusOSFase2,
    para_status_fase2,
    para_status_interno,
)
from src.integracoes.contratos import (
    COMANDOS_SAGA_V1,
    EVENTOS_SAGA_V1,
    validar_envelope_v1,
)
from src.saga.dominio.estados import (
    CompensacaoFinanceiraStatus,
    EstadoSaga,
    MotivoCompensacao,
    SubestadoCompensacao,
    TRANSICOES_SAGA_VALIDAS,
    exige_barreira_execucao,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
CONTRATOS_DIR = ROOT_DIR / "docs" / "contratos"


class TestEstadosFase4EContratosSaga:
    def test_novos_status_os_e_prioridade_listagem(self):
        assert (
            para_status_fase2(StatusOS.AGUARDANDO_PAGAMENTO)
            == StatusOSFase2.AGUARDANDO_PAGAMENTO
        )
        assert (
            para_status_fase2(StatusOS.AGUARDANDO_EXECUCAO)
            == StatusOSFase2.AGUARDANDO_EXECUCAO
        )
        assert (
            para_status_fase2(StatusOS.COMPENSACAO_PENDENTE)
            == StatusOSFase2.COMPENSACAO_PENDENTE
        )
        assert (
            para_status_interno("Aguardando Pagamento") == StatusOS.AGUARDANDO_PAGAMENTO
        )
        assert (
            para_status_interno("Aguardando Execução") == StatusOS.AGUARDANDO_EXECUCAO
        )
        assert (
            para_status_interno("Compensação Pendente") == StatusOS.COMPENSACAO_PENDENTE
        )

        # Ordem de prioridade: EXECUCAO < AGUARDANDO_EXECUCAO < AGUARDANDO_PAGAMENTO < AGUARDANDO_APROVACAO < DIAGNOSTICO < RECEBIDA
        assert (
            PRIORIDADE_LISTAGEM_FASE2[StatusOSFase2.EXECUCAO]
            < PRIORIDADE_LISTAGEM_FASE2[StatusOSFase2.AGUARDANDO_EXECUCAO]
            < PRIORIDADE_LISTAGEM_FASE2[StatusOSFase2.AGUARDANDO_PAGAMENTO]
            < PRIORIDADE_LISTAGEM_FASE2[StatusOSFase2.AGUARDANDO_APROVACAO]
            < PRIORIDADE_LISTAGEM_FASE2[StatusOSFase2.DIAGNOSTICO]
            < PRIORIDADE_LISTAGEM_FASE2[StatusOSFase2.RECEBIDA]
        )

        # Todos os StatusOS possuem transições mapeadas
        for status in StatusOS:
            assert status in TRANSICOES_VALIDAS

    def test_maquina_estados_saga_e_barreira_obrigatoria(self):
        for estado in EstadoSaga:
            assert estado in TRANSICOES_SAGA_VALIDAS

        assert (
            EstadoSaga.COMPENSANDO_EFEITOS
            in TRANSICOES_SAGA_VALIDAS[EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO]
        )
        assert (
            EstadoSaga.INTERVENCAO_MANUAL
            in TRANSICOES_SAGA_VALIDAS[EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO]
        )
        assert (
            EstadoSaga.COMPENSADA
            not in TRANSICOES_SAGA_VALIDAS[EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO]
        )

        assert exige_barreira_execucao("CancelarExecucao.v1") is False
        assert exige_barreira_execucao("LiberarReserva.v1") is True
        assert exige_barreira_execucao("CancelarOrcamento.v1") is True
        assert exige_barreira_execucao("CancelarCobranca.v1") is True
        assert exige_barreira_execucao("EstornarPagamento.v1") is True

        assert SubestadoCompensacao.AGUARDANDO_BARREIRA_EXECUCAO.value
        assert CompensacaoFinanceiraStatus.PENDENTE.value
        assert MotivoCompensacao.FALHA_ENFILEIRAMENTO.value

    def test_schemas_json_e_fixtures_fluxo_feliz_e_compensacao_validos(self):
        envelope_schema = json.loads(
            (CONTRATOS_DIR / "schemas" / "envelope-v1.schema.json").read_text()
        )
        comandos_schema = json.loads(
            (CONTRATOS_DIR / "schemas" / "comandos-saga-v1.schema.json").read_text()
        )
        eventos_schema = json.loads(
            (CONTRATOS_DIR / "schemas" / "eventos-saga-v1.schema.json").read_text()
        )
        openapi_spec = json.loads(
            (CONTRATOS_DIR / "openapi-fase4-contratos-v1.json").read_text()
        )
        fixtures = json.loads(
            (
                CONTRATOS_DIR / "fixtures" / "fluxo-feliz-e-compensacao-v1.json"
            ).read_text()
        )

        assert envelope_schema["properties"]["schema_version"]["const"] == 1
        for cmd in COMANDOS_SAGA_V1:
            assert cmd in comandos_schema["$defs"]
        for evt in EVENTOS_SAGA_V1:
            assert evt in eventos_schema["$defs"]
        assert "/v1/ordens-servico" in openapi_spec["paths"]
        assert "/webhooks/mercadopago" in openapi_spec["paths"]
        assert "/internal/clientes/autenticacao" in openapi_spec["paths"]

        for msg in fixtures["fluxo_feliz"]:
            validado = validar_envelope_v1(msg)
            assert validado.schema_version == 1

        for msg in fixtures["compensacao_falha_fila_apos_pagamento"]:
            validado = validar_envelope_v1(msg)
            assert validado.schema_version == 1

    def test_rejeita_contratos_invalidos_e_compensacao_sem_barreira(self):
        fixtures = json.loads(
            (
                CONTRATOS_DIR / "fixtures" / "fluxo-feliz-e-compensacao-v1.json"
            ).read_text()
        )
        estorno_msg = dict(fixtures["compensacao_falha_fila_apos_pagamento"][5])
        estorno_payload = dict(estorno_msg["payload"])
        del estorno_payload["execucao_cancelada_event_id"]
        estorno_msg["payload"] = estorno_payload

        with pytest.raises(ValueError, match="sem campos obrigatórios"):
            validar_envelope_v1(estorno_msg)

        estorno_msg["payload"] = {
            **fixtures["compensacao_falha_fila_apos_pagamento"][5]["payload"],
            "execucao_cancelada_event_id": "",
        }
        with pytest.raises(ValueError, match="exige execucao_cancelada_event_id"):
            validar_envelope_v1(estorno_msg)

        # Produtor inválido tentando emitir comando da Saga
        cmd_invalido = {
            **fixtures["fluxo_feliz"][0],
            "producer": "oficina-billing",
        }
        with pytest.raises(ValueError, match="só podem ser produzidos por oficina-os"):
            validar_envelope_v1(cmd_invalido)

        # Campo sensível proibido (cpf) no payload
        msg_Com_cpf = {
            **fixtures["fluxo_feliz"][0],
            "payload": {
                **fixtures["fluxo_feliz"][0]["payload"],
                "cpf": "12345678901",
            },
        }
        with pytest.raises(ValueError, match="campos sensíveis proibidos"):
            validar_envelope_v1(msg_Com_cpf)


class TestSpikeMercadoPagoOrdersQR:
    def test_conversao_centavos_decimal_sem_float(self):
        assert centavos_para_decimal_str(15000) == "150.00"
        assert centavos_para_decimal_str(199) == "1.99"
        assert decimal_str_para_centavos("150.00") == 15000
        assert decimal_str_para_centavos("1.99") == 199
        with pytest.raises(ValueError, match="maior que zero"):
            centavos_para_decimal_str(0)

    def test_mapeamento_status_orders_api(self):
        assert mapear_status_order_mp("created") == StatusPagamentoProvedor.PENDENTE
        assert (
            mapear_status_order_mp("action_required")
            == StatusPagamentoProvedor.PENDENTE
        )
        assert mapear_status_order_mp("processed") == StatusPagamentoProvedor.CONFIRMADO
        assert mapear_status_order_mp("failed") == StatusPagamentoProvedor.RECUSADO
        assert mapear_status_order_mp("canceled") == StatusPagamentoProvedor.CANCELADO
        assert mapear_status_order_mp("refunded") == StatusPagamentoProvedor.ESTORNADO
        with pytest.raises(ValueError, match="Status desconhecido"):
            mapear_status_order_mp("desconhecido")

    def test_validacao_assinatura_webhook_x_signature(self):
        segredo = "mp-webhook-secret-2026"
        assinatura = gerar_assinatura_webhook_mp(
            data_id="ORD001",
            x_request_id="req-123",
            ts="1763305200",
            webhook_secret=segredo,
        )
        assert (
            validar_assinatura_webhook_mp(
                x_signature=assinatura,
                x_request_id="req-123",
                data_id="ORD001",
                webhook_secret=segredo,
            )
            is True
        )
        # Assinatura adulterada deve ser rejeitada
        assert (
            validar_assinatura_webhook_mp(
                x_signature=f"{assinatura}00",
                x_request_id="req-123",
                data_id="ORD001",
                webhook_secret=segredo,
            )
            is False
        )
        assert (
            validar_assinatura_webhook_mp(
                x_signature="formato-invalido",
                x_request_id="req-123",
                data_id="ORD001",
                webhook_secret=segredo,
            )
            is False
        )
        assert (
            validar_assinatura_webhook_mp(
                x_signature="",
                x_request_id="req-123",
                data_id="ORD001",
                webhook_secret=segredo,
            )
            is False
        )

    def test_fake_provider_ciclo_completo_idempotencia_e_compensacao(self):
        fake = FakeMercadoPagoOrdersProvider(webhook_secret="segredo")
        pag_id = str(uuid4())

        # Criação idempotente
        o1 = fake.criar_cobranca(
            pagamento_id=pag_id,
            total_centavos=25000,
            moeda="BRL",
            descricao="OS #1",
            idempotency_key="key-create-1",
        )
        o2 = fake.criar_cobranca(
            pagamento_id=pag_id,
            total_centavos=25000,
            moeda="BRL",
            descricao="OS #1",
            idempotency_key="key-create-1",
        )
        assert o1.provider_order_id == o2.provider_order_id
        assert o1.status == StatusPagamentoProvedor.PENDENTE

        # Estorno antes de pagar deve falhar
        with pytest.raises(ErroOperacaoProvedorError, match="exige order paga"):
            fake.estornar(o1.provider_order_id, idempotency_key="key-refund-err")

        # Simula aprovação e webhook assinado
        headers, body = fake.simular_pagamento_aprovado(o1.provider_order_id)
        assert validar_assinatura_webhook_mp(
            x_signature=headers["x-signature"],
            x_request_id=headers["x-request-id"],
            data_id=body["data"]["id"],
            webhook_secret="segredo",
        )

        # Cancelar order já paga deve ser recusado (exige /refund)
        with pytest.raises(ErroOperacaoProvedorError, match="utilize estornar"):
            fake.cancelar(o1.provider_order_id, idempotency_key="key-cancel-err")

        # Confirmação válida vs divergente
        consultada = fake.consultar(o1.provider_order_id)
        validar_confirmacao_cobranca(
            consultada,
            pagamento_id_esperado=pag_id,
            total_centavos_esperado=25000,
        )
        with pytest.raises(ErroDivergenciaConfirmacaoError, match="Valor divergente"):
            validar_confirmacao_cobranca(
                consultada,
                pagamento_id_esperado=pag_id,
                total_centavos_esperado=99999,
            )

        # Estorno idempotente
        est1 = fake.estornar(o1.provider_order_id, idempotency_key="key-refund-1")
        est2 = fake.estornar(o1.provider_order_id, idempotency_key="key-refund-1")
        assert est1.status == StatusPagamentoProvedor.ESTORNADO
        assert est2.status == StatusPagamentoProvedor.ESTORNADO

    def test_cliente_http_orders_api_endpoints_cancel_e_refund(self):
        chamadas: list[tuple[str, str, dict[str, str], bytes]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            chamadas.append(
                (
                    request.method,
                    request.url.path,
                    dict(request.headers),
                    request.content,
                )
            )
            if request.method == "POST" and request.url.path == "/v1/orders":
                return httpx.Response(
                    201,
                    json={
                        "id": "ORD_MP_900",
                        "external_reference": "pag-900",
                        "status": "created",
                        "total_amount": "300.00",
                        "currency": "BRL",
                        "type_response": {"qr_data": "000201QRDATA"},
                    },
                )
            if request.method == "GET" and request.url.path == "/v1/orders/ORD_MP_900":
                return httpx.Response(
                    200,
                    json={
                        "id": "ORD_MP_900",
                        "external_reference": "pag-900",
                        "status": "processed",
                        "total_amount": "300.00",
                        "currency": "BRL",
                        "type_response": {"qr_data": "000201QRDATA"},
                    },
                )
            if (
                request.method == "POST"
                and request.url.path == "/v1/orders/ORD_MP_900/cancel"
            ):
                return httpx.Response(
                    200,
                    json={
                        "id": "ORD_MP_900",
                        "external_reference": "pag-900",
                        "status": "canceled",
                        "total_amount": "300.00",
                        "currency": "BRL",
                    },
                )
            if (
                request.method == "POST"
                and request.url.path == "/v1/orders/ORD_MP_900/refund"
            ):
                return httpx.Response(
                    201,
                    json={
                        "id": "ORD_MP_900",
                        "external_reference": "pag-900",
                        "status": "refunded",
                        "total_amount": "300.00",
                        "currency": "BRL",
                    },
                )
            if request.url.path == "/v1/orders/ERRO_503":
                return httpx.Response(503, text="Service Unavailable")
            return httpx.Response(404, text="Not Found")

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as http_client:
            mp = MercadoPagoOrdersClient(
                access_token="TEST-TOKEN",
                external_pos_id="POS01",
                http_client=http_client,
            )

            criada = mp.criar_cobranca(
                pagamento_id="pag-900",
                total_centavos=30000,
                moeda="BRL",
                descricao="OS #900",
                idempotency_key="idem-create-900",
            )
            assert criada.provider_order_id == "ORD_MP_900"
            assert criada.qr_data == "000201QRDATA"
            assert criada.status == StatusPagamentoProvedor.PENDENTE

            consultada = mp.consultar("ORD_MP_900")
            assert consultada.status == StatusPagamentoProvedor.CONFIRMADO

            cancelada = mp.cancelar("ORD_MP_900", idempotency_key="idem-cancel-900")
            assert cancelada.status == StatusPagamentoProvedor.CANCELADO

            estornada = mp.estornar("ORD_MP_900", idempotency_key="idem-refund-900")
            assert estornada.status == StatusPagamentoProvedor.ESTORNADO

            with pytest.raises(ErroComunicacaoProvedorError, match="HTTP 503"):
                mp.consultar("ERRO_503")

            with pytest.raises(ErroOperacaoProvedorError, match="HTTP 404"):
                mp.consultar("INEXISTENTE")

        # Comprova os paths exatos (/cancel e /refund no singular) e o header X-Idempotency-Key
        assert chamadas[0][1] == "/v1/orders"
        assert chamadas[0][2]["x-idempotency-key"] == "idem-create-900"
        assert chamadas[2][1] == "/v1/orders/ORD_MP_900/cancel"
        assert chamadas[2][2]["x-idempotency-key"] == "idem-cancel-900"
        assert chamadas[3][1] == "/v1/orders/ORD_MP_900/refund"
        assert chamadas[3][2]["x-idempotency-key"] == "idem-refund-900"
