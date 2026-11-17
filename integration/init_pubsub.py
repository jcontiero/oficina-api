"""
Inicializa os tópicos e subscriptions da Fase 4 no emulador do Google Cloud Pub/Sub.
Topologia por ambiente (homolog):
- Tópico de eventos: oficina-homolog-eventos-v1
- Tópico de comandos do Billing: oficina-homolog-billing-comandos-v1
- Tópico de comandos da Execução: oficina-homolog-execucao-comandos-v1
- Tópico de DLQ: oficina-homolog-saga-dlq
"""

import os
import sys
import time

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "fiap-project-514922")
ENV = os.getenv("ENVIRONMENT", "homolog")

TOPICOS = [
    f"oficina-{ENV}-eventos-v1",
    f"oficina-{ENV}-billing-comandos-v1",
    f"oficina-{ENV}-execucao-comandos-v1",
    f"oficina-{ENV}-saga-dlq",
]

SUBSCRIPTIONS = [
    (f"oficina-{ENV}-os-orquestrador-sub", f"oficina-{ENV}-eventos-v1"),
    (f"oficina-{ENV}-notificacoes-sub", f"oficina-{ENV}-eventos-v1"),
    (f"oficina-{ENV}-billing-comandos-sub", f"oficina-{ENV}-billing-comandos-v1"),
    (f"oficina-{ENV}-execucao-comandos-sub", f"oficina-{ENV}-execucao-comandos-v1"),
    (f"oficina-{ENV}-saga-dlq-inspecao-sub", f"oficina-{ENV}-saga-dlq"),
]


def inicializar_topologia_pubsub() -> dict[str, list[str]]:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    topicos_criados: list[str] = []
    subs_criadas: list[str] = []

    for nome_topico in TOPICOS:
        topic_path = publisher.topic_path(PROJECT_ID, nome_topico)
        try:
            publisher.create_topic(request={"name": topic_path})
        except AlreadyExists:
            pass
        topicos_criados.append(nome_topico)

    for nome_sub, nome_topico in SUBSCRIPTIONS:
        sub_path = subscriber.subscription_path(PROJECT_ID, nome_sub)
        topic_path = publisher.topic_path(PROJECT_ID, nome_topico)
        try:
            subscriber.create_subscription(
                request={
                    "name": sub_path,
                    "topic": topic_path,
                    "ack_deadline_seconds": 30,
                }
            )
        except AlreadyExists:
            pass
        subs_criadas.append(nome_sub)

    return {"topics": topicos_criados, "subscriptions": subs_criadas}


def main() -> int:
    deadline = time.time() + 30
    ultimo_erro: Exception | None = None
    while time.time() < deadline:
        try:
            resultado = inicializar_topologia_pubsub()
            print(f"Pub/Sub inicializado com sucesso: {resultado}")
            return 0
        except Exception as exc:  # noqa: BLE001
            ultimo_erro = exc
            time.sleep(1)
    print(f"Falha ao inicializar Pub/Sub: {ultimo_erro}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
