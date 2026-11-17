from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.atendimento.dominio.value_objects import StatusOS
from src.atendimento.infraestrutura.modelos import (
    ClienteModel,
    OrdemDeServicoModel,
    VeiculoModel,
)
from src.config import Configuracoes
from src.main import criar_app
from src.saga.aplicacao.orquestrador import OrquestradorSaga
from src.saga.dominio.estados import EstadoSaga
from src.saga.infraestrutura.modelos import SagaInstanceModel
from src.shared.banco import Base
from src.shared.outbox import OutboxEventoModel
from src.worker import consumir_mensagens_pull, publicar_lote_outbox


def _criar_sessao_sqlite(tmp_path):
    db_file = tmp_path / "p4_saga.sqlite"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _seed_os(db):
    cli_id = uuid4()
    vei_id = uuid4()
    os_id = uuid4()
    db.add(
        ClienteModel(
            id=cli_id,
            nome="João",
            cpf="52998224725",
            email="joao@teste.com",
            telefone="11999990000",
            status="ATIVO",
        )
    )
    db.add(
        VeiculoModel(
            id=vei_id,
            cliente_id=cli_id,
            placa="ABC1D23",
            marca="Ford",
            modelo="Ka",
            ano=2020,
            cor="Prata",
        )
    )
    db.add(
        OrdemDeServicoModel(
            id=os_id,
            cliente_id=cli_id,
            veiculo_id=vei_id,
            descricao_problema="Ruído no freio",
            status=StatusOS.RECEBIDA,
        )
    )
    db.commit()
    return cli_id, vei_id, os_id


def _envelope(
    *,
    event_type: str,
    producer: str,
    saga_id: UUID,
    os_id: UUID,
    correlation_id: UUID,
    causation_id: UUID,
    payload: dict,
    event_id: UUID | None = None,
    aggregate_version: int = 1,
) -> dict:
    return {
        "event_id": str(event_id or uuid4()),
        "event_type": event_type,
        "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": producer,
        "saga_id": str(saga_id),
        "os_id": str(os_id),
        "correlation_id": str(correlation_id),
        "causation_id": str(causation_id),
        "aggregate_version": aggregate_version,
        "payload": payload,
    }


