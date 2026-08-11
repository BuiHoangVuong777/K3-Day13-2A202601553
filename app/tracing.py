from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

try:
    from langfuse import get_client, observe

    LANGFUSE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - chỉ dùng khi chưa cài requirements
    LANGFUSE_SDK_AVAILABLE = False

    def observe(*args: Any, **kwargs: Any):
        def decorator(func):
            return func

        return decorator

    class _DummyClient:
        def update_current_trace(self, **kwargs: Any) -> None:
            return None

        def update_current_generation(self, **kwargs: Any) -> None:
            return None

    def get_client():
        return _DummyClient()


def get_langfuse_client():
    return get_client()


def tracing_enabled() -> bool:
    return LANGFUSE_SDK_AVAILABLE and bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )


@contextmanager
def start_span(client: Any, name: str, **kwargs: Any) -> Iterator[Any]:
    """Mở một child span dưới observation đang active.

    Trả về ``None`` khi client không hỗ trợ span (fake client trong test hoặc
    khi chưa cài Langfuse SDK), nhờ vậy agent luôn chạy được mà không cần
    kiểm tra tracing ở từng call site.
    """
    starter = getattr(client, "start_as_current_span", None)
    if starter is None:
        yield None
        return
    with starter(name=name, **kwargs) as span:
        yield span


def update_span(span: Any, **kwargs: Any) -> None:
    if span is None:
        return
    updater = getattr(span, "update", None)
    if updater is None:
        return
    updater(**kwargs)


def current_trace_id(client: Any) -> str | None:
    """ID của trace đang chạy; dùng để nối log JSON với trace trên Langfuse."""
    getter = getattr(client, "get_current_trace_id", None)
    if getter is None:
        return None
    try:
        return getter()
    except Exception:  # pragma: no cover - không để tracing làm hỏng request
        return None


_TRACE_URL_PREFIX: str | None = None


def trace_url(trace_id: str | None) -> str | None:
    """URL trace trên Langfuse UI để dán thẳng vào report.

    ``Langfuse.get_trace_url()`` gọi API project mỗi lần khi được gọi bên trong
    một span đang active (~250ms/request), nên phần cố định của URL được resolve
    một lần rồi cache lại; các request sau chỉ nối chuỗi.
    """
    global _TRACE_URL_PREFIX
    if not trace_id:
        return None
    if _TRACE_URL_PREFIX is None:
        try:
            resolved = get_client().get_trace_url(trace_id=trace_id)
        except Exception:  # pragma: no cover - URL chỉ là tiện ích cho evidence
            return None
        if not resolved:
            return None
        _TRACE_URL_PREFIX = resolved.rsplit("/", 1)[0] + "/"
    return _TRACE_URL_PREFIX + trace_id
