from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from src.shared.banco import Base


class OutboxEventoModel(Base):
    """
    Tabela Transactional Outbox com suporte a lease (locked_until), retry com
    backoff exponencial (next_attempt_at / tentativas) e tópicos por destino.
    Status válidos: PENDENTE, FALHA_AGENDADA, PROCESSADO.
    """

    __tablename__ = "outbox_eventos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), unique=True, nullable=True)
    topic = Column(String(128), nullable=False, default="oficina-homolog-eventos-v1")
    tipo_evento = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    traceparent = Column(String(128), nullable=True)
    status = Column(String(24), nullable=False, default="PENDENTE")
    tentativas = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    locked_until = Column(DateTime(timezone=True), nullable=True)
    criado_em = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processado_em = Column(DateTime(timezone=True), nullable=True)
    erro = Column(Text, nullable=True)


class InboxEventoModel(Base):
    """
    Tabela Inbox para deduplicação idempotente de consumidores por (consumer, event_id).
    Inserida na mesma transação local que aplica o efeito de domínio e gera nova outbox.
    """

    __tablename__ = "inbox_eventos"
    __table_args__ = (
        UniqueConstraint("consumer", "event_id", name="uq_inbox_consumer_event"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    consumer = Column(String(64), nullable=False)
    event_id = Column(String(36), nullable=False)
    event_type = Column(String(100), nullable=False)
    saga_id = Column(String(36), nullable=True)
    recebido_em = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
