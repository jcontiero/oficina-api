from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.atendimento.aplicacao.casos_de_uso import AbrirOrdemDeServico
from src.atendimento.infraestrutura.modelos import (
    ClienteModel,
    OrdemDeServicoModel,
    VeiculoModel,
)
from src.atendimento.infraestrutura.repositorios import (
    ClienteRepositorioImpl,
    OrdemDeServicoRepositorioImpl,
    VeiculoRepositorioImpl,
)
from src.config import Configuracoes
from src.identidade.infraestrutura.jwt_provider import JwtTokenProvider
from src.saga.aplicacao.orquestrador import OrquestradorSaga
from src.saga.dominio.estados import EstadoSaga
from src.saga.infraestrutura.modelos import SagaInstanceModel, SagaStepModel
from src.shared.banco import Base
from src.shared.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
from src.shared.outbox import OutboxEventoModel


def _db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'audit_os.sqlite'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed_os_e_saga(
    db, *, estado: str, rodada: int = 1, execucao_cancelada_event_id: str | None = None
):
    os_id = uuid4()
    saga_id = uuid4()
    cliente_id = uuid4()
    veiculo_id = uuid4()
    db.add(
        ClienteModel(
            id=cliente_id,
            nome="Cliente Teste",
            cpf="52998224725",
            email=f"{cliente_id}@teste.local",
            telefone="11999999999",
        )
    )
    db.add(
        VeiculoModel(
            id=veiculo_id,
            cliente_id=cliente_id,
            placa="ABC1234",
            marca="VW",
            modelo="Gol",
            ano=2020,
        )
    )
    db.add(
        OrdemDeServicoModel(
            id=os_id,
            cliente_id=cliente_id,
            veiculo_id=veiculo_id,
            descricao_problema="Barulho no freio",
            status="RECEBIDA",
        )
    )
    db.add(
        SagaInstanceModel(
            id=str(saga_id),
            os_id=str(os_id),
            rodada=rodada,
            estado=estado,
            correlation_id=str(saga_id),
            orcamento_id=str(uuid4()),
            orcamento_versao=1,
            pagamento_id=str(uuid4()),
            total_centavos=25000,
            execucao_cancelada_event_id=execucao_cancelada_event_id,
            compensacao_financeira_status=(
                "PENDENTE" if execucao_cancelada_event_id else "NAO_APLICAVEL"
            ),
        )
    )
    db.commit()
    return os_id, saga_id


def _evt(event_type: str, *, saga_id, os_id, producer: str, payload: dict) -> dict:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": producer,
        "saga_id": str(saga_id),
        "os_id": str(os_id),
        "correlation_id": str(saga_id),
        "causation_id": str(uuid4()),
        "aggregate_version": 2,
        "payload": payload,
    }


def test_r01_abertura_os_e_saga_atomica_sem_commit_interno(tmp_path) -> None:
    session_factory = _db_session(tmp_path)
    with session_factory() as db:
        cid = uuid4()
        vid = uuid4()
        db.add(
            ClienteModel(
                id=cid,
                nome="Ana",
                cpf="52998224725",
                email="ana@t.local",
                telefone="11999999999",
            )
        )
        db.add(
            VeiculoModel(
                id=vid,
                cliente_id=cid,
                placa="XYZ9876",
                marca="Fiat",
                modelo="Uno",
                ano=2019,
            )
        )
        db.commit()

    with session_factory() as db:
        caso = AbrirOrdemDeServico(
            OrdemDeServicoRepositorioImpl(db),
            ClienteRepositorioImpl(db),
            VeiculoRepositorioImpl(db),
            SQLAlchemyUnitOfWork(db),
        )
        caso.preparar_abertura("52998224725", "XYZ9876", "Revisao geral")
        # Se ocorrer erro antes do commit final (ex: falha ao iniciar Saga), rollback desfaz a OS
        db.rollback()

    with session_factory() as db:
        assert db.query(OrdemDeServicoModel).count() == 0


