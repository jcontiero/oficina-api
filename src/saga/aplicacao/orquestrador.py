from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.atendimento.dominio.value_objects import StatusOS
from src.atendimento.infraestrutura.modelos import HistoricoOSModel, OrdemDeServicoModel
from src.integracoes.contratos import validar_envelope_v1
from src.saga.dominio.estados import (
    EstadoSaga,
    MotivoCompensacao,
    SubestadoCompensacao,
    TRANSICOES_SAGA_VALIDAS,
)
from src.saga.infraestrutura.modelos import (
    EventoAdiantadoModel,
    SagaInstanceModel,
    SagaStepModel,
)
from src.shared.outbox import InboxEventoModel, OutboxEventoModel

logger = logging.getLogger("saga-orquestrador")

DEADLINE_POR_ESTADO_SEGUNDOS: dict[EstadoSaga, int] = {
    EstadoSaga.DIAGNOSTICO: 120,
    EstadoSaga.GERANDO_ORCAMENTO: 120,
    EstadoSaga.AGUARDANDO_APROVACAO: 86400,
    EstadoSaga.RESERVANDO_PECAS: 120,
    EstadoSaga.CRIANDO_COBRANCA: 120,
    EstadoSaga.AGUARDANDO_PAGAMENTO: 3600,
    EstadoSaga.ENFILEIRANDO: 120,
}

CMD_RESERVAR_PECAS = "ReservarPecas.v1"
EVT_RESERVA_RECUSADA = "ReservaRecusada.v1"
CMD_ENFILEIRAR_EXECUCAO = "EnfileirarExecucao.v1"
EVT_EXECUCAO_REJEITADA = "ExecucaoRejeitada.v1"
CMD_CANCELAR_EXECUCAO = "CancelarExecucao.v1"
CMD_LIBERAR_RESERVA = "LiberarReserva.v1"
EVT_RESERVA_LIBERADA = "ReservaLiberada.v1"
EVT_ORCAMENTO_CANCELADO = "OrcamentoCancelado.v1"
CMD_ESTORNAR_PAGAMENTO = "EstornarPagamento.v1"
EVT_PAGAMENTO_ESTORNADO = "PagamentoEstornado.v1"
MSG_SAGA_NAO_ENCONTRADA = "Saga não encontrada para a OS"

COMANDO_POR_EVENTO_RESPOSTA: dict[str, str] = {
    "DiagnosticoConcluido.v1": "SolicitarDiagnostico.v1",
    "OrcamentoGerado.v1": "GerarOrcamento.v1",
    "PecasReservadas.v1": CMD_RESERVAR_PECAS,
    EVT_RESERVA_RECUSADA: CMD_RESERVAR_PECAS,
    "ExecucaoEnfileirada.v1": CMD_ENFILEIRAR_EXECUCAO,
    EVT_EXECUCAO_REJEITADA: CMD_ENFILEIRAR_EXECUCAO,
    "ExecucaoCancelada.v1": CMD_CANCELAR_EXECUCAO,
    "ExecucaoCancelamentoRecusado.v1": CMD_CANCELAR_EXECUCAO,
    EVT_RESERVA_LIBERADA: CMD_LIBERAR_RESERVA,
    "ReservaLiberacaoRecusada.v1": CMD_LIBERAR_RESERVA,
    EVT_ORCAMENTO_CANCELADO: "CancelarOrcamento.v1",
    EVT_PAGAMENTO_ESTORNADO: CMD_ESTORNAR_PAGAMENTO,
    "PagamentoEstornoFalhou.v1": CMD_ESTORNAR_PAGAMENTO,
}


def _topico_comando(destino: str, env: str = "homolog") -> str:
    if destino == "billing":
        return f"oficina-{env}-billing-comandos-v1"
    if destino == "execucao":
        return f"oficina-{env}-execucao-comandos-v1"
    return f"oficina-{env}-eventos-v1"


