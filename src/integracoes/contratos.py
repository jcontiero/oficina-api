from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.saga.dominio.estados import exige_barreira_execucao

PRODUTORES_PERMITIDOS = {"oficina-os", "oficina-billing", "oficina-execucao"}

COMANDOS_SAGA_V1: dict[str, set[str]] = {
    "SolicitarDiagnostico.v1": {
        "rodada",
        "cliente_id",
        "veiculo_id",
        "descricao_problema",
    },
    "GerarOrcamento.v1": {
        "rodada",
        "versao",
        "cliente_id",
        "itens_servico",
        "itens_peca",
    },
    "ReservarPecas.v1": {
        "rodada",
        "reserva_id",
        "orcamento_id",
        "orcamento_versao",
        "itens_peca",
    },
    "CriarCobranca.v1": {
        "rodada",
        "orcamento_id",
        "orcamento_versao",
        "cliente_id",
        "total_centavos",
        "moeda",
    },
    "EnfileirarExecucao.v1": {
        "rodada",
        "reserva_id",
        "orcamento_id",
        "pagamento_id",
        "itens_servico",
        "itens_peca",
    },
    "CancelarExecucao.v1": {"rodada", "motivo", "compensacao_id"},
    "LiberarReserva.v1": {
        "rodada",
        "motivo",
        "compensacao_id",
        "reserva_id",
        "execucao_cancelada_event_id",
    },
    "CancelarOrcamento.v1": {
        "rodada",
        "motivo",
        "compensacao_id",
        "orcamento_id",
        "orcamento_versao",
        "execucao_cancelada_event_id",
    },
    "CancelarCobranca.v1": {
        "rodada",
        "motivo",
        "compensacao_id",
        "execucao_cancelada_event_id",
    },
    "EstornarPagamento.v1": {
        "rodada",
        "motivo",
        "compensacao_id",
        "pagamento_id",
        "total_centavos",
        "moeda",
        "execucao_cancelada_event_id",
    },
}

EVENTOS_SAGA_V1: dict[str, set[str]] = {
    "DiagnosticoConcluido.v1": {
        "rodada",
        "diagnostico_id",
        "laudo",
        "itens_servico",
        "itens_peca",
    },
    "OrcamentoGerado.v1": {
        "rodada",
        "orcamento_id",
        "versao",
        "total_centavos",
        "moeda",
    },
    "OrcamentoAprovado.v1": {
        "rodada",
        "orcamento_id",
        "versao",
        "cliente_id",
        "total_centavos",
        "moeda",
    },
    "OrcamentoRecusado.v1": {
        "rodada",
        "orcamento_id",
        "versao",
        "cliente_id",
        "motivo",
    },
    "PecasReservadas.v1": {"rodada", "reserva_id", "status"},
    "ReservaRecusada.v1": {
        "rodada",
        "reserva_id",
        "motivo",
        "pecas_indisponiveis",
    },
    "CobrancaCriada.v1": {
        "rodada",
        "orcamento_id",
        "pagamento_id",
        "provider_order_id",
        "qr_data",
        "total_centavos",
        "moeda",
    },
    "PagamentoConfirmado.v1": {
        "orcamento_id",
        "pagamento_id",
        "provider_order_id",
        "total_centavos",
        "moeda",
        "orcamento_versao",
    },
    "PagamentoRecusado.v1": {
        "rodada",
        "orcamento_id",
        "pagamento_id",
        "motivo",
    },
    "ExecucaoEnfileirada.v1": {
        "rodada",
        "execucao_id",
        "reserva_id",
        "status",
    },
    "ExecucaoRejeitada.v1": {"rodada", "reserva_id", "motivo"},
    "ExecucaoIniciada.v1": {"rodada", "execucao_id", "reserva_consumida"},
    "ExecucaoConcluida.v1": {"rodada", "execucao_id", "concluida_em"},
    "ExecucaoCancelada.v1": {
        "rodada",
        "compensacao_id",
        "resultado",
        "motivo",
        "tombstone_persistido",
    },
    "ExecucaoCancelamentoRecusado.v1": {
        "rodada",
        "compensacao_id",
        "resultado",
        "motivo",
        "execucao_id",
    },
    "ReservaLiberada.v1": {
        "rodada",
        "compensacao_id",
        "reserva_id",
        "resultado",
        "motivo",
    },
    "ReservaLiberacaoRecusada.v1": {
        "rodada",
        "compensacao_id",
        "reserva_id",
        "resultado",
        "motivo",
    },
    "OrcamentoCancelado.v1": {
        "rodada",
        "compensacao_id",
        "orcamento_id",
        "resultado",
        "motivo",
    },
    "CobrancaCancelada.v1": {
        "rodada",
        "compensacao_id",
        "resultado",
        "motivo",
    },
    "PagamentoEstornado.v1": {
        "rodada",
        "compensacao_id",
        "pagamento_id",
        "provider_order_id",
        "total_centavos",
        "moeda",
        "resultado",
        "motivo",
    },
    "PagamentoEstornoPendente.v1": {
        "rodada",
        "compensacao_id",
        "pagamento_id",
        "resultado",
        "motivo",
    },
    "PagamentoEstornoFalhou.v1": {
        "rodada",
        "compensacao_id",
        "pagamento_id",
        "resultado",
        "motivo",
    },
}