def test_r04_pagamento_confirmado_em_criando_cobranca_nao_e_perdido(tmp_path) -> None:
    session_factory = _db_session(tmp_path)
    with session_factory() as db:
        os_id, saga_id = _seed_os_e_saga(db, estado=EstadoSaga.CRIANDO_COBRANCA.value)
        res = OrquestradorSaga(db).processar_evento_envelope(
            _evt(
                "PagamentoConfirmado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "orcamento_id": str(uuid4()),
                    "pagamento_id": str(uuid4()),
                    "provider_order_id": "ORD_1",
                    "total_centavos": 25000,
                    "moeda": "BRL",
                    "orcamento_versao": 1,
                    "itens_servico": [],
                    "itens_peca": [],
                },
            )
        )
        assert res == "PROCESSADO"
        saga = (
            db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.id == str(saga_id))
            .first()
        )
        assert saga is not None
        assert saga.estado == EstadoSaga.ENFILEIRANDO.value


def test_r06_estorno_tardio_confirmado_em_compensada_atualiza_status(tmp_path) -> None:
    session_factory = _db_session(tmp_path)
    with session_factory() as db:
        os_id, saga_id = _seed_os_e_saga(
            db,
            estado=EstadoSaga.COMPENSADA.value,
            execucao_cancelada_event_id=str(uuid4()),
        )
        res = OrquestradorSaga(db).processar_evento_envelope(
            _evt(
                "PagamentoEstornado.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-billing",
                payload={
                    "rodada": 1,
                    "compensacao_id": str(uuid4()),
                    "pagamento_id": str(uuid4()),
                    "provider_order_id": "ORD_1",
                    "total_centavos": 25000,
                    "moeda": "BRL",
                    "resultado": "ESTORNADO",
                    "motivo": "PAGAMENTO_TARDIO",
                },
            )
        )
        assert res == "PROCESSADO"
        saga = (
            db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.id == str(saga_id))
            .first()
        )
        assert saga is not None
        assert saga.compensacao_financeira_status == "CONCLUIDA"


def test_r07_jwt_exige_chave_persistente_em_homolog_e_production() -> None:
    cfg = Configuracoes(environment="homolog", admin_jwt_private_key_pem="")
    with pytest.raises(ValueError, match="ADMIN_JWT_PRIVATE_KEY_PEM"):
        JwtTokenProvider(cfg)


def test_r08_expiracao_deadline_saga_e_atualizacao_saga_step(tmp_path) -> None:
    session_factory = _db_session(tmp_path)
    with session_factory() as db:
        os_id, saga_id = _seed_os_e_saga(db, estado=EstadoSaga.DIAGNOSTICO.value)
        saga = (
            db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.id == str(saga_id))
            .first()
        )
        assert saga is not None
        saga.deadline_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

        expiradas = OrquestradorSaga(db).expirar_sagas_vencidas(
            agora=datetime.now(timezone.utc)
        )
        assert expiradas == 1
        db.refresh(saga)
        assert saga.estado == EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO.value


def test_r10_reabrir_nova_rodada_apos_recusa_orcamento(tmp_path) -> None:
    session_factory = _db_session(tmp_path)
    with session_factory() as db:
        os_id, _ = _seed_os_e_saga(db, estado=EstadoSaga.RECUSADA.value, rodada=1)
        nova = OrquestradorSaga(db).reabrir_nova_rodada(os_id=os_id)
        assert nova.rodada == 2
        assert nova.estado == EstadoSaga.DIAGNOSTICO.value


def test_r11_traceparent_e_correlacao_propagados_no_outbox_e_worker(tmp_path) -> None:
    session_factory = _db_session(tmp_path)
    trace = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    with session_factory() as db:
        os_id, saga_id = _seed_os_e_saga(db, estado=EstadoSaga.DIAGNOSTICO.value)
        OrquestradorSaga(db).processar_evento_envelope(
            _evt(
                "DiagnosticoConcluido.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-execucao",
                payload={
                    "rodada": 1,
                    "diagnostico_id": str(uuid4()),
                    "laudo": "OK",
                    "itens_servico": [],
                    "itens_peca": [],
                },
            ),
            traceparent=trace,
        )
        out = db.query(OutboxEventoModel).first()
        assert out is not None
        assert out.traceparent == trace


