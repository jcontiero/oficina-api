from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.atendimento.dominio.value_objects import CPF, StatusOS
from src.atendimento.infraestrutura.modelos import (
    ClienteModel,
    OrdemDeServicoModel,
    VeiculoModel,
)
from src.config import Configuracoes
from src.container import _get_session
from src.identidade.dominio.entidades import ActorType, PerfilUsuario, Principal
from src.main import criar_app
from src.saga.aplicacao.orquestrador import OrquestradorSaga
from src.saga.dominio.estados import EstadoSaga
from src.saga.infraestrutura.modelos import SagaInstanceModel
from src.shared.banco import Base
from src.shared.dependencias import get_usuario_atual


def _setup_app(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'p6_rotas.db'}"
    eng = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    cfg = Configuracoes(
        database_url=db_url,
        environment="homolog",
        allow_ephemeral_admin_jwt_key=True,
        dd_trace_enabled=False,
        enable_legacy_monolith_domains=False,
        secret_key="segredo-teste-p6-com-mais-de-32-bytes",
    )
    app = criar_app(cfg)

    def _override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[_get_session] = _override_db
    return app, Session


def _criar_os_com_saga(
    Session,
    *,
    falha_estorno: bool = False,
    cpf_num: str = "52998224725",
    placa: str = "P6R1A23",
):
    with Session() as db:
        cli_id = uuid4()
        vei_id = uuid4()
        os_id = uuid4()
        db.add(
            ClienteModel(
                id=cli_id,
                nome="Cliente Rotas P6",
                cpf=CPF(cpf_num),
                email=f"rotas.{cpf_num}@teste.com",
                telefone="11999999999",
            )
        )
        db.add(
            VeiculoModel(
                id=vei_id,
                cliente_id=cli_id,
                placa=placa,
                marca="Toyota",
                modelo="Yaris",
                ano=2024,
            )
        )
        db.add(
            OrdemDeServicoModel(
                id=os_id,
                cliente_id=cli_id,
                veiculo_id=vei_id,
                descricao_problema="Teste rotas P6",
                status=StatusOS.RECEBIDA,
                criada_em=datetime.now(timezone.utc),
                atualizada_em=datetime.now(timezone.utc),
            )
        )
        db.commit()
        saga = OrquestradorSaga(db).iniciar_saga_abertura(
            os_id=os_id,
            cliente_id=cli_id,
            veiculo_id=vei_id,
            descricao_problema="Teste rotas P6",
        )
        if falha_estorno:
            saga.estado = EstadoSaga.COMPENSANDO_EFEITOS.value
            saga.compensacao_financeira_status = "FALHA_PENDENTE"
            saga.execucao_cancelada_event_id = str(uuid4())
            saga.pagamento_id = str(uuid4())
            saga.total_centavos = 15000
        db.commit()
        return os_id, saga.id


def test_autorizacao_e_fluxo_cancelar_e_reprocessar_estorno(tmp_path) -> None:
    app, Session = _setup_app(tmp_path)
    client = TestClient(app)
    os_id, _ = _criar_os_com_saga(Session, falha_estorno=False)

    # Sem token -> 401
    assert client.post(f"/v1/ordens-servico/{os_id}/cancelar").status_code == 401
    assert (
        client.post(f"/v1/ordens-servico/{os_id}/saga/reprocessar-estorno").status_code
        == 401
    )

    # Mecânico não pode acionar reprocessamento administrativo de estorno -> 403
    app.dependency_overrides[get_usuario_atual] = lambda: Principal(
        id=uuid4(), actor_type=ActorType.FUNCIONARIO, perfil=PerfilUsuario.MECANICO
    )
    assert (
        client.post(f"/v1/ordens-servico/{os_id}/saga/reprocessar-estorno").status_code
        == 403
    )

    # ADMIN autenticado
    app.dependency_overrides[get_usuario_atual] = lambda: Principal(
        id=uuid4(), actor_type=ActorType.FUNCIONARIO, perfil=PerfilUsuario.ADMIN
    )

    # OS inexistente -> 409
    assert client.post(f"/v1/ordens-servico/{uuid4()}/cancelar").status_code == 409

    # Reprocessar estorno sem falha pendente -> 409
    assert (
        client.post(f"/v1/ordens-servico/{os_id}/saga/reprocessar-estorno").status_code
        == 409
    )

    # Cancelamento válido -> 202
    r_can = client.post(f"/v1/ordens-servico/{os_id}/cancelar")
    assert r_can.status_code == 202
    assert r_can.json()["estado"] == EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO.value

    # GET saga inclui efeitos_esperados e efeitos_confirmados
    r_saga = client.get(f"/v1/ordens-servico/{os_id}/saga")
    assert r_saga.status_code == 200
    assert "efeitos_esperados" in r_saga.json()
    assert "efeitos_confirmados" in r_saga.json()

    # OS com FALHA_PENDENTE -> ADMIN consegue reprocessar (202)
    os_id_2, _ = _criar_os_com_saga(
        Session, falha_estorno=True, cpf_num="11144477735", placa="P6R2B45"
    )
    r_rep = client.post(f"/v1/ordens-servico/{os_id_2}/saga/reprocessar-estorno")
    assert r_rep.status_code == 202
    assert r_rep.json()["compensacao_financeira_status"] == "PENDENTE"
    with Session() as db:
        s2 = db.query(SagaInstanceModel).filter_by(os_id=str(os_id_2)).one()
        assert s2.compensacao_financeira_status == "PENDENTE"
