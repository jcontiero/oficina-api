from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import hashlib
import hmac
from typing import Any, Protocol

import httpx


class StatusPagamentoProvedor(str, Enum):
    PENDENTE = "PENDENTE"
    CONFIRMADO = "CONFIRMADO"
    RECUSADO = "RECUSADO"
    CANCELADO = "CANCELADO"
    ESTORNADO = "ESTORNADO"


class ErroComunicacaoProvedorError(Exception):
    """Erro transitório de rede, timeout, 429 ou 5xx no provedor de pagamento."""


class ErroOperacaoProvedorError(Exception):
    """Erro definitivo retornado pelo provedor (4xx de negócio/estado inválido)."""


class ErroDivergenciaConfirmacaoError(Exception):
    """Divergência entre os dados da order consultada e a cobrança local esperada."""


@dataclass(frozen=True)
class ResultadoOrdemProvedor:
    provider_order_id: str
    external_reference: str
    status: StatusPagamentoProvedor
    total_centavos: int
    moeda: str
    qr_data: str | None
    raw_status: str


class ProvedorPagamento(Protocol):
    def criar_cobranca(
        self,
        *,
        pagamento_id: str,
        total_centavos: int,
        moeda: str,
        descricao: str,
        idempotency_key: str,
    ) -> ResultadoOrdemProvedor: ...

    def consultar(self, provider_order_id: str) -> ResultadoOrdemProvedor: ...

    def cancelar(
        self, provider_order_id: str, *, idempotency_key: str
    ) -> ResultadoOrdemProvedor: ...

    def estornar(
        self, provider_order_id: str, *, idempotency_key: str
    ) -> ResultadoOrdemProvedor: ...


