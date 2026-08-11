from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from app import agent as agent_module
from app import logging_config


class FakeSpan:
    def __init__(self, name: str, kwargs: dict) -> None:
        self.name = name
        self.start_kwargs = kwargs
        self.updates: list[dict] = []

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)


class SpanRecordingClient:
    """Client Langfuse giả, ghi lại span con và metadata mà agent gửi lên."""

    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []
        self.trace_updates: list[dict] = []
        self.generation_updates: list[dict] = []

    def get_current_trace_id(self) -> str:
        return "trace-abc123"

    @contextmanager
    def start_as_current_span(self, *, name: str, **kwargs):
        span = FakeSpan(name, kwargs)
        self.spans.append(span)
        yield span

    def update_current_trace(self, **kwargs) -> None:
        self.trace_updates.append(kwargs)

    def update_current_generation(self, **kwargs) -> None:
        self.generation_updates.append(kwargs)


def _run_agent(monkeypatch, tmp_path: Path, client: SpanRecordingClient) -> list[dict]:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    # File này có thể chạy riêng lẻ, khi đó chưa ai gọi configure_logging().
    logging_config.configure_logging()
    monkeypatch.setattr(agent_module, "log", logging_config.get_logger())
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "trace_url", lambda trace_id: f"http://lf/{trace_id}")

    agent_module.LabAgent.run.__wrapped__(
        agent_module.LabAgent(),
        user_id="student-01",
        feature="refund",
        session_id="session-01",
        message="What is your refund policy?",
    )
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_agent_opens_one_span_per_sub_component(monkeypatch, tmp_path: Path) -> None:
    client = SpanRecordingClient()

    _run_agent(monkeypatch, tmp_path, client)

    assert [span.name for span in client.spans] == [
        "rag-retrieval",
        "prompt-resolve",
        "llm-generate",
    ]
    retrieval_metadata = client.spans[0].updates[-1]["metadata"]
    assert retrieval_metadata["component"] == "mock_rag"
    assert retrieval_metadata["doc_count"] == 1
    assert "duration_ms" in retrieval_metadata


def test_failed_retrieval_marks_its_span_as_error(monkeypatch, tmp_path: Path) -> None:
    client = SpanRecordingClient()
    monkeypatch.setattr(
        agent_module,
        "retrieve",
        lambda message: (_ for _ in ()).throw(RuntimeError("Vector store timeout")),
    )

    try:
        _run_agent(monkeypatch, tmp_path, client)
    except RuntimeError:
        pass
    else:  # pragma: no cover - lỗi phải được ném lại cho handler của API
        raise AssertionError("agent phải ném lại lỗi retrieval")

    assert [span.name for span in client.spans] == ["rag-retrieval"]
    failure_update = client.spans[0].updates[-1]
    assert failure_update["level"] == "ERROR"
    assert failure_update["status_message"] == "RuntimeError"


def test_logs_link_correlation_id_to_trace_id_and_span_timings(
    monkeypatch, tmp_path: Path
) -> None:
    client = SpanRecordingClient()

    events = _run_agent(monkeypatch, tmp_path, client)

    linked = next(event for event in events if event["event"] == "trace_linked")
    timings = next(event for event in events if event["event"] == "span_timings")
    assert linked["trace_id"] == "trace-abc123"
    assert linked["trace_url"] == "http://lf/trace-abc123"
    assert timings["slowest_span"] == "llm-generate"
    assert timings["llm_ms"] >= 100
    assert {"retrieval_ms", "prompt_ms", "llm_ms", "latency_ms"} <= timings.keys()


def test_correlation_id_is_searchable_as_a_trace_tag(monkeypatch, tmp_path: Path) -> None:
    from structlog.contextvars import bind_contextvars, clear_contextvars

    client = SpanRecordingClient()
    clear_contextvars()
    bind_contextvars(correlation_id="req-deadbeef")
    try:
        _run_agent(monkeypatch, tmp_path, client)
    finally:
        clear_contextvars()

    assert "req-deadbeef" in client.trace_updates[-1]["tags"]
    assert client.generation_updates[-1]["metadata"]["correlation_id"] == "req-deadbeef"
