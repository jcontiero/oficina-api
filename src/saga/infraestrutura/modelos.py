from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.banco import Base


class SagaInstanceModel(Base):
    __tablename__ = "saga_instances"
    __table_args__ = (UniqueConstraint("os_id", "rodada", name="uq_saga_os_rodada"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    os_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rodada: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="ABERTA")
    subestado_compensacao: Mapped[str | None] = mapped_column(String(48), nullable=True)
    compensacao_financeira_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NAO_APLICAVEL"
    )
    execucao_cancelada_event_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    compensacao_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    motivo_compensacao: Mapped[str | None] = mapped_column(String(64), nullable=True)
    efeitos_esperados_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    efeitos_confirmados_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    orcamento_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    orcamento_versao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pagamento_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    total_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class SagaStepModel(Base):
    __tablename__ = "saga_steps"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    saga_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saga_instances.id", ondelete="CASCADE"), nullable=False
    )
    etapa: Mapped[str] = mapped_column(String(48), nullable=False)
    comando_event_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False
    )
    comando_tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    resposta_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resposta_tipo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDENTE")
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