def test_fluxo_feliz_orquestrador_reinicio_e_deduplicacao(tmp_path):
    SessionLocal = _criar_sessao_sqlite(tmp_path)
    with SessionLocal() as db:
        cli_id, vei_id, os_id = _seed_os(db)
        orq = OrquestradorSaga(db, environment="homolog")
        saga = orq.iniciar_saga_abertura(
            os_id=os_id,
            cliente_id=cli_id,
            veiculo_id=vei_id,
            descricao_problema="Ruído no freio",
        )
        db.commit()
        saga_id = UUID(saga.id)
        corr_id = UUID(saga.correlation_id)

        outbox_inicial = db.query(OutboxEventoModel).all()
        assert len(outbox_inicial) == 1
        assert outbox_inicial[0].tipo_evento == "SolicitarDiagnostico.v1"

    # Simula reinício do Orquestrador (nova instância Python e nova sessão SQL)
    evt_diag_id = uuid4()
    env_diag = _envelope(
        event_id=evt_diag_id,
        event_type="DiagnosticoConcluido.v1",
        producer="oficina-execucao",
        saga_id=saga_id,
        os_id=os_id,
        correlation_id=corr_id,
        causation_id=saga_id,
        payload={
            "rodada": 1,
            "diagnostico_id": f"{os_id}_1",
            "laudo": "Trocar pastilhas",
            "itens_servico": [
                {
                    "servico_id": str(uuid4()),
                    "descricao": "Troca de pastilhas",
                    "preco_unitario_centavos": 12000,
                }
            ],
            "itens_peca": [
                {
                    "peca_id": str(uuid4()),
                    "descricao": "Pastilha",
                    "quantidade": 1,
                    "preco_unitario_centavos": 18000,
                }
            ],
        },
    )
    with SessionLocal() as db:
        orq2 = OrquestradorSaga(db, environment="homolog")
        assert orq2.processar_evento_envelope(env_diag) == "PROCESSADO"
        # Reentrega do mesmo event_id após commit (janela commit/ACK) -> DUPLICADO sem novo comando
        assert orq2.processar_evento_envelope(env_diag) == "DUPLICADO"

        saga_db = db.query(SagaInstanceModel).filter_by(id=str(saga_id)).one()
        assert saga_db.estado == EstadoSaga.GERANDO_ORCAMENTO.value
        assert saga_db.version == 2
        assert (
            db.query(OutboxEventoModel)
            .filter_by(tipo_evento="GerarOrcamento.v1")
            .count()
            == 1
        )

    # Evento de rodada antiga (rodada=99) é ignorado sem regredir estado
    with SessionLocal() as db:
        orq3 = OrquestradorSaga(db, environment="homolog")
        orc_id = uuid4()
        env_velho = _envelope(
            event_type="OrcamentoGerado.v1",
            producer="oficina-billing",
            saga_id=saga_id,
            os_id=os_id,
            correlation_id=corr_id,
            causation_id=evt_diag_id,
            payload={
                "rodada": 99,
                "orcamento_id": str(orc_id),
                "versao": 1,
                "total_centavos": 30000,
                "moeda": "BRL",
            },
        )
        assert orq3.processar_evento_envelope(env_velho) == "IGNORADO_PRECONDICAO"

        # Continua fluxo feliz até CONCLUIDA
        for evt_type, prod, pay in [
            (
                "OrcamentoGerado.v1",
                "oficina-billing",
                {
                    "rodada": 1,
                    "orcamento_id": str(orc_id),
                    "versao": 1,
                    "total_centavos": 30000,
                    "moeda": "BRL",
                },
            ),
            (
                "OrcamentoAprovado.v1",
                "oficina-billing",
                {
                    "rodada": 1,
                    "orcamento_id": str(orc_id),
                    "versao": 1,
                    "cliente_id": str(cli_id),
                    "total_centavos": 30000,
                    "moeda": "BRL",
                },
            ),
            (
                "PecasReservadas.v1",
                "oficina-execucao",
                {"rodada": 1, "reserva_id": str(saga_id), "status": "RESERVADA"},
            ),
            (
                "CobrancaCriada.v1",
                "oficina-billing",
                {
                    "rodada": 1,
                    "orcamento_id": str(orc_id),
                    "pagamento_id": str(uuid4()),
                    "provider_order_id": "ORD1",
                    "qr_data": "QR",
                    "total_centavos": 30000,
                    "moeda": "BRL",
                },
            ),
        ]:
            assert (
                orq3.processar_evento_envelope(
                    _envelope(
                        event_type=evt_type,
                        producer=prod,
                        saga_id=saga_id,
                        os_id=os_id,
                        correlation_id=corr_id,
                        causation_id=evt_diag_id,
                        payload=pay,
                    )
                )
                == "PROCESSADO"
            )

        pag_id = UUID(
            db.query(SagaInstanceModel).filter_by(id=str(saga_id)).one().pagamento_id
        )
        for evt_type, prod, pay in [
            (
                "PagamentoConfirmado.v1",
                "oficina-billing",
                {
                    "orcamento_id": str(orc_id),
                    "pagamento_id": str(pag_id),
                    "provider_order_id": "ORD1",
                    "total_centavos": 30000,
                    "moeda": "BRL",
                    "orcamento_versao": 1,
                },
            ),
            (
                "ExecucaoEnfileirada.v1",
                "oficina-execucao",
                {
                    "rodada": 1,
                    "execucao_id": f"{os_id}_1",
                    "reserva_id": str(saga_id),
                    "status": "AGUARDANDO_EXECUCAO",
                },
            ),
            (
                "ExecucaoIniciada.v1",
                "oficina-execucao",
                {
                    "rodada": 1,
                    "execucao_id": f"{os_id}_1",
                    "reserva_consumida": True,
                },
            ),
            (
                "ExecucaoConcluida.v1",
                "oficina-execucao",
                {
                    "rodada": 1,
                    "execucao_id": f"{os_id}_1",
                    "concluida_em": datetime.now(timezone.utc).isoformat(),
                },
            ),
        ]:
            assert (
                orq3.processar_evento_envelope(
                    _envelope(
                        event_type=evt_type,
                        producer=prod,
                        saga_id=saga_id,
                        os_id=os_id,
                        correlation_id=corr_id,
                        causation_id=evt_diag_id,
                        payload=pay,
                    )
                )
                == "PROCESSADO"
            )

        saga_final = db.query(SagaInstanceModel).filter_by(id=str(saga_id)).one()
        os_final = db.query(OrdemDeServicoModel).filter_by(id=os_id).one()
        assert saga_final.estado == EstadoSaga.CONCLUIDA.value
        assert os_final.status == StatusOS.FINALIZADA


