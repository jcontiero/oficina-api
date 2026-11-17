from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.atendimento.dominio.value_objects import CPF, StatusOS
from src.atendimento.infraestrutura.modelos import (
    ClienteModel,
    OrdemDeServicoModel,
    VeiculoModel,
)
from src.saga.aplicacao.orquestrador import OrquestradorSaga
from src.saga.dominio.estados import EstadoSaga
from src.saga.infraestrutura.modelos import SagaInstanceModel
from src.shared.banco import Base
from src.shared.outbox import OutboxEventoModel


def _setup(tmp_path, suffix: str):
    eng = create_engine(
        f"sqlite:///{tmp_path / f'p5_{suffix}.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    with Session() as db:
        cli_id = uuid4()
        vei_id = uuid4()
        os_id = uuid4()
        db.add(
            ClienteModel(
                id=cli_id,
                nome="Cliente P5",
                cpf=CPF("52998224725"),
                email="p5@teste.com",
                telefone="11999999999",
            )
        )
        db.add(
            VeiculoModel(
                id=vei_id,
                cliente_id=cli_id,
                placa="PFA5A23",
                marca="Honda",
                modelo="Civic",
                ano=2024,
            )
        )
        db.add(
            OrdemDeServicoModel(
                id=os_id,
                cliente_id=cli_id,
                veiculo_id=vei_id,
                descricao_problema="Teste compensacoes P5",
                status=StatusOS.RECEBIDA,
                criada_em=datetime.now(timezone.utc),
                atualizada_em=datetime.now(timezone.utc),
            )
        )
        db.commit()
    return Session, cli_id, vei_id, os_id


def _evt(
    event_type: str,
    *,
    saga_id: str,
    os_id,
    payload: dict,
    producer: str = "oficina-execucao",
) -> dict:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": producer,
        "saga_id": saga_id,
        "os_id": str(os_id),
        "correlation_id": saga_id,
        "causation_id": saga_id,
        "aggregate_version": 1,
        "payload": payload,
    }


def _avancar_ate_aguardando_pagamento(
    Session, cli_id, vei_id, os_id
) -> tuple[str, str, str]:
    orc_id = str(uuid4())
    pag_id = str(uuid4())
    with Session() as db:
        orq = OrquestradorSaga(db)
        saga = orq.iniciar_saga_abertura(
            os_id=os_id,
            cliente_id=cli_id,
            veiculo_id=vei_id,
            descricao_problema="P5",
        )
        db.commit()
        saga_id = saga.id
        orq.processar_evento_envelope(
            _evt(
                "DiagnosticoConcluido.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "diagnostico_id": str(uuid4()),
                    "laudo": "Freio",
                    "itens_servico": [
                        {
                            "servico_id": str(uuid4()),
                            "descricao": "Troca",
                            "preco_unitario_centavos": 10000,
                        }
                    ],
                    "itens_peca": [],
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "OrcamentoGerado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "orcamento_id": orc_id,
                    "versao": 1,
                    "total_centavos": 10000,
                    "moeda": "BRL",
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "OrcamentoAprovado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "orcamento_id": orc_id,
                    "versao": 1,
                    "cliente_id": str(cli_id),
                    "total_centavos": 10000,
                    "moeda": "BRL",
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "PecasReservadas.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "reserva_id": saga_id,
                    "status": "RESERVA_LOGICA_VAZIA",
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "CobrancaCriada.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "orcamento_id": orc_id,
                    "pagamento_id": pag_id,
                    "provider_order_id": "ORD_1",
                    "qr_data": "000201QR",
                    "total_centavos": 10000,
                    "moeda": "BRL",
                },
            )
        )
    return saga_id, orc_id, pag_id


def test_p5_recusa_pagamento_compensacao_completa(tmp_path) -> None:
    Session, cli_id, vei_id, os_id = _setup(tmp_path, "recusa")
    saga_id, orc_id, pag_id = _avancar_ate_aguardando_pagamento(
        Session, cli_id, vei_id, os_id
    )
    comp_id = str(uuid4())

    with Session() as db:
        orq = OrquestradorSaga(db)
        orq.processar_evento_envelope(
            _evt(
                "PagamentoRecusado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "orcamento_id": orc_id,
                    "pagamento_id": pag_id,
                    "motivo": "failed",
                },
            )
        )
        saga = db.query(SagaInstanceModel).filter_by(id=saga_id).one()
        assert saga.estado == EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO.value

        orq.processar_evento_envelope(
            _evt(
                "ExecucaoCancelada.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "resultado": "CANCELADA",
                    "motivo": "PAGAMENTO_RECUSADO",
                    "tombstone_persistido": True,
                },
            )
        )
        saga = db.query(SagaInstanceModel).filter_by(id=saga_id).one()
        assert saga.estado == EstadoSaga.COMPENSANDO_EFEITOS.value
        assert set(saga.efeitos_esperados_json) == {"RESERVA", "ORCAMENTO", "ESTORNO"}

        orq.processar_evento_envelope(
            _evt(
                "ReservaLiberada.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "reserva_id": saga_id,
                    "resultado": "LIBERADA",
                    "motivo": "PAGAMENTO_RECUSADO",
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "OrcamentoCancelado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "orcamento_id": orc_id,
                    "resultado": "CANCELADO",
                    "motivo": "PAGAMENTO_RECUSADO",
                },
            )
        )
        saga = db.query(SagaInstanceModel).filter_by(id=saga_id).one()
        assert saga.estado == EstadoSaga.COMPENSANDO_EFEITOS.value

        orq.processar_evento_envelope(
            _evt(
                "PagamentoEstornado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "pagamento_id": pag_id,
                    "provider_order_id": "ORD_1",
                    "total_centavos": 10000,
                    "moeda": "BRL",
                    "resultado": "CANCELADO_SEM_COBRANCA",
                    "motivo": "PAGAMENTO_RECUSADO",
                },
            )
        )
        saga = db.query(SagaInstanceModel).filter_by(id=saga_id).one()
        os_m = db.query(OrdemDeServicoModel).filter_by(id=os_id).one()
        assert saga.estado == EstadoSaga.COMPENSADA.value
        assert os_m.status == StatusOS.CANCELADA


