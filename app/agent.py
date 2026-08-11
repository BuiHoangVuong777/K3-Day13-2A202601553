from __future__ import annotations

import time
from dataclasses import dataclass

from structlog.contextvars import get_contextvars

from . import metrics
from .logging_config import get_logger
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .prompt_management import resolve_prompt
from .tracing import (
    current_trace_id,
    get_langfuse_client,
    observe,
    start_span,
    trace_url,
    tracing_enabled,
    update_span,
)

log = get_logger()


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float
    trace_id: str | None = None
    retrieval_ms: int = 0
    prompt_ms: int = 0
    llm_ms: int = 0


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @observe(as_type="generation", capture_input=False, capture_output=False)
    def run(self, user_id: str, feature: str, session_id: str, message: str) -> AgentResult:
        started = time.perf_counter()
        langfuse_client = get_langfuse_client()
        correlation_id = get_contextvars().get("correlation_id", "MISSING")
        trace_id = current_trace_id(langfuse_client)

        # Nối 3 tầng observability: log line này là cầu nối correlation_id -> trace_id.
        log.info(
            "trace_linked",
            service="agent",
            trace_id=trace_id,
            trace_url=trace_url(trace_id),
        )

        docs, retrieval_ms = self._retrieve_docs(
            langfuse_client, message=message, feature=feature, correlation_id=correlation_id
        )

        prompt_started = time.perf_counter()
        with start_span(langfuse_client, name="prompt-resolve") as span:
            prompt = resolve_prompt(
                langfuse_client,
                feature=feature,
                docs=docs,
                message=message,
                enabled=tracing_enabled(),
            )
            prompt_ms = int((time.perf_counter() - prompt_started) * 1000)
            update_span(
                span,
                output={"prompt_version": prompt.version, "prompt_source": prompt.source},
                metadata={
                    "component": "prompt_management",
                    "correlation_id": correlation_id,
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                    "prompt_version": prompt.version,
                    "prompt_source": prompt.source,
                    "prompt_fetch_error": prompt.fetch_error,
                    "duration_ms": prompt_ms,
                },
            )

        # Version prompt phải truy được từ log, không chỉ từ Langfuse UI.
        log.info(
            "prompt_resolved",
            service="agent",
            trace_id=trace_id,
            prompt_name=prompt.name,
            prompt_label=prompt.label,
            prompt_version=prompt.version,
            prompt_source=prompt.source,
            prompt_fetch_error=prompt.fetch_error,
        )

        llm_started = time.perf_counter()
        with start_span(
            langfuse_client, name="llm-generate", input={"prompt_chars": len(prompt.text)}
        ) as span:
            response = self.llm.generate(prompt.text)
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            update_span(
                span,
                output={"answer_preview": summarize_text(response.text)},
                metadata={
                    "component": "mock_llm",
                    "correlation_id": correlation_id,
                    "model": self.model,
                    "tokens_in": response.usage.input_tokens,
                    "tokens_out": response.usage.output_tokens,
                    "duration_ms": llm_ms,
                },
            )

        quality_score = self._heuristic_quality(message, response.text, docs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost_usd = self._estimate_cost(response.usage.input_tokens, response.usage.output_tokens)
        span_durations = {
            "rag-retrieval": retrieval_ms,
            "prompt-resolve": prompt_ms,
            "llm-generate": llm_ms,
        }
        slowest_span = max(span_durations, key=span_durations.__getitem__)

        langfuse_client.update_current_trace(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, self.model, correlation_id],
            metadata={
                "prompt_name": prompt.name,
                "prompt_label": prompt.label,
                "prompt_version": prompt.version,
                "prompt_source": prompt.source,
            },
        )
        langfuse_client.update_current_generation(
            model=self.model,
            metadata={
                "doc_count": len(docs),
                "query_preview": summarize_text(message),
                "prompt_name": prompt.name,
                "prompt_label": prompt.label,
                "prompt_version": prompt.version,
                "prompt_source": prompt.source,
                "prompt_fetch_error": prompt.fetch_error,
                "correlation_id": correlation_id,
                "retrieval_ms": retrieval_ms,
                "prompt_ms": prompt_ms,
                "llm_ms": llm_ms,
                "slowest_span": slowest_span,
            },
            usage_details={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
            cost_details={"total": cost_usd},
            prompt=prompt.managed_prompt,
        )

        metrics.record_request(
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        # Span breakdown nằm trong log để chứng minh root cause mà không cần mở UI.
        log.info(
            "span_timings",
            service="agent",
            trace_id=trace_id,
            latency_ms=latency_ms,
            retrieval_ms=retrieval_ms,
            prompt_ms=prompt_ms,
            llm_ms=llm_ms,
            slowest_span=slowest_span,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
            trace_id=trace_id,
            retrieval_ms=retrieval_ms,
            prompt_ms=prompt_ms,
            llm_ms=llm_ms,
        )

    def _retrieve_docs(
        self, langfuse_client, *, message: str, feature: str, correlation_id: str
    ) -> tuple[list[str], int]:
        started = time.perf_counter()
        with start_span(
            langfuse_client,
            name="rag-retrieval",
            input={"feature": feature, "query_preview": summarize_text(message)},
        ) as span:
            try:
                docs = retrieve(message)
            except Exception as exc:
                update_span(
                    span,
                    level="ERROR",
                    status_message=type(exc).__name__,
                    metadata={
                        "component": "mock_rag",
                        "correlation_id": correlation_id,
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                    },
                )
                raise
            duration_ms = int((time.perf_counter() - started) * 1000)
            update_span(
                span,
                output={"doc_count": len(docs)},
                metadata={
                    "component": "mock_rag",
                    "correlation_id": correlation_id,
                    "doc_count": len(docs),
                    "duration_ms": duration_ms,
                },
            )
        return docs, duration_ms

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