class OrquestradorSaga:
    """
    Orquestrador persistente da Saga dentro do OS Service (oficina-api).
    Todas as alterações de estado da OS, da Saga, da Inbox e da Outbox ocorrem na
    mesma transação local SQL.
    """

    def __init__(self, db: Session, *, environment: str = "homolog") -> None:
        self.db = db
        self.environment = environment

    def _montar_envelope(
        self,
        *,
        event_type: str,
        saga_id: UUID,
        os_id: UUID,
        correlation_id: UUID,
        causation_id: UUID,
        aggregate_version: int,
        payload: dict[str, Any],
    ) -> tuple[UUID, dict[str, Any]]:
        event_id = uuid4()
        envelope = {
            "event_id": str(event_id),
            "event_type": event_type,
            "schema_version": 1,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "producer": "oficina-os",
            "saga_id": str(saga_id),
            "os_id": str(os_id),
            "correlation_id": str(correlation_id),
            "causation_id": str(causation_id),
            "aggregate_version": aggregate_version,
            "payload": payload,
        }
        validar_envelope_v1(envelope)
        return event_id, envelope

    def _enfileirar_comando(
        self,
        *,
        saga: SagaInstanceModel,
        destino: str,
        event_type: str,
        causation_id: UUID,
        payload: dict[str, Any],
        traceparent: str | None = None,
    ) -> UUID:
        event_id, envelope = self._montar_envelope(
            event_type=event_type,
            saga_id=UUID(saga.id),
            os_id=UUID(saga.os_id),
            correlation_id=UUID(saga.correlation_id),
            causation_id=causation_id,
            aggregate_version=saga.version,
            payload=payload,
        )
        self.db.add(
            SagaStepModel(
                saga_id=saga.id,
                etapa=saga.estado,
                comando_event_id=str(event_id),
                comando_tipo=event_type,
                status="PENDENTE",
            )
        )
        self.db.add(
            OutboxEventoModel(
                id=str(event_id),
                event_id=str(event_id),
                topic=_topico_comando(destino, self.environment),
                tipo_evento=event_type,
                payload=envelope,
                traceparent=traceparent,
                status="PENDENTE",
            )
        )
        return event_id

    def _transicionar_saga(
        self, saga: SagaInstanceModel, novo_estado: EstadoSaga
    ) -> None:
        estado_atual = EstadoSaga(saga.estado)
        if novo_estado not in TRANSICOES_SAGA_VALIDAS[estado_atual]:
            raise ValueError(
                f"Transição de Saga inválida: {estado_atual.value} -> {novo_estado.value}"
            )
        agora = datetime.now(timezone.utc)
        saga.estado = novo_estado.value
        saga.version += 1
        saga.atualizada_em = agora
        ttl = DEADLINE_POR_ESTADO_SEGUNDOS.get(novo_estado)
        saga.deadline_at = agora + timedelta(seconds=ttl) if ttl is not None else None

    def _registrar_status_os(
        self, os_model: OrdemDeServicoModel, novo_status: StatusOS, origem: str = "SAGA"
    ) -> None:
        if os_model.status == novo_status:
            return
        anterior = os_model.status
        os_model.status = novo_status
        os_model.atualizada_em = datetime.now(timezone.utc)
        seq = len(os_model.historico) + 1
        self.db.add(
            HistoricoOSModel(
                id=uuid4(),
                os_id=os_model.id,
                status_anterior=anterior,
                status_novo=novo_status,
                ocorrido_em=datetime.now(timezone.utc),
                sequencia=seq,
                origem=origem,
            )
        )

    def iniciar_saga_abertura(
        self,
        *,
        os_id: UUID,
        cliente_id: UUID,
        veiculo_id: UUID,
        descricao_problema: str,
        rodada: int = 1,
        traceparent: str | None = None,
    ) -> SagaInstanceModel:
        """
        Cria a instância da Saga na mesma transação da abertura da OS e enfileira
        SolicitarDiagnostico.v1 na Outbox.
        """
        saga_id = uuid4()
        correlation_id = uuid4()
        saga = SagaInstanceModel(
            id=str(saga_id),
            os_id=str(os_id),
            rodada=rodada,
            estado=EstadoSaga.DIAGNOSTICO.value,
            correlation_id=str(correlation_id),
            version=1,
            deadline_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        )
        self.db.add(saga)
        self.db.flush()

        self._enfileirar_comando(
            saga=saga,
            destino="execucao",
            event_type="SolicitarDiagnostico.v1",
            causation_id=saga_id,
            payload={
                "rodada": rodada,
                "cliente_id": str(cliente_id),
                "veiculo_id": str(veiculo_id),
                "descricao_problema": descricao_problema,
                "servicos_iniciais": [],
                "pecas_iniciais": [],
            },
            traceparent=traceparent,
        )
        return saga

    def _aplicar_fluxo_principal(
        self,
        saga: SagaInstanceModel,
        os_model: OrdemDeServicoModel,
        envelope: Any,
        *,
        traceparent: str | None = None,
    ) -> bool:
        evt = envelope.event_type
        payload = envelope.payload
        estado = EstadoSaga(saga.estado)

        if evt == "DiagnosticoConcluido.v1" and estado == EstadoSaga.DIAGNOSTICO:
            self._registrar_status_os(os_model, StatusOS.AGUARDANDO_ORCAMENTO)
            os_model.laudo_diagnostico = str(payload.get("laudo", ""))
            self._transicionar_saga(saga, EstadoSaga.GERANDO_ORCAMENTO)
            self._enfileirar_comando(
                saga=saga,
                destino="billing",
                event_type="GerarOrcamento.v1",
                causation_id=envelope.event_id,
                payload={
                    "rodada": saga.rodada,
                    "versao": saga.rodada,
                    "cliente_id": str(os_model.cliente_id),
                    "laudo_diagnostico": str(payload.get("laudo", "")),
                    "itens_servico": payload["itens_servico"],
                    "itens_peca": payload["itens_peca"],
                },
                traceparent=traceparent,
            )
            return True

        if evt == "OrcamentoGerado.v1" and estado == EstadoSaga.GERANDO_ORCAMENTO:
            saga.orcamento_id = str(payload["orcamento_id"])
            saga.orcamento_versao = int(payload["versao"])
            saga.total_centavos = int(payload["total_centavos"])
            self._registrar_status_os(os_model, StatusOS.AGUARDANDO_APROVACAO)
            self._transicionar_saga(saga, EstadoSaga.AGUARDANDO_APROVACAO)
            return True

        if evt == "OrcamentoAprovado.v1" and estado == EstadoSaga.AGUARDANDO_APROVACAO:
            self._transicionar_saga(saga, EstadoSaga.RESERVANDO_PECAS)
            self._enfileirar_comando(
                saga=saga,
                destino="execucao",
                event_type=CMD_RESERVAR_PECAS,
                causation_id=envelope.event_id,
                payload={
                    "rodada": saga.rodada,
                    "reserva_id": saga.id,
                    "orcamento_id": str(payload["orcamento_id"]),
                    "orcamento_versao": int(payload["versao"]),
                    "itens_peca": payload.get("itens_peca", []),
                },
                traceparent=traceparent,
            )
            return True

        if evt == "OrcamentoRecusado.v1" and estado == EstadoSaga.AGUARDANDO_APROVACAO:
            self._registrar_status_os(os_model, StatusOS.EM_DIAGNOSTICO)
            self._transicionar_saga(saga, EstadoSaga.RECUSADA)
            return True

        if evt == "PecasReservadas.v1" and estado == EstadoSaga.RESERVANDO_PECAS:
            self._transicionar_saga(saga, EstadoSaga.CRIANDO_COBRANCA)
            self._enfileirar_comando(
                saga=saga,
                destino="billing",
                event_type="CriarCobranca.v1",
                causation_id=envelope.event_id,
                payload={
                    "rodada": saga.rodada,
                    "orcamento_id": str(saga.orcamento_id),
                    "orcamento_versao": int(saga.orcamento_versao or 1),
                    "cliente_id": str(os_model.cliente_id),
                    "total_centavos": int(saga.total_centavos or 0),
                    "moeda": "BRL",
                },
                traceparent=traceparent,
            )
            return True

        return self._aplicar_pagamento_e_execucao(
            saga, os_model, envelope, traceparent=traceparent
        )

    def _aplicar_pagamento_e_execucao(
        self,
        saga: SagaInstanceModel,
        os_model: OrdemDeServicoModel,
        envelope: Any,
        *,
        traceparent: str | None = None,
    ) -> bool:
        evt = envelope.event_type
        payload = envelope.payload
        estado = EstadoSaga(saga.estado)

        if evt == "CobrancaCriada.v1" and estado == EstadoSaga.CRIANDO_COBRANCA:
            saga.pagamento_id = str(payload["pagamento_id"])
            self._registrar_status_os(os_model, StatusOS.AGUARDANDO_PAGAMENTO)
            self._transicionar_saga(saga, EstadoSaga.AGUARDANDO_PAGAMENTO)
            return True

        if evt == "PagamentoConfirmado.v1" and estado in {
            EstadoSaga.CRIANDO_COBRANCA,
            EstadoSaga.AGUARDANDO_PAGAMENTO,
        }:
            saga.pagamento_id = str(payload["pagamento_id"])
            self._transicionar_saga(saga, EstadoSaga.ENFILEIRANDO)
            self._enfileirar_comando(
                saga=saga,
                destino="execucao",
                event_type=CMD_ENFILEIRAR_EXECUCAO,
                causation_id=envelope.event_id,
                payload={
                    "rodada": saga.rodada,
                    "reserva_id": saga.id,
                    "orcamento_id": str(payload["orcamento_id"]),
                    "pagamento_id": str(payload["pagamento_id"]),
                    "itens_servico": payload.get(
                        "itens_servico",
                        [
                            {
                                "servico_id": str(uuid4()),
                                "descricao": "Serviço aprovado no orçamento",
                                "preco_unitario_centavos": int(
                                    payload["total_centavos"]
                                ),
                            }
                        ],
                    ),
                    "itens_peca": payload.get("itens_peca", []),
                },
                traceparent=traceparent,
            )
            return True

        if evt == "ExecucaoEnfileirada.v1" and estado == EstadoSaga.ENFILEIRANDO:
            self._registrar_status_os(os_model, StatusOS.AGUARDANDO_EXECUCAO)
            self._transicionar_saga(saga, EstadoSaga.EM_EXECUCAO)
            return True

        if evt == "ExecucaoIniciada.v1" and estado == EstadoSaga.EM_EXECUCAO:
            self._registrar_status_os(os_model, StatusOS.EM_EXECUCAO)
            saga.version += 1
            saga.atualizada_em = datetime.now(timezone.utc)
            return True

        if evt == "ExecucaoConcluida.v1" and estado == EstadoSaga.EM_EXECUCAO:
            self._registrar_status_os(os_model, StatusOS.SERVICOS_CONCLUIDOS)
            self._registrar_status_os(os_model, StatusOS.FINALIZADA)
            self._transicionar_saga(saga, EstadoSaga.CONCLUIDA)
            return True

        return False

    def _aplicar_execucao_cancelada(
        self,
        saga: SagaInstanceModel,
        envelope: Any,
        *,
        traceparent: str | None = None,
    ) -> None:
        saga.execucao_cancelada_event_id = str(envelope.event_id)
        saga.subestado_compensacao = SubestadoCompensacao.EXECUTANDO_COMPENSACOES.value
        self._transicionar_saga(saga, EstadoSaga.COMPENSANDO_EFEITOS)
        comp_id = saga.compensacao_id or str(uuid4())
        motivo = saga.motivo_compensacao or MotivoCompensacao.FALHA_ENFILEIRAMENTO.value
        esperados = ["RESERVA"]
        if saga.orcamento_id:
            esperados.append("ORCAMENTO")
        if saga.pagamento_id:
            esperados.append("ESTORNO")
        saga.efeitos_esperados_json = esperados
        saga.efeitos_confirmados_json = []

        self._enfileirar_comando(
            saga=saga,
            destino="execucao",
            event_type=CMD_LIBERAR_RESERVA,
            causation_id=envelope.event_id,
            payload={
                "rodada": saga.rodada,
                "compensacao_id": comp_id,
                "motivo": motivo,
                "reserva_id": saga.id,
                "execucao_cancelada_event_id": str(envelope.event_id),
            },
            traceparent=traceparent,
        )
        if saga.orcamento_id:
            self._enfileirar_comando(
                saga=saga,
                destino="billing",
                event_type="CancelarOrcamento.v1",
                causation_id=envelope.event_id,
                payload={
                    "rodada": saga.rodada,
                    "compensacao_id": comp_id,
                    "motivo": motivo,
                    "orcamento_id": saga.orcamento_id,
                    "orcamento_versao": int(saga.orcamento_versao or 1),
                    "execucao_cancelada_event_id": str(envelope.event_id),
                },
                traceparent=traceparent,
            )
        if saga.pagamento_id:
            saga.compensacao_financeira_status = "PENDENTE"
            self._enfileirar_comando(
                saga=saga,
                destino="billing",
                event_type=CMD_ESTORNAR_PAGAMENTO,
                causation_id=envelope.event_id,
                payload={
                    "rodada": saga.rodada,
                    "compensacao_id": comp_id,
                    "motivo": motivo,
                    "pagamento_id": saga.pagamento_id,
                    "total_centavos": int(saga.total_centavos or 1),
                    "moeda": "BRL",
                    "execucao_cancelada_event_id": str(envelope.event_id),
                },
                traceparent=traceparent,
            )

    def _aplicar_compensacao(
        self,
        saga: SagaInstanceModel,
        os_model: OrdemDeServicoModel,
        envelope: Any,
        *,
        traceparent: str | None = None,
    ) -> bool:
        evt = envelope.event_type
        estado = EstadoSaga(saga.estado)

        if evt in {
            EVT_RESERVA_RECUSADA,
            "PagamentoRecusado.v1",
            EVT_EXECUCAO_REJEITADA,
        }:
            motivo_map = {
                EVT_RESERVA_RECUSADA: MotivoCompensacao.ESTOQUE_INSUFICIENTE.value,
                "PagamentoRecusado.v1": MotivoCompensacao.PAGAMENTO_RECUSADO.value,
                EVT_EXECUCAO_REJEITADA: MotivoCompensacao.FALHA_ENFILEIRAMENTO.value,
            }
            comp_id = uuid4()
            saga.compensacao_id = str(comp_id)
            saga.motivo_compensacao = motivo_map[evt]
            saga.subestado_compensacao = (
                SubestadoCompensacao.AGUARDANDO_BARREIRA_EXECUCAO.value
            )
            self._registrar_status_os(os_model, StatusOS.COMPENSACAO_PENDENTE)
            self._transicionar_saga(saga, EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO)
            self._enfileirar_comando(
                saga=saga,
                destino="execucao",
                event_type=CMD_CANCELAR_EXECUCAO,
                causation_id=envelope.event_id,
                payload={
                    "rodada": saga.rodada,
                    "compensacao_id": str(comp_id),
                    "motivo": saga.motivo_compensacao,
                    "execucao_id": None,
                },
                traceparent=traceparent,
            )
            return True

        if (
            evt == "ExecucaoCancelada.v1"
            and estado == EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO
        ):
            self._aplicar_execucao_cancelada(saga, envelope, traceparent=traceparent)
            return True

        if (
            evt == "ExecucaoCancelamentoRecusado.v1"
            and estado == EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO
        ):
            saga.subestado_compensacao = (
                SubestadoCompensacao.BLOQUEADA_POR_REPARO_INICIADO.value
            )
            self._registrar_status_os(os_model, StatusOS.COMPENSACAO_PENDENTE)
            self._transicionar_saga(saga, EstadoSaga.INTERVENCAO_MANUAL)
            return True

        if (
            evt
            in {EVT_RESERVA_LIBERADA, EVT_ORCAMENTO_CANCELADO, EVT_PAGAMENTO_ESTORNADO}
            and estado == EstadoSaga.COMPENSANDO_EFEITOS
        ):
            efeito_map = {
                EVT_RESERVA_LIBERADA: "RESERVA",
                EVT_ORCAMENTO_CANCELADO: "ORCAMENTO",
                EVT_PAGAMENTO_ESTORNADO: "ESTORNO",
            }
            efeito = efeito_map[evt]
            confirmados = list(saga.efeitos_confirmados_json or [])
            if efeito not in confirmados:
                confirmados.append(efeito)
            saga.efeitos_confirmados_json = confirmados
            if efeito == "ESTORNO":
                saga.compensacao_financeira_status = "CONCLUIDA"
            esperados = list(saga.efeitos_esperados_json or [])
            saga.version += 1
            saga.atualizada_em = datetime.now(timezone.utc)
            if esperados and set(esperados).issubset(set(confirmados)):
                saga.subestado_compensacao = SubestadoCompensacao.FINALIZADA.value
                self._registrar_status_os(os_model, StatusOS.CANCELADA)
                self._transicionar_saga(saga, EstadoSaga.COMPENSADA)
            return True

        return self._aplicar_estorno_tardio(
            saga, os_model, envelope, traceparent=traceparent
        )

    def _aplicar_estorno_tardio(
        self,
        saga: SagaInstanceModel,
        os_model: OrdemDeServicoModel,
        envelope: Any,
        *,
        traceparent: str | None = None,
    ) -> bool:
        evt = envelope.event_type
        payload = envelope.payload
        estado = EstadoSaga(saga.estado)
        estados_pos_barreira = {
            EstadoSaga.COMPENSANDO_EFEITOS,
            EstadoSaga.COMPENSADA,
            EstadoSaga.RECUSADA,
            EstadoSaga.INTERVENCAO_MANUAL,
        }
        status_financeiro_map = {
            "PagamentoEstornoFalhou.v1": "FALHA_PENDENTE",
            "PagamentoEstornoPendente.v1": "PENDENTE",
            EVT_PAGAMENTO_ESTORNADO: "CONCLUIDA",
        }
        if evt in status_financeiro_map and estado in estados_pos_barreira:
            saga.compensacao_financeira_status = status_financeiro_map[evt]
            saga.version += 1
            saga.atualizada_em = datetime.now(timezone.utc)
            return True

        if evt == "PagamentoConfirmado.v1" and estado in (
            estados_pos_barreira | {EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO}
        ):
            saga.pagamento_id = str(payload["pagamento_id"])
            saga.total_centavos = int(
                payload.get("total_centavos") or saga.total_centavos or 1
            )
            saga.compensacao_financeira_status = "PENDENTE"
            if saga.execucao_cancelada_event_id:
                if estado == EstadoSaga.COMPENSANDO_EFEITOS:
                    esperados = list(saga.efeitos_esperados_json or [])
                    if "ESTORNO" not in esperados:
                        esperados.append("ESTORNO")
                        saga.efeitos_esperados_json = esperados
                self._enfileirar_comando(
                    saga=saga,
                    destino="billing",
                    event_type=CMD_ESTORNAR_PAGAMENTO,
                    causation_id=envelope.event_id,
                    payload={
                        "rodada": saga.rodada,
                        "compensacao_id": saga.compensacao_id or str(uuid4()),
                        "motivo": MotivoCompensacao.PAGAMENTO_TARDIO.value,
                        "pagamento_id": saga.pagamento_id,
                        "total_centavos": int(saga.total_centavos or 1),
                        "moeda": "BRL",
                        "execucao_cancelada_event_id": saga.execucao_cancelada_event_id,
                    },
                    traceparent=traceparent,
                )
            elif estado == EstadoSaga.RECUSADA:
                comp_id = uuid4()
                saga.compensacao_id = str(comp_id)
                saga.motivo_compensacao = MotivoCompensacao.PAGAMENTO_TARDIO.value
                saga.subestado_compensacao = (
                    SubestadoCompensacao.AGUARDANDO_BARREIRA_EXECUCAO.value
                )
                self._registrar_status_os(os_model, StatusOS.COMPENSACAO_PENDENTE)
                self._transicionar_saga(saga, EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO)
                self._enfileirar_comando(
                    saga=saga,
                    destino="execucao",
                    event_type=CMD_CANCELAR_EXECUCAO,
                    causation_id=envelope.event_id,
                    payload={
                        "rodada": saga.rodada,
                        "compensacao_id": str(comp_id),
                        "motivo": saga.motivo_compensacao,
                        "execucao_id": None,
                    },
                    traceparent=traceparent,
                )
            return True

        return False

    def _aplicar_evento(
        self,
        saga: SagaInstanceModel,
        os_model: OrdemDeServicoModel,
        envelope: Any,
        *,
        traceparent: str | None = None,
    ) -> bool:
        if self._aplicar_fluxo_principal(
            saga, os_model, envelope, traceparent=traceparent
        ):
            return True
        return self._aplicar_compensacao(
            saga, os_model, envelope, traceparent=traceparent
        )

    def _reavaliar_eventos_adiantados(
        self, saga: SagaInstanceModel, os_model: OrdemDeServicoModel
    ) -> None:
        while True:
            pendentes = (
                self.db.query(EventoAdiantadoModel)
                .filter(
                    EventoAdiantadoModel.saga_id == saga.id,
                    EventoAdiantadoModel.rodada == saga.rodada,
                    EventoAdiantadoModel.status == "PENDENTE",
                )
                .order_by(EventoAdiantadoModel.criado_em.asc())
                .all()
            )
            progrediu = False
            for item in pendentes:
                env_pend = validar_envelope_v1(item.envelope_json)
                if self._aplicar_evento(
                    saga, os_model, env_pend, traceparent=item.traceparent
                ):
                    item.status = "APLICADO"
                    item.atualizado_em = datetime.now(timezone.utc)
                    self._concluir_step_correspondente(
                        saga_id=saga.id,
                        causation_id=str(env_pend.causation_id),
                        resposta_event_id=str(env_pend.event_id),
                        resposta_tipo=env_pend.event_type,
                    )
                    progrediu = True
                    break
            if not progrediu:
                break

    def processar_evento_envelope(
        self,
        dados: dict[str, Any],
        *,
        consumer: str = "os-orquestrador",
        traceparent: str | None = None,
    ) -> str:
        """
        Processa um evento validado com deduplicação atômica por Inbox (consumer, event_id),
        bufferização/reavaliação geral de eventos válidos adiantados e controle concorrente.
        """
        envelope = validar_envelope_v1(dados)

        ja_processado = (
            self.db.query(InboxEventoModel)
            .filter(
                InboxEventoModel.consumer == consumer,
                InboxEventoModel.event_id == str(envelope.event_id),
            )
            .first()
        )
        if ja_processado is not None:
            return "DUPLICADO"

        saga = (
            self.db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.id == str(envelope.saga_id))
            .with_for_update()
            .first()
        )
        if saga is None:
            raise ValueError(f"Saga {envelope.saga_id} não encontrada")

        os_model = (
            self.db.query(OrdemDeServicoModel)
            .filter(OrdemDeServicoModel.id == envelope.os_id)
            .first()
        )
        if os_model is None:
            raise ValueError(f"OS {envelope.os_id} não encontrada")

        payload = envelope.payload
        rodada_evt = payload.get("rodada")
        if rodada_evt is not None and int(rodada_evt) != saga.rodada:
            self.db.add(
                InboxEventoModel(
                    consumer=consumer,
                    event_id=str(envelope.event_id),
                    event_type=envelope.event_type,
                    saga_id=saga.id,
                )
            )
            self.db.commit()
            return "IGNORADO_PRECONDICAO"

        try:
            self.db.add(
                InboxEventoModel(
                    consumer=consumer,
                    event_id=str(envelope.event_id),
                    event_type=envelope.event_type,
                    saga_id=saga.id,
                )
            )
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            return "DUPLICADO"

        aplicado = self._aplicar_evento(
            saga, os_model, envelope, traceparent=traceparent
        )
        if not aplicado:
            estado_atual = EstadoSaga(saga.estado)
            estados_finais = {
                EstadoSaga.CONCLUIDA,
                EstadoSaga.COMPENSADA,
                EstadoSaga.RECUSADA,
                EstadoSaga.INTERVENCAO_MANUAL,
            }
            if estado_atual not in estados_finais:
                self.db.add(
                    EventoAdiantadoModel(
                        saga_id=saga.id,
                        event_id=str(envelope.event_id),
                        event_type=envelope.event_type,
                        rodada=saga.rodada,
                        envelope_json=dados,
                        traceparent=traceparent,
                        status="PENDENTE",
                    )
                )
                self.db.commit()
                return "ADIANTADO_PENDENTE"
            self.db.commit()
            return "IGNORADO_PRECONDICAO"

        self._concluir_step_correspondente(
            saga_id=saga.id,
            causation_id=str(envelope.causation_id),
            resposta_event_id=str(envelope.event_id),
            resposta_tipo=envelope.event_type,
        )
        self._reavaliar_eventos_adiantados(saga, os_model)
        logger.info(
            "Evento %s aplicado na Saga %s (estado=%s)",
            envelope.event_type,
            saga.id,
            saga.estado,
        )
        self.db.commit()
        return "PROCESSADO"

    def solicitar_cancelamento(
        self,
        *,
        os_id: UUID,
        motivo: str = MotivoCompensacao.CANCELAMENTO_CLIENTE.value,
        traceparent: str | None = None,
    ) -> SagaInstanceModel:
        saga = (
            self.db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.os_id == str(os_id))
            .order_by(SagaInstanceModel.rodada.desc())
            .first()
        )
        if saga is None:
            raise ValueError(MSG_SAGA_NAO_ENCONTRADA)
        os_model = (
            self.db.query(OrdemDeServicoModel)
            .filter(OrdemDeServicoModel.id == os_id)
            .first()
        )
        if os_model is None:
            raise ValueError("OS não encontrada")

        comp_id = uuid4()
        saga.compensacao_id = str(comp_id)
        saga.motivo_compensacao = motivo
        saga.subestado_compensacao = (
            SubestadoCompensacao.AGUARDANDO_BARREIRA_EXECUCAO.value
        )
        self._registrar_status_os(os_model, StatusOS.COMPENSACAO_PENDENTE, origem="API")
        self._transicionar_saga(saga, EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO)
        self._enfileirar_comando(
            saga=saga,
            destino="execucao",
            event_type="CancelarExecucao.v1",
            causation_id=UUID(saga.id),
            payload={
                "rodada": saga.rodada,
                "compensacao_id": str(comp_id),
                "motivo": motivo,
                "execucao_id": None,
            },
            traceparent=traceparent,
        )
        self.db.commit()
        return saga

    def reprocessar_estorno(
        self,
        *,
        os_id: UUID,
        traceparent: str | None = None,
    ) -> SagaInstanceModel:
        saga = (
            self.db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.os_id == str(os_id))
            .order_by(SagaInstanceModel.rodada.desc())
            .first()
        )
        if saga is None:
            raise ValueError(MSG_SAGA_NAO_ENCONTRADA)
        if (
            saga.compensacao_financeira_status != "FALHA_PENDENTE"
            or not saga.execucao_cancelada_event_id
            or not saga.pagamento_id
        ):
            raise ValueError("Saga não possui estorno pendente de reprocessamento")

        saga.compensacao_financeira_status = "PENDENTE"
        self._enfileirar_comando(
            saga=saga,
            destino="billing",
            event_type="EstornarPagamento.v1",
            causation_id=UUID(saga.id),
            payload={
                "rodada": saga.rodada,
                "compensacao_id": saga.compensacao_id or str(uuid4()),
                "motivo": saga.motivo_compensacao
                or MotivoCompensacao.FALHA_ENFILEIRAMENTO.value,
                "pagamento_id": saga.pagamento_id,
                "total_centavos": int(saga.total_centavos or 1),
                "moeda": "BRL",
                "execucao_cancelada_event_id": saga.execucao_cancelada_event_id,
            },
            traceparent=traceparent,
        )
        self.db.commit()
        return saga

    def _concluir_step_correspondente(
        self,
        *,
        saga_id: str,
        causation_id: str,
        resposta_event_id: str,
        resposta_tipo: str,
    ) -> None:
        comando_esperado = COMANDO_POR_EVENTO_RESPOSTA.get(resposta_tipo)
        query_base = self.db.query(SagaStepModel).filter(
            SagaStepModel.saga_id == saga_id,
            SagaStepModel.status == "PENDENTE",
        )
        if comando_esperado:
            query_base = query_base.filter(
                SagaStepModel.comando_tipo == comando_esperado
            )
        step = query_base.filter(SagaStepModel.comando_event_id == causation_id).first()
        if step is None and comando_esperado:
            step = query_base.order_by(SagaStepModel.criado_em.asc()).first()
        if step is not None:
            step.status = "CONCLUIDO"
            step.resposta_event_id = resposta_event_id
            step.resposta_tipo = resposta_tipo
            step.atualizado_em = datetime.now(timezone.utc)

    def expirar_sagas_vencidas(self, *, agora: datetime | None = None) -> int:
        ref = agora or datetime.now(timezone.utc)
        estados_expiraveis = [
            EstadoSaga.DIAGNOSTICO.value,
            EstadoSaga.GERANDO_ORCAMENTO.value,
            EstadoSaga.AGUARDANDO_APROVACAO.value,
            EstadoSaga.AGUARDANDO_PAGAMENTO.value,
        ]
        sagas = (
            self.db.query(SagaInstanceModel)
            .filter(
                SagaInstanceModel.estado.in_(estados_expiraveis),
                SagaInstanceModel.deadline_at.is_not(None),
                SagaInstanceModel.deadline_at <= ref,
            )
            .all()
        )
        expiradas = 0
        for saga in sagas:
            os_model = (
                self.db.query(OrdemDeServicoModel)
                .filter(OrdemDeServicoModel.id == UUID(saga.os_id))
                .first()
            )
            if os_model is None:
                continue
            motivo_timeout_map = {
                EstadoSaga.DIAGNOSTICO.value: MotivoCompensacao.TIMEOUT_DIAGNOSTICO.value,
                EstadoSaga.GERANDO_ORCAMENTO.value: MotivoCompensacao.TIMEOUT_ORCAMENTO.value,
                EstadoSaga.AGUARDANDO_PAGAMENTO.value: MotivoCompensacao.PAGAMENTO_EXPIRADO.value,
            }
            comp_id = uuid4()
            saga.compensacao_id = str(comp_id)
            saga.motivo_compensacao = motivo_timeout_map.get(
                saga.estado, MotivoCompensacao.TIMEOUT_DIAGNOSTICO.value
            )
            saga.subestado_compensacao = (
                SubestadoCompensacao.AGUARDANDO_BARREIRA_EXECUCAO.value
            )
            self._registrar_status_os(
                os_model, StatusOS.COMPENSACAO_PENDENTE, origem="WORKER_TIMEOUT"
            )
            self._transicionar_saga(saga, EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO)
            self._enfileirar_comando(
                saga=saga,
                destino="execucao",
                event_type="CancelarExecucao.v1",
                causation_id=UUID(saga.id),
                payload={
                    "rodada": saga.rodada,
                    "compensacao_id": str(comp_id),
                    "motivo": saga.motivo_compensacao,
                    "execucao_id": None,
                },
            )
            expiradas += 1
        if expiradas:
            self.db.commit()
        return expiradas

    def reabrir_nova_rodada(
        self,
        *,
        os_id: UUID,
        traceparent: str | None = None,
    ) -> SagaInstanceModel:
        anterior = (
            self.db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.os_id == str(os_id))
            .order_by(SagaInstanceModel.rodada.desc())
            .first()
        )
        if anterior is None:
            raise ValueError(MSG_SAGA_NAO_ENCONTRADA)
        if anterior.estado != EstadoSaga.RECUSADA.value:
            raise ValueError("Nova rodada só é permitida após recusa de orçamento")
        os_model = (
            self.db.query(OrdemDeServicoModel)
            .filter(OrdemDeServicoModel.id == os_id)
            .first()
        )
        if os_model is None:
            raise ValueError("OS não encontrada")

        self._registrar_status_os(os_model, StatusOS.EM_DIAGNOSTICO, origem="API")
        nova_saga = self.iniciar_saga_abertura(
            os_id=os_id,
            cliente_id=os_model.cliente_id,
            veiculo_id=os_model.veiculo_id,
            descricao_problema=os_model.descricao_problema,
            rodada=anterior.rodada + 1,
            traceparent=traceparent,
        )
        self.db.commit()
        return nova_saga