def centavos_para_decimal_str(total_centavos: int) -> str:
    if total_centavos <= 0:
        raise ValueError("total_centavos deve ser maior que zero")
    valor = (Decimal(total_centavos) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return f"{valor:.2f}"


def decimal_str_para_centavos(valor_str: str | int | Decimal) -> int:
    valor = Decimal(str(valor_str)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(valor * 100)


def mapear_status_order_mp(raw_status: str) -> StatusPagamentoProvedor:
    normalizado = raw_status.strip().lower()
    mapeamento = {
        "created": StatusPagamentoProvedor.PENDENTE,
        "action_required": StatusPagamentoProvedor.PENDENTE,
        "processing": StatusPagamentoProvedor.PENDENTE,
        "processed": StatusPagamentoProvedor.CONFIRMADO,
        "failed": StatusPagamentoProvedor.RECUSADO,
        "canceled": StatusPagamentoProvedor.CANCELADO,
        "cancelled": StatusPagamentoProvedor.CANCELADO,
        "refunded": StatusPagamentoProvedor.ESTORNADO,
    }
    if normalizado not in mapeamento:
        raise ValueError(f"Status desconhecido na Orders API: {raw_status}")
    return mapeamento[normalizado]


def gerar_assinatura_webhook_mp(
    *, data_id: str, x_request_id: str, ts: str, webhook_secret: str
) -> str:
    manifesto = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    digest = hmac.new(
        webhook_secret.encode("utf-8"),
        manifesto.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"ts={ts},v1={digest}"


def validar_assinatura_webhook_mp(
    *,
    x_signature: str,
    x_request_id: str,
    data_id: str,
    webhook_secret: str,
) -> bool:
    if not x_signature or not x_request_id or not data_id or not webhook_secret:
        return False

    partes: dict[str, str] = {}
    for item in x_signature.split(","):
        if "=" in item:
            chave, valor = item.split("=", 1)
            partes[chave.strip()] = valor.strip()

    ts = partes.get("ts")
    v1 = partes.get("v1")
    if not ts or not v1:
        return False

    esperada = gerar_assinatura_webhook_mp(
        data_id=data_id,
        x_request_id=x_request_id,
        ts=ts,
        webhook_secret=webhook_secret,
    )
    v1_esperada = esperada.split("v1=", 1)[1]
    return hmac.compare_digest(v1, v1_esperada)


def validar_confirmacao_cobranca(
    ordem: ResultadoOrdemProvedor,
    *,
    pagamento_id_esperado: str,
    total_centavos_esperado: int,
    moeda_esperada: str = "BRL",
) -> None:
    if ordem.external_reference != pagamento_id_esperado:
        raise ErroDivergenciaConfirmacaoError(
            f"external_reference divergente: esperado={pagamento_id_esperado}, "
            f"recebido={ordem.external_reference}"
        )
    if ordem.moeda != moeda_esperada:
        raise ErroDivergenciaConfirmacaoError(
            f"Moeda divergente: esperada={moeda_esperada}, recebida={ordem.moeda}"
        )
    if ordem.total_centavos != total_centavos_esperado:
        raise ErroDivergenciaConfirmacaoError(
            f"Valor divergente: esperado={total_centavos_esperado}, "
            f"recebido={ordem.total_centavos}"
        )


class MercadoPagoOrdersClient:
    """
    Adaptador HTTP real para a Orders API (/v1/orders) do Mercado Pago com QR Dinâmico.
    Endpoints oficiais validados no ADR-018:
    - Criar order QR dinâmico: POST /v1/orders
    - Consultar order:         GET  /v1/orders/{order_id}
    - Cancelar order pendente: POST /v1/orders/{order_id}/cancel
    - Reembolsar order paga:   POST /v1/orders/{order_id}/refund
    """

    def __init__(
        self,
        *,
        access_token: str,
        external_pos_id: str,
        base_url: str = "https://api.mercadopago.com",
        timeout_seconds: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.access_token = access_token
        self.external_pos_id = external_pos_id
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = http_client

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        idempotency_key: str | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._headers(idempotency_key)
        try:
            if self._client is not None:
                resp = self._client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    timeout=self.timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.request(method, url, headers=headers, json=json_body)
        except httpx.HTTPError as exc:
            raise ErroComunicacaoProvedorError(
                f"Falha de rede ao chamar Mercado Pago ({method} {path}): {exc}"
            ) from exc

        if resp.status_code == 429 or resp.status_code >= 500:
            raise ErroComunicacaoProvedorError(
                f"Erro transitório HTTP {resp.status_code} em {method} {path}"
            )
        if resp.status_code >= 400:
            raise ErroOperacaoProvedorError(
                f"Erro definitivo HTTP {resp.status_code} em {method} {path}: {resp.text}"
            )
        return resp.json()

    def _parse_order(self, data: dict[str, Any]) -> ResultadoOrdemProvedor:
        raw_status = str(data.get("status", "created"))
        total_amount = data.get("total_amount", "0.00")
        type_response = data.get("type_response") or {}
        qr_data = type_response.get("qr_data") or data.get("qr_data")
        return ResultadoOrdemProvedor(
            provider_order_id=str(data["id"]),
            external_reference=str(data.get("external_reference", "")),
            status=mapear_status_order_mp(raw_status),
            total_centavos=decimal_str_para_centavos(total_amount),
            moeda=str(data.get("currency", "BRL")),
            qr_data=str(qr_data) if qr_data else None,
            raw_status=raw_status,
        )

    def criar_cobranca(
        self,
        *,
        pagamento_id: str,
        total_centavos: int,
        moeda: str,
        descricao: str,
        idempotency_key: str,
    ) -> ResultadoOrdemProvedor:
        amount_str = centavos_para_decimal_str(total_centavos)
        payload = {
            "type": "qr",
            "external_reference": pagamento_id,
            "total_amount": amount_str,
            "description": descricao,
            "config": {
                "qr": {
                    "pos_id": self.external_pos_id,
                    "mode": "dynamic",
                }
            },
            "transactions": {
                "payments": [
                    {
                        "amount": amount_str,
                    }
                ]
            },
        }
        data = self._request(
            "POST",
            "/v1/orders",
            idempotency_key=idempotency_key,
            json_body=payload,
        )
        return self._parse_order(data)

    def consultar(self, provider_order_id: str) -> ResultadoOrdemProvedor:
        data = self._request("GET", f"/v1/orders/{provider_order_id}")
        return self._parse_order(data)

    def cancelar(
        self, provider_order_id: str, *, idempotency_key: str
    ) -> ResultadoOrdemProvedor:
        data = self._request(
            "POST",
            f"/v1/orders/{provider_order_id}/cancel",
            idempotency_key=idempotency_key,
            json_body={},
        )
        return self._parse_order(data)

    def estornar(
        self, provider_order_id: str, *, idempotency_key: str
    ) -> ResultadoOrdemProvedor:
        data = self._request(
            "POST",
            f"/v1/orders/{provider_order_id}/refund",
            idempotency_key=idempotency_key,
            json_body={},
        )
        return self._parse_order(data)


class FakeMercadoPagoOrdersProvider:
    """
    Fake determinístico da Orders API (QR Dinâmico) para testes automatizados e CI/BDD.
    Implementa idempotência por X-Idempotency-Key, validação de estados para cancel/refund
    e geração de notificação webhook assinada (x-signature HMAC-SHA256).
    """

    def __init__(self, webhook_secret: str = "test-mp-webhook-secret") -> None:
        self.webhook_secret = webhook_secret
        self._orders: dict[str, ResultadoOrdemProvedor] = {}
        self._idempotency_cache: dict[str, ResultadoOrdemProvedor] = {}
        self._seq = 0

    def criar_cobranca(
        self,
        *,
        pagamento_id: str,
        total_centavos: int,
        moeda: str,
        descricao: str,
        idempotency_key: str,
    ) -> ResultadoOrdemProvedor:
        if idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[idempotency_key]

        self._seq += 1
        order_id = f"ORD_TEST_{self._seq:06d}"
        qr_data = (
            f"00020101021243650016COM.MERCADOLIBRE020130636{order_id}"
            f"5204000053039865406{centavos_para_decimal_str(total_centavos)}"
        )
        ordem = ResultadoOrdemProvedor(
            provider_order_id=order_id,
            external_reference=pagamento_id,
            status=StatusPagamentoProvedor.PENDENTE,
            total_centavos=total_centavos,
            moeda=moeda,
            qr_data=qr_data,
            raw_status="created",
        )
        self._orders[order_id] = ordem
        self._idempotency_cache[idempotency_key] = ordem
        return ordem

    def consultar(self, provider_order_id: str) -> ResultadoOrdemProvedor:
        if provider_order_id not in self._orders:
            raise ErroOperacaoProvedorError(f"Order {provider_order_id} não encontrada")
        return self._orders[provider_order_id]

    def simular_pagamento_aprovado(
        self,
        provider_order_id: str,
        *,
        x_request_id: str = "req-webhook-001",
        ts: str = "1763305200",
    ) -> tuple[dict[str, str], dict[str, Any]]:
        atual = self.consultar(provider_order_id)
        if atual.status == StatusPagamentoProvedor.CANCELADO:
            raise ErroOperacaoProvedorError("Não é possível aprovar order já cancelada")
        atualizada = ResultadoOrdemProvedor(
            provider_order_id=atual.provider_order_id,
            external_reference=atual.external_reference,
            status=StatusPagamentoProvedor.CONFIRMADO,
            total_centavos=atual.total_centavos,
            moeda=atual.moeda,
            qr_data=atual.qr_data,
            raw_status="processed",
        )
        self._orders[provider_order_id] = atualizada
        assinatura = gerar_assinatura_webhook_mp(
            data_id=provider_order_id,
            x_request_id=x_request_id,
            ts=ts,
            webhook_secret=self.webhook_secret,
        )
        headers = {
            "x-signature": assinatura,
            "x-request-id": x_request_id,
        }
        body = {
            "action": "order.processed",
            "type": "order",
            "data": {"id": provider_order_id},
        }
        return headers, body

    def cancelar(
        self, provider_order_id: str, *, idempotency_key: str
    ) -> ResultadoOrdemProvedor:
        if idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[idempotency_key]

        atual = self.consultar(provider_order_id)
        if atual.status == StatusPagamentoProvedor.CONFIRMADO:
            raise ErroOperacaoProvedorError(
                "Order já processada (processed) não pode ser cancelada; utilize estornar (/refund)"
            )
        cancelada = ResultadoOrdemProvedor(
            provider_order_id=atual.provider_order_id,
            external_reference=atual.external_reference,
            status=StatusPagamentoProvedor.CANCELADO,
            total_centavos=atual.total_centavos,
            moeda=atual.moeda,
            qr_data=atual.qr_data,
            raw_status="canceled",
        )
        self._orders[provider_order_id] = cancelada
        self._idempotency_cache[idempotency_key] = cancelada
        return cancelada

    def estornar(
        self, provider_order_id: str, *, idempotency_key: str
    ) -> ResultadoOrdemProvedor:
        if idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[idempotency_key]

        atual = self.consultar(provider_order_id)
        if atual.status != StatusPagamentoProvedor.CONFIRMADO:
            raise ErroOperacaoProvedorError(
                f"Reembolso (/refund) exige order paga (processed), estado atual={atual.raw_status}"
            )
        estornada = ResultadoOrdemProvedor(
            provider_order_id=atual.provider_order_id,
            external_reference=atual.external_reference,
            status=StatusPagamentoProvedor.ESTORNADO,
            total_centavos=atual.total_centavos,
            moeda=atual.moeda,
            qr_data=atual.qr_data,
            raw_status="refunded",
        )
        self._orders[provider_order_id] = estornada
        self._idempotency_cache[idempotency_key] = estornada
        return estornada