def test_r04_orcamento_aprovado_adiantado_reavaliado_apos_orcamento_gerado(
    tmp_path,
) -> None:
    session_factory = _db_session(tmp_path)
    orc_id = str(uuid4())
    cli_id = str(uuid4())
    with session_factory() as db:
        os_id, saga_id = _seed_os_e_saga(db, estado=EstadoSaga.GERANDO_ORCAMENTO.value)
        orq = OrquestradorSaga(db)
        # OrcamentoAprovado.v1 chega ANTES de OrcamentoGerado.v1
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
                    "cliente_id": cli_id,
                    "total_centavos": 25000,
                    "moeda": "BRL",
                    "itens_peca": [],
                },
            )
        )
        # Quando OrcamentoGerado.v1 chega, a Saga transiciona para AGUARDANDO_APROVACAO
        # e imediatamente reavalia OrcamentoAprovado.v1 pendente -> RESERVANDO_PECAS
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
                    "total_centavos": 25000,
                    "moeda": "BRL",
                },
            )
        )
        saga = (
            db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.id == str(saga_id))
            .one()
        )
        assert saga.estado == EstadoSaga.RESERVANDO_PECAS.value
        evts = [o.tipo_evento for o in db.query(OutboxEventoModel).all()]
        assert "ReservarPecas.v1" in evts


def test_r08_deadlines_por_etapa_e_execucao_no_worker(tmp_path) -> None:
    from src.worker import executar_ciclo_worker

    session_factory = _db_session(tmp_path)
    with session_factory() as db:
        os_id, saga_id = _seed_os_e_saga(db, estado=EstadoSaga.DIAGNOSTICO.value)
        saga = (
            db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.id == str(saga_id))
            .one()
        )
        saga.deadline_at = None
        db.commit()

        OrquestradorSaga(db).processar_evento_envelope(
            _evt(
                "DiagnosticoConcluido.v1",
                saga_id=saga_id,
                os_id=os_id,
                producer="oficina-execucao",
                payload={
                    "rodada": 1,
                    "diagnostico_id": str(uuid4()),
                    "laudo": "OK",
                    "itens_servico": [],
                    "itens_peca": [],
                },
            )
        )
        db.refresh(saga)
        assert saga.estado == EstadoSaga.GERANDO_ORCAMENTO.value
        assert saga.deadline_at is not None

        # Força vencimento para verificar execução automática de expirar_sagas_vencidas no worker
        saga.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        db.commit()

    class _DummySub:
        def subscription_path(self, p, s):
            return s

        def pull(self, request, timeout=5):
            return type("R", (), {"received_messages": []})()

    class _DummyPub:
        def topic_path(self, p, t):
            return t

    resumo = executar_ciclo_worker(
        session_factory,
        publisher=_DummyPub(),
        subscriber=_DummySub(),
        project_id="p",
        subscription_name="s",
        environment="homolog",
    )
    assert resumo["expiradas"] == 1


