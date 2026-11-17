from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import pytest

from integration import e2e_p4_fluxo_feliz, e2e_p5_compensacoes

FEATURE_PATH = Path(__file__).with_name("saga_integrada.feature")
RELATORIOS_DIR = Path(__file__).resolve().parents[2] / "integration" / "relatorios"

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_BDD") != "1",
    reason="BDD integrado executa contra stack Docker ao vivo quando RUN_LIVE_BDD=1",
)


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


def test_bdd_feature_e_cenarios_definidos() -> None:
    conteudo = FEATURE_PATH.read_text(encoding="utf-8")
    assert "Fluxo feliz completo" in conteudo
    assert "Compensação completa após recusa de pagamento" in conteudo


def test_bdd_cenario_fluxo_feliz_completo() -> None:
    try:
        rc = e2e_p4_fluxo_feliz.main()
        assert rc == 0
    except Exception:
        _capturar_logs_falha("fluxo_feliz")
        raise


def test_bdd_cenario_compensacao_e_retomada_apos_reinicio() -> None:
    try:
        rc = e2e_p5_compensacoes.main()
        assert rc == 0
    except Exception:
        _capturar_logs_falha("compensacao_e_retomada")
        raise
