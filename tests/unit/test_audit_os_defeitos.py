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
from src.saga.infraestrutura.modelos import SagaInstanceModel
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