def test_barreira_cancelamento_obrigatoria_e_reparo_iniciado(tmp_path):
    SessionLocal = _criar_sessao_sqlite(tmp_path)
    with SessionLocal() as db:
        cli_id, vei_id, os_id = _seed_os(db)
        orq = OrquestradorSaga(db, environment="homolog")
        saga = orq.iniciar_saga_abertura(
            os_id=os_id,
            cliente_id=cli_id,
            veiculo_id=vei_id,
            descricao_problema="Barulho",
        )
        saga.estado = EstadoSaga.ENFILEIRANDO.value
        saga.orcamento_id = str(uuid4())
        saga.orcamento_versao = 1
        saga.pagamento_id = str(uuid4())
        saga.total_centavos = 15000
        db.commit()

        saga_id = UUID(saga.id)
        corr_id = UUID(saga.correlation_id)

        # ExecucaoRejeitada -> entra na barreira COMPENSANDO_BLOQUEIO_EXECUCAO e emite CancelarExecucao.v1
        assert (
            orq.processar_evento_envelope(
                _envelope(
                    event_type="ExecucaoRejeitada.v1",
                    producer="oficina-execucao",
                    saga_id=saga_id,
                    os_id=os_id,
                    correlation_id=corr_id,
                    causation_id=saga_id,
                    payload={
                        "rodada": 1,
                        "reserva_id": str(saga_id),
                        "motivo": "FILA_INDISPONIVEL",
                    },
                )
            )
            == "PROCESSADO"
        )
        assert (
            db.query(OutboxEventoModel)
            .filter_by(tipo_evento="EstornarPagamento.v1")
            .count()
            == 0
        )

        # Só após ExecucaoCancelada.v1 emite EstornarPagamento.v1 e LiberarReserva.v1
        evt_barreira = uuid4()
        assert (
            orq.processar_evento_envelope(
                _envelope(
                    event_id=evt_barreira,
                    event_type="ExecucaoCancelada.v1",
                    producer="oficina-execucao",
                    saga_id=saga_id,
                    os_id=os_id,
                    correlation_id=corr_id,
                    causation_id=saga_id,
                    payload={
                        "rodada": 1,
                        "compensacao_id": saga.compensacao_id,
                        "resultado": "CANCELADA",
                        "motivo": "FALHA_ENFILEIRAMENTO",
                        "execucao_id": None,
                        "tombstone_persistido": True,
                    },
                )
            )
            == "PROCESSADO"
        )
        assert (
            db.query(OutboxEventoModel)
            .filter_by(tipo_evento="EstornarPagamento.v1")
            .count()
            == 1
        )
        assert (
            db.query(OutboxEventoModel)
            .filter_by(tipo_evento="LiberarReserva.v1")
            .count()
            == 1
        )


