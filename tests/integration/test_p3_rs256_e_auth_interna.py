import json

from fastapi.testclient import TestClient
import jwt

from src.config import Configuracoes
from src.main import criar_app
from src.shared.banco import Base


def test_admin_jwks_rs256_e_validacao_distribuida(client, headers_admin, app_test):
    resp_jwks = client.get("/.well-known/admin-jwks.json")
    assert resp_jwks.status_code == 200
    keys = resp_jwks.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["alg"] == "RS256"
    assert keys[0]["kty"] == "RSA"

    token = headers_admin["Authorization"].split(" ", 1)[1]
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "RS256"
    assert header["kid"] == keys[0]["kid"]

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(keys[0]))
    decoded = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience=app_test.state.container.config.jwt_audience,
        issuer=app_test.state.container.config.jwt_admin_issuer,
    )
    assert decoded["actor_type"] == "FUNCIONARIO"
    assert decoded["perfil"] == "ADMIN"


def test_internal_clientes_autenticacao_oidc_e_abertura_os_v1(tmp_path):
    db_file = tmp_path / "p3_internal.sqlite"
    test_tokens = {
        "oidc-valido": {
            "iss": "https://accounts.google.com",
            "aud": "https://api.oficina.internal/internal/clientes/autenticacao",
            "email": "auth-sa@fiap-project-514922.iam.gserviceaccount.com",
            "email_verified": True,
        },
        "oidc-aud-errada": {
            "iss": "https://accounts.google.com",
            "aud": "https://outro-servico.internal",
            "email": "auth-sa@fiap-project-514922.iam.gserviceaccount.com",
            "email_verified": True,
        },
        "oidc-sa-nao-autorizada": {
            "iss": "https://accounts.google.com",
            "aud": "https://api.oficina.internal/internal/clientes/autenticacao",
            "email": "intruso@fiap-project-514922.iam.gserviceaccount.com",
            "email_verified": True,
        },
    }
    cfg = Configuracoes(
        database_url=f"sqlite:///{db_file}",
        internal_auth_allowed_service_accounts="auth-sa@fiap-project-514922.iam.gserviceaccount.com",
        internal_auth_test_tokens_json=json.dumps(test_tokens),
        enable_legacy_monolith_domains=False,
    )
    app = criar_app(cfg)
    Base.metadata.create_all(bind=app.state.container.engine)
    cli = TestClient(app)

    # Com enable_legacy_monolith_domains=False, /servicos e /pecas não existem no OS
    assert cli.get("/servicos").status_code == 404
    assert cli.get("/pecas").status_code == 404

    # Cria usuário admin para cadastrar cliente/veículo e abrir OS v1
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

    c_resp = cli.post(
        "/clientes",
        json={
            "nome": "Maria Souza",
            "email": "maria@email.com",
            "telefone": "11999990000",
            "cpf": "52998224725",
        },
        headers=headers,
    )
    assert c_resp.status_code == 201
    cliente_id = c_resp.json()["id"]

    cli.post(
        "/veiculos",
        json={
            "cliente_id": cliente_id,
            "placa": "ABC1D23",
            "marca": "VW",
            "modelo": "Golf",
            "ano": 2022,
        },
        headers=headers,
    )

    # Sem OIDC -> 401
    assert (
        cli.post(
            "/internal/clientes/autenticacao", json={"cpf": "52998224725"}
        ).status_code
        == 401
    )

    # Audience errada -> 403
    assert (
        cli.post(
            "/internal/clientes/autenticacao",
            json={"cpf": "52998224725"},
            headers={"Authorization": "Bearer oidc-aud-errada"},
        ).status_code
        == 403
    )

    # SA não autorizada -> 403
    assert (
        cli.post(
            "/internal/clientes/autenticacao",
            json={"cpf": "52998224725"},
            headers={"Authorization": "Bearer oidc-sa-nao-autorizada"},
        ).status_code
        == 403
    )

    # OIDC válido -> 200 com dados do cliente
    r_ok = cli.post(
        "/internal/clientes/autenticacao",
        json={"cpf": "529.982.247-25"},
        headers={"Authorization": "Bearer oidc-valido"},
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["id"] == cliente_id
    assert r_ok.json()["status"] == "ATIVO"

    # Abertura canônica v1 da OS (202 Accepted com saga_id e Location)
    r_os = cli.post(
        "/v1/ordens-servico",
        json={
            "cliente_documento": "52998224725",
            "veiculo_placa": "ABC1D23",
            "descricao_problema": "Revisão periódica",
        },
        headers=headers,
    )
    assert r_os.status_code == 202
    assert r_os.json()["status"] == "RECEBIDA"
    assert "saga_id" in r_os.json()
    assert r_os.headers["location"].startswith("/v1/ordens-servico/")
