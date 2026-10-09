from langchain_core.tracers.langchain import LangChainTracer

from navigator.observability import build_tracing_callbacks


def test_no_key_means_no_tracer() -> None:
    assert build_tracing_callbacks("", "proj") == []


def test_tracer_uses_the_configured_key_not_the_ambient_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    (tracer,) = build_tracing_callbacks("lsv2_pt_test", "proj")  # pragma: allowlist secret
    assert isinstance(tracer, LangChainTracer)
    assert tracer.client.api_key == "lsv2_pt_test"  # pragma: allowlist secret
