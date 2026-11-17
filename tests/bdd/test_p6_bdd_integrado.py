from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import httpx
import pytest
from pytest_bdd import given, scenarios, then, when

from integration import e2e_p4_fluxo_feliz, e2e_p5_compensacoes

RELATORIOS_DIR = Path(__file__).resolve().parents[2] / "integration" / "relatorios"

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_BDD") != "1",
    reason="BDD integrado executa contra stack Docker ao vivo quando RUN_LIVE_BDD=1",
)

scenarios("saga_integrada.feature")


def _capturar_logs_falha(cenario: str) -> None:
    RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_file = RELATORIOS_DIR / f"falha_{cenario}_{ts}.log"
    res = subprocess.run(
        ["docker", "compose", "-f", "integration/compose.yml", "logs", "--no-color"],
        capture_output=True,
        text=True,
        check=False,
    )
    log_file.write_text(res.stdout + "\n" + res.stderr, encoding="utf-8")


@pytest.fixture
def contexto_bdd() -> dict[str, int]:
    return {}


@given(
    "que a stack integrada com os três serviços, PostgreSQL, Firestore Emulator e Pub/Sub Emulator está saudável"
)
def stack_integrada_saudavel() -> None:
    for url in (
        e2e_p4_fluxo_feliz.OS_URL,
        e2e_p4_fluxo_feliz.BILLING_URL,
        e2e_p4_fluxo_feliz.EXEC_URL,
    ):
        e2e_p4_fluxo_feliz._esperar_condicao(
            lambda u=url: (
                True
                if httpx.get(f"{u}/health/ready", timeout=3.0).status_code == 200
                else None
            ),
            timeout_s=45.0,
            descricao=f"readiness de {url}",
        )


@when("executo o fluxo E2E completo de abertura até entrega com pagamento aprovado")
def executar_fluxo_feliz(contexto_bdd: dict[str, int]) -> None:
    try:
        contexto_bdd["fluxo_feliz"] = e2e_p4_fluxo_feliz.main()
    except Exception:
        _capturar_logs_falha("fluxo_feliz")
        raise


@then(
    "a Saga conclui em CONCLUIDA, a OS atinge ENTREGUE e o estoque reservado permanece debitado"
)
def validar_fluxo_feliz(contexto_bdd: dict[str, int]) -> None:
    assert contexto_bdd.get("fluxo_feliz") == 0


@when(
    "o worker do orquestrador reinicia em etapa pendente e o pagamento é recusado após reserva de peças"
)
def executar_compensacao_e_reinicio(contexto_bdd: dict[str, int]) -> None:
    try:
        contexto_bdd["compensacao"] = e2e_p5_compensacoes.main()
    except Exception:
        _capturar_logs_falha("compensacao_e_retomada")
        raise


@then(
    "a Saga retoma pelo estado persistido, exige a barreira de cancelamento, restaura o estoque e conclui em COMPENSADA"
)
def validar_compensacao_e_reinicio(contexto_bdd: dict[str, int]) -> None:
    assert contexto_bdd.get("compensacao") == 0