def test_worker_janela_commit_publish_retry_e_commit_ack(tmp_path):
    SessionLocal = _criar_sessao_sqlite(tmp_path)
    with SessionLocal() as db:
        cli_id, vei_id, os_id = _seed_os(db)
        orq = OrquestradorSaga(db, environment="homolog")
        saga = orq.iniciar_saga_abertura(
            os_id=os_id,
            cliente_id=cli_id,
            veiculo_id=vei_id,
            descricao_problema="Freio",
        )
        db.commit()
        saga_id = UUID(saga.id)
        corr_id = UUID(saga.correlation_id)

        # 1. Falha no broker durante publish -> fica em FALHA_AGENDADA (reprocessável, nunca abandonado)
        pub_falha = MagicMock()
        pub_falha.topic_path.return_value = "projects/p/topics/t"
        fut_err = MagicMock()
        fut_err.result.side_effect = RuntimeError("Broker indisponível")
        pub_falha.publish.return_value = fut_err

        assert publicar_lote_outbox(db, pub_falha, project_id="p") == 0
        ev = db.query(OutboxEventoModel).one()
        assert ev.status == "FALHA_AGENDADA"
        assert ev.tentativas == 1

        # 2. Broker recupera e tempo vence -> republica o mesmo event_id e marca PROCESSADO
        ev.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        pub_ok = MagicMock()
        pub_ok.topic_path.return_value = "projects/p/topics/t"
        fut_ok = MagicMock()
        fut_ok.result.return_value = "msg-1"
        pub_ok.publish.return_value = fut_ok

        assert publicar_lote_outbox(db, pub_ok, project_id="p") == 1
        db.refresh(ev)
        assert ev.status == "PROCESSADO"

    # 3. Janela commit/ACK no consumidor Pub/Sub: reentrega da mesma mensagem -> ACK idempotente sem duplicar efeitos
    env_diag = _envelope(
        event_id=uuid4(),
        event_type="DiagnosticoConcluido.v1",
        producer="oficina-execucao",
        saga_id=saga_id,
        os_id=os_id,
        correlation_id=corr_id,
        causation_id=saga_id,
        payload={
            "rodada": 1,
            "diagnostico_id": f"{os_id}_1",
            "laudo": "OK",
            "itens_servico": [
                {
                    "servico_id": str(uuid4()),
                    "descricao": "Rev",
                    "preco_unitario_centavos": 10000,
                }
            ],
            "itens_peca": [],
        },
    )
    msg = SimpleNamespace(
        ack_id="ack-1",
        message=SimpleNamespace(
            data=json.dumps(env_diag).encode("utf-8"),
            attributes={"traceparent": "00-abc-def-01"},
        ),
    )
    sub = MagicMock()
    sub.subscription_path.return_value = "projects/p/subscriptions/s"
    sub.pull.return_value = SimpleNamespace(received_messages=[msg])

    assert (
        consumir_mensagens_pull(
            SessionLocal, sub, project_id="p", subscription_name="s"
        )
        == 1
    )
    # Reentrega simulada porque ACK anterior não chegou ao broker
    assert (
        consumir_mensagens_pull(
            SessionLocal, sub, project_id="p", subscription_name="s"
        )
        == 1
    )
    assert sub.acknowledge.call_count == 2
    with SessionLocal() as db:
        assert (
            db.query(OutboxEventoModel)
            .filter_by(tipo_evento="GerarOrcamento.v1")
            .count()
            == 1
        )


def test_rotas_legadas_bloqueadas_com_410_quando_distribuido(tmp_path):
    db_file = tmp_path / "p4_410.sqlite"
    cfg = Configuracoes(
        database_url=f"sqlite:///{db_file}",
        enable_legacy_monolith_domains=False,
    )
    app = criar_app(cfg)
    Base.metadata.create_all(bind=app.state.container.engine)
    cli = TestClient(app)

    from src.identidade.aplicacao.casos_de_uso import CriarUsuario
    from src.identidade.dominio.entidades import PerfilUsuario
    from src.identidade.infraestrutura.bcrypt_provider import BcryptHashProvider
    from src.identidade.infraestrutura.repositorios import UsuarioRepositorioImpl
    from src.shared.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    with app.state.container.SessionLocal() as db:
        CriarUsuario(
            UsuarioRepositorioImpl(db),
            BcryptHashProvider(),
            uow=SQLAlchemyUnitOfWork(db),
        ).executar("admin@oficina.com", "senha123", PerfilUsuario.ADMIN)

    tok = cli.post(
        "/auth/login", json={"email": "admin@oficina.com", "senha": "senha123"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {tok}"}

    os_fake_id = uuid4()
    assert (
        cli.post(
            f"/ordens-de-servico/{os_fake_id}/gerar-orcamento", headers=headers
        ).status_code
        == 410
    )
    assert (
        cli.post(
            f"/ordens-de-servico/{os_fake_id}/aprovacao",
            json={"aprovado": True},
            headers=headers,
        ).status_code
        == 410
    )
    assert (
        cli.post(
            f"/ordens-de-servico/{os_fake_id}/iniciar-diagnostico", headers=headers
        ).status_code
        == 410
    )
    assert (
        cli.post(
            f"/ordens-de-servico/{os_fake_id}/executar-servico/{uuid4()}",
            headers=headers,
        ).status_code
        == 410
    )