CAMPOS_SENSIVEIS_PROIBIDOS = {
    "cpf",
    "senha",
    "password",
    "secret",
    "access_token",
    "token",
}


class EnvelopeMensagemV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_type: str
    schema_version: int = Field(default=1)
    occurred_at: datetime
    producer: str
    saga_id: UUID
    os_id: UUID
    correlation_id: UUID
    causation_id: UUID
    aggregate_version: int = Field(ge=1)
    payload: dict[str, Any]

    @field_validator("schema_version")
    @classmethod
    def _validar_versao(cls, valor: int) -> int:
        if valor != 1:
            raise ValueError("schema_version deve ser 1")
        return valor

    @field_validator("producer")
    @classmethod
    def _validar_produtor(cls, valor: str) -> str:
        if valor not in PRODUTORES_PERMITIDOS:
            raise ValueError(f"Produtor não permitido: {valor}")
        return valor


def validar_envelope_v1(dados: dict[str, Any]) -> EnvelopeMensagemV1:
    """
    Valida o envelope canônico v1, os campos obrigatórios do comando/evento,
    a regra de barreira de compensação e a ausência de campos sensíveis.
    """
    envelope = EnvelopeMensagemV1.model_validate(dados)
    event_type = envelope.event_type

    todos_contratos = {**COMANDOS_SAGA_V1, **EVENTOS_SAGA_V1}
    if event_type not in todos_contratos:
        raise ValueError(f"Tipo de evento/comando desconhecido: {event_type}")

    if event_type in COMANDOS_SAGA_V1 and envelope.producer != "oficina-os":
        raise ValueError(
            f"Comandos da Saga ({event_type}) só podem ser produzidos por oficina-os"
        )

    chaves_obrigatorias = todos_contratos[event_type]
    faltantes = chaves_obrigatorias - set(envelope.payload.keys())
    if faltantes:
        raise ValueError(
            f"Payload de {event_type} sem campos obrigatórios: {sorted(faltantes)}"
        )

    if exige_barreira_execucao(event_type):
        barreira_id = envelope.payload.get("execucao_cancelada_event_id")
        if not barreira_id:
            raise ValueError(
                f"Comando {event_type} exige execucao_cancelada_event_id comprovando a barreira"
            )
        UUID(str(barreira_id))

    chaves_proibidas = set(envelope.payload.keys()) & CAMPOS_SENSIVEIS_PROIBIDOS
    if chaves_proibidas:
        raise ValueError(
            f"Payload contém campos sensíveis proibidos na mensageria: {sorted(chaves_proibidas)}"
        )

    return envelope
