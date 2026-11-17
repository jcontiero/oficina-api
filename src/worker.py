from datetime import datetime, timedelta, timezone
import json
import logging
import os
import time
from typing import Any

from google.cloud import pubsub_v1
from pythonjsonlogger import jsonlogger
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker

from src.config import Configuracoes
from src.saga.aplicacao.orquestrador import OrquestradorSaga
from src.shared.correlacao import (
    FiltroCorrelacaoPadrao,
    correlacao_ctx,
    extrair_trace_e_span,
)
from src.shared.outbox import OutboxEventoModel

_FiltroCorrelacaoPadrao = FiltroCorrelacaoPadrao

if os.getenv("DD_TRACE_ENABLED", "false").lower() in {"1", "true", "yes"}:
    try:
        from ddtrace import patch_all

        patch_all()
    except Exception:
        pass

logger = logging.getLogger("os-saga-worker")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(
    jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"levelname": "level", "asctime": "timestamp"},
    )
)
logger.handlers.clear()
logger.addHandler(_handler)
logger.addFilter(_FiltroCorrelacaoPadrao())
logger.propagate = False


def publicar_lote_outbox(
    session: Session,
    publisher: Any,
    *,
    project_id: str,
    lease_seconds: int = 30,
    limit: int = 50,
    agora: datetime | None = None,
) -> int:
    """
    Reivindica eventos PENDENTE ou FALHA_AGENDADA vencidos com lease (locked_until),
    publica no tópico Pub/Sub fora de trava longa e só marca PROCESSADO após ACK
    do broker. Em falha, agenda nova tentativa com backoff exponencial sem nunca
    abandonar o registro em estado irrecuperável.
    """
    ref = agora or datetime.now(timezone.utc)
    eventos = (
        session.query(OutboxEventoModel)
        .filter(
            OutboxEventoModel.status.in_(["PENDENTE", "FALHA_AGENDADA"]),
            OutboxEventoModel.next_attempt_at <= ref,
            or_(
                OutboxEventoModel.locked_until.is_(None),
                OutboxEventoModel.locked_until <= ref,
            ),
        )
        .order_by(OutboxEventoModel.criado_em.asc())
        .limit(limit)
        .all()
    )

    if not eventos:
        return 0

    lease_expira = ref + timedelta(seconds=lease_seconds)
    reivindicados: list[OutboxEventoModel] = []
    for ev in eventos:
        atualizado = (
            session.query(OutboxEventoModel)
            .filter(
                OutboxEventoModel.id == ev.id,
                OutboxEventoModel.status.in_(["PENDENTE", "FALHA_AGENDADA"]),
                or_(
                    OutboxEventoModel.locked_until.is_(None),
                    OutboxEventoModel.locked_until <= ref,
                ),
            )
            .update({"locked_until": lease_expira}, synchronize_session=False)
        )
        if atualizado == 1:
            reivindicados.append(ev)
    session.commit()
    if not reivindicados:
        return 0

    publicados = 0
    for ev in reivindicados:
        try:
            topic_path = publisher.topic_path(project_id, ev.topic)
            data = json.dumps(ev.payload).encode("utf-8")
            attrs = {
                "event_type": ev.tipo_evento,
                "producer": str(ev.payload.get("producer", "oficina-os")),
                "schema_version": str(ev.payload.get("schema_version", 1)),
            }
            if ev.traceparent:
                attrs["traceparent"] = ev.traceparent

            future = publisher.publish(topic_path, data, **attrs)
            future.result(timeout=10)
            ev.status = "PROCESSADO"
            ev.processado_em = datetime.now(timezone.utc)
            ev.locked_until = None
            ev.erro = None
            publicados += 1
        except Exception as exc:  # noqa: BLE001
            ev.tentativas = int(ev.tentativas or 0) + 1
            atraso = min(60, 2 ** min(ev.tentativas, 5))
            ev.status = "FALHA_AGENDADA"
            ev.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=atraso)
            ev.locked_until = None
            ev.erro = str(exc)
            logger.error("Falha ao publicar outbox %s: %s", ev.id, exc)
        session.commit()

    return publicados