def test_p5_rejeicao_fila_falha_estorno_recuperavel_e_pagamento_tardio(
    tmp_path,
) -> None:
    Session, cli_id, vei_id, os_id = _setup(tmp_path, "estorno")
    saga_id, orc_id, pag_id = _avancar_ate_aguardando_pagamento(
        Session, cli_id, vei_id, os_id
    )
    comp_id = str(uuid4())

    with Session() as db:
        orq = OrquestradorSaga(db)
        orq.processar_evento_envelope(
            _evt(
                "PagamentoConfirmado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "orcamento_id": orc_id,
                    "pagamento_id": pag_id,
                    "provider_order_id": "ORD_1",
                    "total_centavos": 10000,
                    "moeda": "BRL",
                    "orcamento_versao": 1,
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "ExecucaoRejeitada.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "reserva_id": saga_id,
                    "motivo": "FILA_INDISPONIVEL",
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "ExecucaoCancelada.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "resultado": "CANCELADA",
                    "motivo": "FALHA_ENFILEIRAMENTO",
                    "tombstone_persistido": True,
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "ReservaLiberada.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "reserva_id": saga_id,
                    "resultado": "LIBERADA",
                    "motivo": "FALHA_ENFILEIRAMENTO",
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "OrcamentoCancelado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "orcamento_id": orc_id,
                    "resultado": "CANCELADO",
                    "motivo": "FALHA_ENFILEIRAMENTO",
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "PagamentoEstornoFalhou.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "pagamento_id": pag_id,
                    "resultado": "FALHA_DEFINITIVA",
                    "motivo": "timeout MP",
                },
            )
        )
        saga = db.query(SagaInstanceModel).filter_by(id=saga_id).one()
        assert saga.estado == EstadoSaga.COMPENSANDO_EFEITOS.value
        assert saga.compensacao_financeira_status == "FALHA_PENDENTE"

        orq.reprocessar_estorno(os_id=os_id)
        orq.processar_evento_envelope(
            _evt(
                "PagamentoEstornado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "compensacao_id": comp_id,
                    "pagamento_id": pag_id,
                    "provider_order_id": "ORD_1",
                    "total_centavos": 10000,
                    "moeda": "BRL",
                    "resultado": "ESTORNADO",
                    "motivo": "FALHA_ENFILEIRAMENTO",
                },
            )
        )
        saga = db.query(SagaInstanceModel).filter_by(id=saga_id).one()
        assert saga.estado == EstadoSaga.COMPENSADA.value
        assert saga.compensacao_financeira_status == "CONCLUIDA"

        qtd_antes = db.query(OutboxEventoModel).count()
        orq.processar_evento_envelope(
            _evt(
                "PagamentoConfirmado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "orcamento_id": orc_id,
                    "pagamento_id": pag_id,
                    "provider_order_id": "ORD_1",
                    "total_centavos": 10000,
                    "moeda": "BRL",
                    "orcamento_versao": 1,
                },
            )
        )
        novos = db.query(OutboxEventoModel).offset(qtd_antes).all()
        assert [e.tipo_evento for e in novos] == ["EstornarPagamento.v1"]


def test_p5_concorrencia_cancelamento_vs_reparo_iniciado_exige_intervencao(
    tmp_path,
) -> None:
    Session, cli_id, vei_id, os_id = _setup(tmp_path, "race")
    saga_id, orc_id, pag_id = _avancar_ate_aguardando_pagamento(
        Session, cli_id, vei_id, os_id
    )

    with Session() as db:
        orq = OrquestradorSaga(db)
        orq.processar_evento_envelope(
            _evt(
                "PagamentoConfirmado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "orcamento_id": orc_id,
                    "pagamento_id": pag_id,
                    "provider_order_id": "ORD_1",
                    "total_centavos": 10000,
                    "moeda": "BRL",
                    "orcamento_versao": 1,
                },
            )
        )
        orq.processar_evento_envelope(
            _evt(
                "ExecucaoEnfileirada.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "execucao_id": f"{os_id}_1",
                    "reserva_id": saga_id,
                    "status": "AGUARDANDO_EXECUCAO",
                },
            )
        )
        orq.solicitar_cancelamento(os_id=os_id)
        orq.processar_evento_envelope(
            _evt(
                "ExecucaoCancelamentoRecusado.v1",
                saga_id=saga_id,
                os_id=os_id,
                payload={
                    "rodada": 1,
                    "compensacao_id": str(uuid4()),
                    "resultado": "RECUSADO",
                    "motivo": "REPARO_INICIADO",
                    "execucao_id": f"{os_id}_1",
                },
            )
        )
        saga = db.query(SagaInstanceModel).filter_by(id=saga_id).one()
        assert saga.estado == EstadoSaga.INTERVENCAO_MANUAL.value
        assert saga.subestado_compensacao == "BLOQUEADA_POR_REPARO_INICIADO"