def test_r08_saga_step_concluido_por_causation_id_e_nao_ultimo_pendente(
    tmp_path,
) -> None:
    session_factory = _db_session(tmp_path)
    with session_factory() as db:
        os_id, saga_id = _seed_os_e_saga(
            db,
            estado=EstadoSaga.COMPENSANDO_EFEITOS.value,
            execucao_cancelada_event_id=str(uuid4()),
        )
        saga = (
            db.query(SagaInstanceModel)
            .filter(SagaInstanceModel.id == str(saga_id))
            .one()
        )
        saga.efeitos_esperados_json = ["RESERVA", "ORCAMENTO"]
        saga.efeitos_confirmados_json = []
        cmd_liberar = str(uuid4())
        cmd_cancelar_orc = str(uuid4())
        db.add(
            SagaStepModel(
                saga_id=str(saga_id),
                etapa="COMPENSANDO_EFEITOS",
                comando_event_id=cmd_liberar,
                comando_tipo="LiberarReserva.v1",
                status="PENDENTE",
                criado_em=datetime.now(timezone.utc) - timedelta(seconds=2),
            )
        )
        db.add(
            SagaStepModel(
                saga_id=str(saga_id),
                etapa="COMPENSANDO_EFEITOS",
                comando_event_id=cmd_cancelar_orc,
                comando_tipo="CancelarOrcamento.v1",
                status="PENDENTE",
                criado_em=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
        )
        db.commit()

        # Chega ReservaLiberada.v1 (que corresponde ao 1o step, NÃO ao último)
        evt = _evt(
            "ReservaLiberada.v1",
            saga_id=saga_id,
            os_id=os_id,
            producer="oficina-execucao",
            payload={
                "rodada": 1,
                "compensacao_id": str(uuid4()),
                "reserva_id": str(saga_id),
                "resultado": "LIBERADA",
                "motivo": "ORCAMENTO_RECUSADO",
            },
        )
        evt["causation_id"] = cmd_liberar
        OrquestradorSaga(db).processar_evento_envelope(evt)

        step_lib = (
            db.query(SagaStepModel)
            .filter(SagaStepModel.comando_event_id == cmd_liberar)
            .one()
        )
        step_orc = (
            db.query(SagaStepModel)
            .filter(SagaStepModel.comando_event_id == cmd_cancelar_orc)
            .one()
        )
        assert step_lib.status == "CONCLUIDO"
        assert step_orc.status == "PENDENTE"


def test_r11_consumidor_ativa_contexto_correlacao_e_traceparent_nos_logs(
    tmp_path, caplog
) -> None:
    import logging
    from src.worker import _FiltroCorrelacaoPadrao, consumir_mensagens_pull

    session_factory = _db_session(tmp_path)
    with session_factory() as db:
        os_id, saga_id = _seed_os_e_saga(db, estado=EstadoSaga.DIAGNOSTICO.value)

    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    span_id = "00f067aa0ba902b7"
    trace = f"00-{trace_id}-{span_id}-01"
    evt = _evt(
        "DiagnosticoConcluido.v1",
        saga_id=saga_id,
        os_id=os_id,
        producer="oficina-execucao",
        payload={
            "rodada": 1,
            "diagnostico_id": str(uuid4()),
            "laudo": "OK",
            "itens_servico": [],
            "itens_peca": [],
        },
    )

    msg = type(
        "M",
        (),
        {
            "data": __import__("json").dumps(evt).encode("utf-8"),
            "attributes": {"traceparent": trace},
        },
    )()
    rec = type("Rec", (), {"ack_id": "ack-1", "message": msg})()

    class _Sub:
        def subscription_path(self, p, s):
            return s

        def pull(self, request, timeout=5):
            return type("Resp", (), {"received_messages": [rec]})()

        def acknowledge(self, request):
            return None

    target_logger = logging.getLogger("saga-orquestrador")
    filtro = _FiltroCorrelacaoPadrao()
    target_logger.addFilter(filtro)
    try:
        with caplog.at_level(logging.INFO, logger="saga-orquestrador"):
            processadas = consumir_mensagens_pull(
                session_factory,
                _Sub(),
                project_id="p",
                subscription_name="s",
            )
        assert processadas == 1
        assert any(
            getattr(r, "correlation_id", "") == str(saga_id)
            and getattr(r, "saga_id", "") == str(saga_id)
            and getattr(r, "os_id", "") == str(os_id)
            and getattr(r, "event_id", "") == evt["event_id"]
            and getattr(r, "dd.trace_id", "0") == str(int(trace_id, 16))
            and getattr(r, "dd.span_id", "0") == str(int(span_id, 16))
            for r in caplog.records
        )
    finally:
        target_logger.removeFilter(filtro)
