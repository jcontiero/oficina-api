import uuid
import datetime
from sqlalchemy import Column, String, DateTime, JSON
from src.shared.banco import Base


class OutboxEventoModel(Base):
    __tablename__ = "outbox_eventos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tipo_evento = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(
        String(20), nullable=False, default="PENDENTE"
    )  # PENDENTE, PROCESSADO, ERRO
    criado_em = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    processado_em = Column(DateTime, nullable=True)
    erro = Column(String, nullable=True)