def consumir_mensagens_pull(
    session_factory: sessionmaker,
    subscriber: Any,
    *,
    project_id: str,
    subscription_name: str,
    environment: str = "homolog",
    max_messages: int = 20,
) -> int:
    """
    Consome mensagens via synchronous pull do Pub/Sub e executa ACK somente após
    o commit transacional do OrquestradorSaga. Em falha, executa modify_ack_deadline=0
    (nack imediato) para reentrega segura.
    """
    sub_path = subscriber.subscription_path(project_id, subscription_name)
    try:
        resp = subscriber.pull(
            request={
                "subscription": sub_path,
                "max_messages": max_messages,
                "return_immediately": True,
            },
            timeout=5,
        )
    except Exception as exc:
        if "DeadlineExceeded" in type(exc).__name__ or "504" in str(exc):
            return 0
        raise
    if not resp.received_messages:
        return 0

    processadas = 0
    for rec in resp.received_messages:
        ack_id = rec.ack_id
        try:
            dados = json.loads(rec.message.data.decode("utf-8"))
            traceparent = (rec.message.attributes or {}).get("traceparent")
            trace_id, span_id = extrair_trace_e_span(traceparent)
            token = correlacao_ctx.set(
                {
                    "correlation_id": str(dados.get("correlation_id", "")),
                    "saga_id": str(dados.get("saga_id", "")),
                    "os_id": str(dados.get("os_id", "")),
                    "event_id": str(dados.get("event_id", "")),
                    "dd.trace_id": trace_id,
                    "dd.span_id": span_id,
                }
            )
            try:
                with session_factory() as db:
                    OrquestradorSaga(
                        db, environment=environment
                    ).processar_evento_envelope(
                        dados, consumer="os-orquestrador", traceparent=traceparent
                    )
            finally:
                correlacao_ctx.reset(token)
            subscriber.acknowledge(
                request={"subscription": sub_path, "ack_ids": [ack_id]}
            )
            processadas += 1
        except Exception:  # noqa: BLE001
            logger.exception("Erro ao processar mensagem no OS Orquestrador")
            try:
                subscriber.modify_ack_deadline(
                    request={
                        "subscription": sub_path,
                        "ack_ids": [ack_id],
                        "ack_deadline_seconds": 0,
                    }
                )
            except Exception:  # noqa: BLE001
                pass
    return processadas


def executar_ciclo_worker(
    session_factory: sessionmaker,
    *,
    publisher: Any,
    subscriber: Any,
    project_id: str,
    subscription_name: str,
    environment: str = "homolog",
) -> dict[str, int]:
    with session_factory() as db:
        expiradas = OrquestradorSaga(
            db, environment=environment
        ).expirar_sagas_vencidas()
    with session_factory() as db:
        publicadas = publicar_lote_outbox(db, publisher, project_id=project_id)
    consumidas = consumir_mensagens_pull(
        session_factory,
        subscriber,
        project_id=project_id,
        subscription_name=subscription_name,
        environment=environment,
    )
    return {
        "expiradas": expiradas,
        "publicadas": publicadas,
        "consumidas": consumidas,
    }


def main() -> None:
    cfg = Configuracoes()
    project_id = os.getenv("GCP_PROJECT_ID", "fiap-project-514922")
    env = cfg.environment
    sub_name = os.getenv("OS_ORQUESTRADOR_SUB", f"oficina-{env}-os-orquestrador-sub")
    engine = create_engine(cfg.database_url)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    logger.info("Worker OS Saga iniciado (env=%s, sub=%s)", env, sub_name)
    while True:
        try:
            executar_ciclo_worker(
                session_factory,
                publisher=publisher,
                subscriber=subscriber,
                project_id=project_id,
                subscription_name=sub_name,
                environment=env,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Erro no loop do worker OS Saga")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
