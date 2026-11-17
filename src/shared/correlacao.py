from contextlib import contextmanager
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


def traceparent_atual(recebido: str | None = None) -> str | None:
    from ddtrace import tracer
    from ddtrace.propagation.http import HTTPPropagator

    headers = {}
    contexto = tracer.current_trace_context()
    if contexto is not None:
        HTTPPropagator.inject(contexto, headers)
    return headers.get("traceparent") or recebido


@contextmanager
def consumir_contexto(dados, traceparent):
    from ddtrace import tracer
    from ddtrace.propagation.http import HTTPPropagator

    anterior = tracer.context_provider.active()
    contexto = {
        **(correlacao_ctx.get() or {}),
        **{
            k: str(dados.get(k, ""))
            for k in ("correlation_id", "saga_id", "os_id", "event_id")
        },
    }
    token = correlacao_ctx.set(contexto)
    try:
        if os.getenv("DD_TRACE_ENABLED", "false").lower() != "true":
            yield traceparent
            return
        if traceparent:
            tracer.context_provider.activate(
                HTTPPropagator.extract({"traceparent": traceparent})
            )
        with tracer.trace(
            "pubsub.consume", resource=dados.get("event_type", "mensagem")
        ) as span:
            contexto.update(
                {
                    "trace_id": str(span.trace_id),
                    "span_id": str(span.span_id),
                    "dd.trace_id": str(span.trace_id),
                    "dd.span_id": str(span.span_id),
                }
            )
            for chave, valor in contexto.items():
                span.set_tag(chave, valor)
            yield traceparent_atual(traceparent)
    finally:
        correlacao_ctx.reset(token)
        tracer.context_provider.activate(anterior)
