"""
Teste E2E real da Etapa P4 pelas três APIs (oficina-os:8000, oficina-billing:8001,
oficina-execucao:8002), bancos PostgreSQL isolados, Firestore Emulator e Pub/Sub Emulator,
com provedor financeiro fake (FakeMercadoPagoOrdersProvider) via porta ProvedorPagamento.
"""

import time

import httpx
from sqlalchemy import create_engine

OS_URL = "http://localhost:8000"
BILLING_URL = "http://localhost:8001"
EXEC_URL = "http://localhost:8002"
OS_DB_URL = "postgresql+pg8000://oficina_os_user:oficina_os_pass@localhost:5432/oficina_os_homolog"


def _esperar_condicao(fn, *, timeout_s: float = 40.0, descricao: str = "condição"):
    deadline = time.time() + timeout_s
    ultimo_erro = None
    while time.time() < deadline:
        try:
            res = fn()
            if res:
                return res
        except Exception as exc:  # noqa: BLE001
            ultimo_erro = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timeout aguardando {descricao}: {ultimo_erro}")


def _garantir_usuario_admin() -> None:
    from src.identidade.aplicacao.casos_de_uso import CriarUsuario
    from src.identidade.dominio.entidades import PerfilUsuario
    from src.identidade.infraestrutura.bcrypt_provider import BcryptHashProvider
    from src.identidade.infraestrutura.repositorios import UsuarioRepositorioImpl
    from src.shared.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(OS_DB_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as db:
        repo = UsuarioRepositorioImpl(db)
        if not repo.buscar_por_email("admin.e2e@oficina.com"):
            CriarUsuario(
                repo, BcryptHashProvider(), uow=SQLAlchemyUnitOfWork(db)
            ).executar("admin.e2e@oficina.com", "senha123", PerfilUsuario.ADMIN)


def main() -> int:
    _esperar_condicao(
        lambda: httpx.get(f"{OS_URL}/health/ready", timeout=2.0).status_code == 200
        and httpx.get(f"{BILLING_URL}/health/ready", timeout=2.0).status_code == 200
        and httpx.get(f"{EXEC_URL}/health/ready", timeout=2.0).status_code == 200,
        descricao="readiness dos 3 serviços",
    )
    _garantir_usuario_admin()

    with httpx.Client(timeout=10.0) as client:
        # 1. Login ADMIN -> Token RS256 validado pelos 3 serviços via /.well-known/admin-jwks.json
        r_login = client.post(
            f"{OS_URL}/auth/login",
            json={"email": "admin.e2e@oficina.com", "senha": "senha123"},
        )
        assert r_login.status_code == 200, r_login.text
        headers = {"Authorization": f"Bearer {r_login.json()['token']}"}

        # Confirma que OS Service não expõe rotas legadas de catálogo/estoque (404) ou orçamento/execução (410)
        assert client.get(f"{OS_URL}/servicos", headers=headers).status_code == 404
        assert client.get(f"{OS_URL}/pecas", headers=headers).status_code == 404

        # 2. Cadastra serviço e peça em oficina-execucao (Firestore)
        r_srv = client.post(
            f"{EXEC_URL}/v1/servicos",
            headers=headers,
            json={
                "nome": "Troca de pastilha E2E",
                "descricao": "Serviço completo",
                "preco_base": "120.00",
                "tempo_estimado_minutos": 60,
            },
        )
        assert r_srv.status_code == 201, r_srv.text
        servico_id = r_srv.json()["id"]

        r_pec = client.post(
            f"{EXEC_URL}/v1/pecas",
            headers=headers,
            json={
                "nome": "Pastilha Cerâmica E2E",
                "codigo": f"E2E-{int(time.time())}",
                "preco_unitario": "90.00",
                "quantidade_disponivel": 10,
                "quantidade_minima_alerta": 2,
            },
        )
        assert r_pec.status_code == 201, r_pec.text
        peca_id = r_pec.json()["id"]

        # 3. Cadastra cliente e veículo no OS Service
        r_cli = client.post(
            f"{OS_URL}/clientes",
            headers=headers,
            json={
                "nome": "Cliente E2E P4",
                "email": "e2e@oficina.com",
                "telefone": "11999990000",
                "cpf": "52998224725",
            },
        )
        if r_cli.status_code == 201:
            cliente_id = r_cli.json()["id"]
        else:
            cliente_id = client.get(f"{OS_URL}/clientes", headers=headers).json()[0][
                "id"
            ]

        placa = f"E{int(time.time()) % 90 + 10}A1B23"[:7]
        # Garante formato Mercosul ABC1D23
        placa = "EEA1P40"
        r_vei = client.post(
            f"{OS_URL}/veiculos",
            headers=headers,
            json={
                "cliente_id": cliente_id,
                "placa": placa,
                "marca": "Toyota",
                "modelo": "Corolla",
                "ano": 2023,
            },
        )
        assert r_vei.status_code in {201, 409}, r_vei.text

        # 4. Abertura da OS via POST /v1/ordens-servico -> 202 Accepted
        r_os = client.post(
            f"{OS_URL}/v1/ordens-servico",
            headers=headers,
            json={
                "cliente_documento": "52998224725",
                "veiculo_placa": placa,
                "descricao_problema": "Freio rangendo no E2E P4",
            },
        )
        assert r_os.status_code == 202, r_os.text
        os_id = r_os.json()["os_id"]
        saga_id = r_os.json()["saga_id"]
        exec_id = f"{os_id}_1"

        # 5. Diagnóstico em oficina-execucao -> DiagnosticoConcluido.v1 -> Billing gera orçamento -> OS AGUARDANDO_APROVACAO
        r_diag = client.post(
            f"{EXEC_URL}/v1/execucoes/{exec_id}/diagnostico",
            headers=headers,
            json={
                "os_id": os_id,
                "saga_id": saga_id,
                "rodada": 1,
                "laudo": "Trocar pastilhas dianteiras",
                "itens_servico": [
                    {
                        "servico_id": servico_id,
                        "descricao": "Troca de pastilha E2E",
                        "preco_unitario_centavos": 12000,
                    }
                ],
                "itens_peca": [
                    {
                        "peca_id": peca_id,
                        "descricao": "Pastilha Cerâmica E2E",
                        "quantidade": 2,
                        "preco_unitario_centavos": 9000,
                    }
                ],
            },
        )
        assert r_diag.status_code == 201, r_diag.text

        saga_info = _esperar_condicao(
            lambda: (
                lambda r: (
                    r.json()
                    if r.status_code == 200
                    and r.json()["estado"] == "AGUARDANDO_APROVACAO"
                    else None
                )
            )(client.get(f"{OS_URL}/v1/ordens-servico/{os_id}/saga", headers=headers)),
            descricao="Saga em AGUARDANDO_APROVACAO",
        )
        orc_id = saga_info["orcamento_id"]
        assert saga_info["total_centavos"] == 30000

        # 6. Aprovação em oficina-billing -> OrcamentoAprovado.v1 -> Execução reserva peça -> Billing cria cobrança QR
        r_aprov = client.post(
            f"{BILLING_URL}/v1/orcamentos/{orc_id}/decisao",
            headers=headers,
            json={"aprovado": True, "versao": 1},
        )
        assert r_aprov.status_code == 202, r_aprov.text

        _esperar_condicao(
            lambda: (
                lambda r: (
                    r.json()
                    if r.status_code == 200
                    and r.json()["estado"] == "AGUARDANDO_PAGAMENTO"
                    else None
                )
            )(client.get(f"{OS_URL}/v1/ordens-servico/{os_id}/saga", headers=headers)),
            descricao="Saga em AGUARDANDO_PAGAMENTO",
        )

        # Confirma estoque reservado (10 -> 8) no Firestore
        peca_apos_res = client.get(
            f"{EXEC_URL}/v1/pecas/{peca_id}", headers=headers
        ).json()
        assert peca_apos_res["quantidade_disponivel"] == 8

        # 7. Simula pagamento no FakeMercadoPagoOrdersProvider e dispara webhook assinado
        pag_info = client.get(
            f"{BILLING_URL}/v1/pagamentos/por-os/{os_id}", headers=headers
        ).json()
        provider_order_id = pag_info["provider_order_id"]
        sim = client.post(
            f"{BILLING_URL}/internal/fake-mp/{provider_order_id}/pagar", headers=headers
        ).json()
        r_wh = client.post(
            f"{BILLING_URL}/webhooks/mercadopago",
            headers=sim["headers"],
            json=sim["body"],
        )
        assert r_wh.status_code == 200, r_wh.text

        # Aguarda ExecucaoEnfileirada.v1 -> OS AGUARDANDO_EXECUCAO / Saga EM_EXECUCAO
        _esperar_condicao(
            lambda: (
                lambda r: (
                    r.json()
                    if r.status_code == 200 and r.json()["estado"] == "EM_EXECUCAO"
                    else None
                )
            )(client.get(f"{OS_URL}/v1/ordens-servico/{os_id}/saga", headers=headers)),
            descricao="Saga em EM_EXECUCAO",
        )

        # 8. Mecânico inicia e conclui reparo -> ExecucaoIniciada.v1 / ExecucaoConcluida.v1 -> Saga CONCLUIDA / OS FINALIZADA
        assert (
            client.post(
                f"{EXEC_URL}/v1/execucoes/{exec_id}/iniciar", headers=headers
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"{EXEC_URL}/v1/execucoes/{exec_id}/concluir", headers=headers
            ).status_code
            == 200
        )

        saga_fim = _esperar_condicao(
            lambda: (
                lambda r: (
                    r.json()
                    if r.status_code == 200 and r.json()["estado"] == "CONCLUIDA"
                    else None
                )
            )(client.get(f"{OS_URL}/v1/ordens-servico/{os_id}/saga", headers=headers)),
            descricao="Saga em CONCLUIDA",
        )

        # 9. Entrega no OS Service -> ENTREGUE
        r_ent = client.post(
            f"{OS_URL}/v1/ordens-servico/{os_id}/entrega", headers=headers
        )
        assert r_ent.status_code == 200, r_ent.text
        assert r_ent.json()["status"] == "ENTREGUE"

    print(
        "E2E_P4_OK",
        {
            "os_id": os_id,
            "saga_id": saga_id,
            "orcamento_id": orc_id,
            "provider_order_id": provider_order_id,
            "estado_saga_final": saga_fim["estado"],
            "status_os_final": r_ent.json()["status"],
            "estoque_restante": peca_apos_res["quantidade_disponivel"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
