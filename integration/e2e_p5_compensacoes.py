import subprocess
import time

import httpx
from sqlalchemy import create_engine, text

from integration.e2e_p4_fluxo_feliz import (
    BILLING_URL,
    EXEC_URL,
    OS_URL,
    _esperar_condicao,
    _garantir_usuario_admin,
)

DB_OS = "postgresql+pg8000://oficina_os_user:oficina_os_pass@localhost:5432/oficina_os_homolog"


def main() -> int:
    _garantir_usuario_admin()
    with httpx.Client(timeout=15.0) as client:
        r_login = client.post(
            f"{OS_URL}/auth/login",
            json={"email": "admin.e2e@oficina.com", "senha": "senha123"},
        )
        assert r_login.status_code == 200, r_login.text
        headers = {"Authorization": f"Bearer {r_login.json()['token']}"}

        # Cria serviço e peça (estoque = 10)
        srv_id = client.post(
            f"{EXEC_URL}/v1/servicos",
            headers=headers,
            json={
                "nome": "Alinhamento P5",
                "descricao": "Alinhamento completo",
                "preco_base": "100.00",
                "tempo_estimado_minutos": 45,
            },
        ).json()["id"]
        peca_id = client.post(
            f"{EXEC_URL}/v1/pecas",
            headers=headers,
            json={
                "nome": "Filtro P5",
                "codigo": f"FIL-P5-{int(time.time())}",
                "preco_unitario": "50.00",
                "quantidade_disponivel": 10,
                "quantidade_minima_alerta": 2,
            },
        ).json()["id"]

        r_cli = client.post(
            f"{OS_URL}/clientes",
            headers=headers,
            json={
                "nome": "Cliente E2E P5",
                "cpf": "52998224725",
                "email": "cliente.p5@oficina.com",
                "telefone": "11988887777",
            },
        )
        if r_cli.status_code == 201:
            cli_id = r_cli.json()["id"]
        else:
            cli_id = client.get(f"{OS_URL}/clientes", headers=headers).json()[0]["id"]

        ts = int(time.time())
        placa = f"P{chr(65 + ts % 26)}{chr(65 + (ts // 26) % 26)}5A40"
        r_vei = client.post(
            f"{OS_URL}/veiculos",
            headers=headers,
            json={
                "cliente_id": cli_id,
                "placa": placa,
                "marca": "Fiat",
                "modelo": "Pulse",
                "ano": 2024,
            },
        )
        assert r_vei.status_code in {201, 409}, r_vei.text

        # 1. Abre OS (Saga em DIAGNOSTICO)
        r_os = client.post(
            f"{OS_URL}/v1/ordens-servico",
            headers=headers,
            json={
                "cliente_documento": "52998224725",
                "veiculo_placa": placa,
                "descricao_problema": "Teste restart e compensacao P5",
            },
        )
        assert r_os.status_code == 202, r_os.text
        os_id = r_os.json()["os_id"]
        saga_id = r_os.json()["saga_id"]
        exec_id = f"{os_id}_1"

        # P4 Addendum: para o os-worker DURANTE etapa pendente (DIAGNOSTICO)
        subprocess.run(
            ["docker", "compose", "-f", "integration/compose.yml", "stop", "os-worker"],
            check=True,
        )

        # Conclui diagnóstico enquanto os-worker está parado
        r_diag = client.post(
            f"{EXEC_URL}/v1/execucoes/{exec_id}/diagnostico",
            headers=headers,
            json={
                "os_id": os_id,
                "saga_id": saga_id,
                "rodada": 1,
                "laudo": "Troca filtro P5",
                "itens_servico": [
                    {
                        "servico_id": srv_id,
                        "descricao": "Alinhamento P5",
                        "preco_unitario_centavos": 10000,
                    }
                ],
                "itens_peca": [
                    {
                        "peca_id": peca_id,
                        "descricao": "Filtro P5",
                        "quantidade": 2,
                        "preco_unitario_centavos": 5000,
                    }
                ],
            },
        )
        assert r_diag.status_code == 201, r_diag.text

        # Confirma que a Saga permaneceu persistida em DIAGNOSTICO enquanto worker estava fora
        saga_pausada = client.get(
            f"{OS_URL}/v1/ordens-servico/{os_id}/saga", headers=headers
        ).json()
        assert saga_pausada["estado"] == "DIAGNOSTICO"

        # Religa os-worker -> retoma estado persistido e avança até AGUARDANDO_APROVACAO
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "integration/compose.yml",
                "start",
                "os-worker",
            ],
            check=True,
        )

        _esperar_condicao(
            lambda: (
                lambda r: (
                    r.json()
                    if r.status_code == 200
                    and r.json()["estado"] == "AGUARDANDO_APROVACAO"
                    else None
                )
            )(client.get(f"{OS_URL}/v1/ordens-servico/{os_id}/saga", headers=headers)),
            descricao="Saga retomada após reinício até AGUARDANDO_APROVACAO",
        )

        # 2. Aprova orçamento -> reserva 2 peças (10 -> 8) -> AGUARDANDO_PAGAMENTO
        orc = client.get(
            f"{BILLING_URL}/v1/orcamentos/por-os/{os_id}", headers=headers
        ).json()
        r_aprov = client.post(
            f"{BILLING_URL}/v1/orcamentos/{orc['id']}/decisao",
            headers=headers,
            json={"aprovado": True, "versao": orc["versao"]},
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
        assert (
            client.get(f"{EXEC_URL}/v1/pecas/{peca_id}", headers=headers).json()[
                "quantidade_disponivel"
            ]
            == 8
        )

        # 3. Simula recusa de pagamento -> PagamentoRecusado.v1 -> barreira -> compensação completa
        pag = client.get(
            f"{BILLING_URL}/v1/pagamentos/por-os/{os_id}", headers=headers
        ).json()
        sim_rec = client.post(
            f"{BILLING_URL}/internal/fake-mp/{pag['provider_order_id']}/recusar",
            headers=headers,
        ).json()
        r_wh = client.post(
            f"{BILLING_URL}/webhooks/mercadopago",
            headers=sim_rec["headers"],
            json=sim_rec["body"],
        )
        assert r_wh.status_code == 200, r_wh.text

        saga_comp = _esperar_condicao(
            lambda: (
                lambda r: (
                    r.json()
                    if r.status_code == 200 and r.json()["estado"] == "COMPENSADA"
                    else None
                )
            )(client.get(f"{OS_URL}/v1/ordens-servico/{os_id}/saga", headers=headers)),
            descricao="Saga em COMPENSADA após recusa de pagamento",
        )
        peca_restaurada = client.get(
            f"{EXEC_URL}/v1/pecas/{peca_id}", headers=headers
        ).json()["quantidade_disponivel"]
        assert peca_restaurada == 10

    eng = create_engine(DB_OS)
    with eng.connect() as conn:
        rows = conn.execute(
            text("SELECT status, count(*) FROM outbox_eventos GROUP BY status")
        ).all()
        outbox_status = {r[0]: r[1] for r in rows}

    print(
        "E2E_P5_RESTART_E_COMPENSACAO_OK",
        {
            "os_id": os_id,
            "saga_id": saga_comp["saga_id"],
            "estado_pausado": saga_pausada["estado"],
            "estado_final": saga_comp["estado"],
            "efeitos_confirmados": saga_comp["efeitos_confirmados"],
            "estoque_restaurado": peca_restaurada,
            "outbox_status": outbox_status,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
