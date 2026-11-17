from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
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
from src.shared.outbox import InboxEventoModel, OutboxEventoModel
from src.worker import consumir_mensagens_pull, publicar_lote_outbox


def _setup_db(tmp_path):
    eng = create_engine(
        f"sqlite:///{tmp_path / 'janelas.db'}",
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
                nome="Cliente Janelas",
                cpf=CPF("52998224725"),
                email="janelas@teste.com",
                telefone="11999999999",
            )
        )
        db.add(
            VeiculoModel(
                id=vei_id,
                cliente_id=cli_id,
                placa="JNL1A23",
                marca="VW",
                modelo="Polo",
                ano=2024,
            )
        )
        db.add(
            OrdemDeServicoModel(
                id=os_id,
                cliente_id=cli_id,
                veiculo_id=vei_id,
                descricao_problema="Teste janelas crash",
                status=StatusOS.RECEBIDA,
                criada_em=datetime.now(timezone.utc),
                atualizada_em=datetime.now(timezone.utc),
            )
        )
        db.commit()
    return Session, cli_id, vei_id, os_id


def test_janela_commit_antes_publicacao_e_publicacao_antes_marcar_outbox(
    tmp_path,
) -> None:
    Session, cli_id, vei_id, os_id = _setup_db(tmp_path)

    with Session() as db:
        saga = OrquestradorSaga(db).iniciar_saga_abertura(
            os_id=os_id,
            cliente_id=cli_id,
            veiculo_id=vei_id,
            descricao_problema="Teste janela 1",
        )
        db.commit()
        # Janela 1: commit feito, worker ainda não publicou -> status PENDENTE
        out = db.query(OutboxEventoModel).one()
        assert out.status == "PENDENTE"
        saga_id = saga.id

    # Janela 2: publisher publica no Pub/Sub, mas falha antes de marcar PROCESSADO
    class PublisherFalhaAposEnvio:
        def __init__(self) -> None:
            self.publicacoes: list[bytes] = []

        def topic_path(self, project_id: str, topic_name: str) -> str:
            return f"projects/{project_id}/topics/{topic_name}"

        def publish(self, topic_path: str, data: bytes, **attrs):
            self.publicacoes.append(data)
            fut = MagicMock()
            fut.result.side_effect = TimeoutError("crash apos envio ao broker")
            return fut

    pub_falha = PublisherFalhaAposEnvio()
    with Session() as db:
        publicar_lote_outbox(db, pub_falha, project_id="fiap-project-514922")
        out = db.query(OutboxEventoModel).one()
        assert len(pub_falha.publicacoes) == 1
        assert out.status == "FALHA_AGENDADA"
        # Libera next_attempt_at para simular retry imediato após recuperação
        out.next_attempt_at = datetime.now(timezone.utc)
        db.commit()

    # Worker recupera e publica novamente; marca PROCESSADO
    pub_ok = MagicMock()
    pub_ok.topic_path.side_effect = lambda p, t: f"projects/{p}/topics/{t}"
    pub_ok.publish.return_value.result.return_value = "msg-ok"
    with Session() as db:
        qtd = publicar_lote_outbox(db, pub_ok, project_id="fiap-project-514922")
        assert qtd == 1
        out = db.query(OutboxEventoModel).one()
        assert out.status == "PROCESSADO"

    # Consumidor recebe as duas cópias (duplicadas pelo retry da Janela 2) e deduplica pela Inbox
    payload_evt = {
        "event_id": str(uuid4()),
        "event_type": "DiagnosticoConcluido.v1",
        "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "oficina-execucao",
        "saga_id": saga_id,
        "os_id": str(os_id),
        "correlation_id": saga_id,
        "causation_id": saga_id,
        "aggregate_version": 1,
        "payload": {
            "rodada": 1,
            "diagnostico_id": str(uuid4()),
            "laudo": "Pastilhas",
            "itens_servico": [
                {
                    "servico_id": str(uuid4()),
                    "descricao": "Troca",
                    "preco_unitario_centavos": 10000,
                }
            ],
            "itens_peca": [],
        },
    }
    with Session() as db:
        assert (
            OrquestradorSaga(db).processar_evento_envelope(payload_evt) == "PROCESSADO"
        )
        assert (
            OrquestradorSaga(db).processar_evento_envelope(payload_evt) == "DUPLICADO"
        )
        assert db.query(InboxEventoModel).count() == 1


def test_janela_commit_consumidor_antes_ack_pubsub(tmp_path) -> None:
    Session, cli_id, vei_id, os_id = _setup_db(tmp_path)
    with Session() as db:
        saga = OrquestradorSaga(db).iniciar_saga_abertura(
            os_id=os_id,
            cliente_id=cli_id,
            veiculo_id=vei_id,
            descricao_problema="Teste janela 3",
        )
        db.commit()
        saga_id = saga.id

    envelope = {
        "event_id": str(uuid4()),
        "event_type": "DiagnosticoConcluido.v1",
        "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "oficina-execucao",
        "saga_id": saga_id,
        "os_id": str(os_id),
        "correlation_id": saga_id,
        "causation_id": saga_id,
        "aggregate_version": 1,
        "payload": {
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
    }
    rec = SimpleNamespace(
        ack_id="ack-1",
        message=SimpleNamespace(
            data=json.dumps(envelope).encode("utf-8"),
            attributes={},
        ),
    )

    subscriber = MagicMock()
    subscriber.subscription_path.return_value = "projects/p/subscriptions/s"
    subscriber.pull.return_value = SimpleNamespace(received_messages=[rec])
    # 1ª tentativa: consumidor faz commit no DB, mas falha exatamente no acknowledge()
    subscriber.acknowledge.side_effect = [RuntimeError("queda antes do ACK"), None]

    consumir_mensagens_pull(Session, subscriber, project_id="p", subscription_name="s")
    # 2ª tentativa (reentrega do Pub/Sub): Inbox deduplica e ACK é enviado com sucesso
    consumir_mensagens_pull(Session, subscriber, project_id="p", subscription_name="s")

    with Session() as db:
        saga_final = db.query(SagaInstanceModel).filter_by(id=saga_id).one()
        assert saga_final.estado == EstadoSaga.GERANDO_ORCAMENTO.value
        assert db.query(InboxEventoModel).count() == 1
        assert subscriber.acknowledge.call_count == 2
