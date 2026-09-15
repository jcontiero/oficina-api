import os
import time
import json
import logging
from google.cloud import pubsub_v1
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import Configuracoes
from src.shared.outbox import OutboxEventoModel

from pythonjsonlogger import jsonlogger
from ddtrace import patch_all

patch_all()

logger = logging.getLogger("outbox-worker")
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s",
    rename_fields={"levelname": "level", "asctime": "timestamp"},
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.propagate = False


def main():
    logger.info("Iniciando Outbox Worker...")
    cfg = Configuracoes()

    project_id = os.getenv("GCP_PROJECT_ID", "pos-fiap-2026")
    topic_id = os.getenv("PUBSUB_TOPIC_ID", "oficina-notificacoes-topic")

    # Se estiver rodando localmente sem credenciais, podemos querer pular o pubsub real
    # Mas para o Tech Challenge, o worker deve assumir que tem credenciais ou workload identity.
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)

    engine = create_engine(cfg.database_url)
    Session = sessionmaker(bind=engine)

    while True:
        try:
            with Session() as session:
                # Busca eventos pendentes (com LIMIT para nao estourar memoria)
                eventos = (
                    session.query(OutboxEventoModel)
                    .filter(OutboxEventoModel.status == "PENDENTE")
                    .order_by(OutboxEventoModel.criado_em.asc())
                    .limit(50)
                    .all()
                )

                if not eventos:
                    time.sleep(5)
                    continue

                for evento in eventos:
                    try:
                        data = json.dumps(evento.payload).encode("utf-8")
                        future = publisher.publish(
                            topic_path, data, tipo_evento=evento.tipo_evento
                        )
                        message_id = future.result(timeout=10)

                        logger.info(
                            f"Evento {evento.id} publicado no Pub/Sub. Message ID: {message_id}"
                        )
                        evento.status = "PROCESSADO"
                    except Exception as e:
                        logger.error(f"Erro ao publicar evento {evento.id}: {e}")
                        evento.status = "ERRO"
                        evento.erro = str(e)

                session.commit()
        except Exception as e:
            logger.error(f"Erro no loop do worker: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
