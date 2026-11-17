from ddtrace import tracer
from src.shared.correlacao import consumir_contexto, traceparent_atual, correlacao_ctx


def test_contexto_consumer_preserva_trace_e_limpa_estado(monkeypatch):
    monkeypatch.setenv("DD_TRACE_ENABLED", "true")
    monkeypatch.setattr(tracer, "enabled", False)
    anterior = tracer.context_provider.active()
    pai = "00-0000000000000000000000000000007b-00000000000001c8-01"
    with consumir_contexto(
        {"saga_id": "saga-teste", "event_type": "Teste.v1"}, pai
    ) as propagado:
        assert tracer.current_span().trace_id == 123
        assert tracer.current_span().parent_id == 456
        assert correlacao_ctx.get()["saga_id"] == "saga-teste"
        assert propagado == traceparent_atual()
    assert tracer.context_provider.active() is anterior
    assert correlacao_ctx.get() is None


def test_contexto_local_nao_exige_agent(monkeypatch):
    monkeypatch.setenv("DD_TRACE_ENABLED", "false")
    with consumir_contexto({"event_id": "evento-teste"}, None) as propagado:
        assert propagado is None
        assert correlacao_ctx.get()["event_id"] == "evento-teste"
    assert correlacao_ctx.get() is None
