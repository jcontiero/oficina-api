from pathlib import Path
from unittest.mock import MagicMock

from integration.init_pubsub import (
    SUBSCRIPTIONS,
    TOPICOS,
    inicializar_topologia_pubsub,
)

ROOT_DIR = Path(__file__).resolve().parents[2]


def test_compose_stack_p2_e_isolamento_postgres():
    compose_path = ROOT_DIR / "integration" / "compose.yml"
    init_sql_path = ROOT_DIR / "integration" / "init_postgres.sh"
    assert compose_path.exists()
    assert init_sql_path.exists()

    compose_text = compose_path.read_text()
    init_sql_text = init_sql_path.read_text()

    # Verifica os três microsserviços e os dois emuladores (Pub/Sub e Firestore)
    assert "oficina-os:" in compose_text
    assert "oficina-billing:" in compose_text
    assert "oficina-execucao:" in compose_text
    assert "pubsub-emulator:" in compose_text
    assert "firestore-emulator:" in compose_text

    # Verifica isolamento de usuários e bancos SQL (REVOKE CONNECT FROM PUBLIC)
    assert "CREATE DATABASE oficina_os_homolog;" in init_sql_text
    assert "CREATE USER oficina_os_user" in init_sql_text
    assert "REVOKE CONNECT ON DATABASE oficina_os_homolog FROM PUBLIC;" in init_sql_text
    assert "CREATE DATABASE oficina_billing_homolog;" in init_sql_text
    assert "CREATE USER oficina_billing_user" in init_sql_text
    assert (
        "REVOKE CONNECT ON DATABASE oficina_billing_homolog FROM PUBLIC;"
        in init_sql_text
    )


def test_init_pubsub_topologia_v1(monkeypatch):
    fake_pub = MagicMock()
    fake_sub = MagicMock()
    fake_pub.topic_path.side_effect = lambda proj, top: f"projects/{proj}/topics/{top}"
    fake_sub.subscription_path.side_effect = (
        lambda proj, sub: f"projects/{proj}/subscriptions/{sub}"
    )

    monkeypatch.setattr(
        "integration.init_pubsub.pubsub_v1.PublisherClient", lambda: fake_pub
    )
    monkeypatch.setattr(
        "integration.init_pubsub.pubsub_v1.SubscriberClient", lambda: fake_sub
    )

    resultado = inicializar_topologia_pubsub()
    assert resultado["topics"] == TOPICOS
    assert len(resultado["subscriptions"]) == len(SUBSCRIPTIONS)
    assert fake_pub.create_topic.call_count == len(TOPICOS)
    assert fake_sub.create_subscription.call_count == len(SUBSCRIPTIONS)
