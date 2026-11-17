from contextvars import ContextVar
import logging
import os

correlacao_ctx: ContextVar[dict[str, str] | None] = ContextVar(
    "correlacao_ctx", default=None
)


def extrair_trace_e_span(traceparent: str | None) -> tuple[str, str]:
    if not traceparent:
        return "0", "0"
    partes = traceparent.strip().split("-")
    if len(partes) != 4:
        return "0", "0"
    try:
        trace_id = str(int(partes[1], 16))
        span_id = str(int(partes[2], 16))
        return trace_id, span_id
    except ValueError:
        return "0", "0"


class FiltroCorrelacaoPadrao(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        ctx = correlacao_ctx.get() or {}
        padroes = {
            "dd.service": os.getenv("DD_SERVICE", "oficina-api"),
            "dd.env": os.getenv("DD_ENV", "homolog"),
            "dd.version": os.getenv("DD_VERSION", "0.2.0"),
            "dd.trace_id": ctx.get("dd.trace_id", "0"),
            "dd.span_id": ctx.get("dd.span_id", "0"),
            "correlation_id": ctx.get("correlation_id", ""),
            "saga_id": ctx.get("saga_id", ""),
            "os_id": ctx.get("os_id", ""),
            "event_id": ctx.get("event_id", ""),
        }
        for campo, valor in padroes.items():
            atual = getattr(record, campo, None)
            if atual is None or atual in ("", "0"):
                setattr(record, campo, valor)
        return True
