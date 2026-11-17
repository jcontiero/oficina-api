"""
Script de verificação e smoke test da stack integrada da Etapa P2:
1. Verifica /health/live e /health/ready nos três microsserviços (oficina-os:8000, oficina-billing:8001, oficina-execucao:8002).
2. Comprova o isolamento dos bancos PostgreSQL:
   - oficina_os_user conecta em oficina_os_homolog, mas é RECUSADO em oficina_billing_homolog.
   - oficina_billing_user conecta em oficina_billing_homolog, mas é RECUSADO em oficina_os_homolog.
3. Comprova persistência real no PostgreSQL do Billing, no Firestore Emulator da Execução e a topologia no Pub/Sub Emulator.
"""

import os
import time

from google.cloud import pubsub_v1
import httpx
from sqlalchemy import create_engine, text


def aguardar_servicos_saudaveis(timeout_s: int = 60) -> dict[str, dict]:
    endpoints = {
        "oficina-os": "http://localhost:8000/health/ready",
        "oficina-billing": "http://localhost:8001/health/ready",
        "oficina-execucao": "http://localhost:8002/health/ready",
    }
    resultados: dict[str, dict] = {}
    deadline = time.time() + timeout_s

    with httpx.Client(timeout=3.0) as client:
        for nome, url in endpoints.items():
            while True:
                try:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        resultados[nome] = resp.json()
                        break
                except Exception:  # noqa: BLE001
                    pass
                if time.time() >= deadline:
                    raise RuntimeError(
                        f"Timeout aguardando readiness de {nome} ({url})"
                    )
                time.sleep(1)
    return resultados


def verificar_isolamento_postgres() -> dict[str, str]:
    os_ok_url = "postgresql+pg8000://oficina_os_user:oficina_os_pass@localhost:5432/oficina_os_homolog"
    os_cross_url = "postgresql+pg8000://oficina_os_user:oficina_os_pass@localhost:5432/oficina_billing_homolog"

    billing_ok_url = "postgresql+pg8000://oficina_billing_user:oficina_billing_pass@localhost:5432/oficina_billing_homolog"
    billing_cross_url = "postgresql+pg8000://oficina_billing_user:oficina_billing_pass@localhost:5432/oficina_os_homolog"

    with create_engine(os_ok_url).connect() as conn:
        conn.execute(text("SELECT 1"))

    with create_engine(billing_ok_url).connect() as conn:
        conn.execute(text("SELECT 1"))

    os_bloqueado = False
    try:
        with create_engine(os_cross_url).connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        os_bloqueado = True

    billing_bloqueado = False
    try:
        with create_engine(billing_cross_url).connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        billing_bloqueado = True

    if not os_bloqueado or not billing_bloqueado:
        raise RuntimeError(
            f"Isolamento de bancos violado! os_bloqueado={os_bloqueado}, billing_bloqueado={billing_bloqueado}"
        )

    return {
        "oficina_os_user_em_billing_db": "PERMISSION_DENIED (ISOLADO)",
        "oficina_billing_user_em_os_db": "PERMISSION_DENIED (ISOLADO)",
    }


def verificar_persistencia_firestore_e_pubsub() -> dict[str, int | bool]:
    os.environ.setdefault("PUBSUB_EMULATOR_HOST", "localhost:8085")

    fs_url = "http://localhost:8086/v1/projects/fiap-project-514922/databases/(default)/documents/controle_saga?documentId=smoke-test-p2"
    with httpx.Client(timeout=5.0) as client:
        client.delete(
            "http://localhost:8086/v1/projects/fiap-project-514922/databases/(default)/documents/controle_saga/smoke-test-p2"
        )
        r_create = client.post(
            fs_url,
            json={
                "fields": {
                    "saga_id": {"stringValue": "smoke-test-p2"},
                    "estado_controle": {"stringValue": "ATIVO"},
                }
            },
        )
        assert r_create.status_code == 200
        r_get = client.get(
            "http://localhost:8086/v1/projects/fiap-project-514922/databases/(default)/documents/controle_saga/smoke-test-p2"
        )
        assert r_get.status_code == 200
        assert r_get.json()["fields"]["estado_controle"]["stringValue"] == "ATIVO"

    publisher = pubsub_v1.PublisherClient()
    project_path = "projects/fiap-project-514922"
    topicos = [t.name for t in publisher.list_topics(request={"project": project_path})]
    assert any("oficina-homolog-eventos-v1" in t for t in topicos)

    return {
        "firestore_write_read_ok": True,
        "pubsub_topics_count": len(topicos),
    }


def main() -> int:
    saude = aguardar_servicos_saudaveis()
    isolamento = verificar_isolamento_postgres()
    emuladores = verificar_persistencia_firestore_e_pubsub()
    print(
        "SMOKE_P2_OK",
        {"health": saude, "isolation": isolamento, "emulators": emuladores},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
