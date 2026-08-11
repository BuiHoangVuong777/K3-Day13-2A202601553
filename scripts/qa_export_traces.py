"""Xuất bằng chứng trace từ Langfuse API ra submission/evidence/.

Ảnh chụp màn hình Langfuse vẫn phải nộp, nhưng file này cho phép người chấm kiểm
chứng lại số liệu mà không cần đăng nhập: danh sách trace kèm metadata, và cây
span (waterfall) của một trace cụ thể.

    python scripts/qa_export_traces.py
    python scripts/qa_export_traces.py --limit 30 --trace-id <trace_id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio  # noqa: E402

EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    env.setdefault("LANGFUSE_HOST", env.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"))
    return env


ENV = load_env()
HOST = ENV["LANGFUSE_HOST"].rstrip("/")
AUTH = (ENV["LANGFUSE_PUBLIC_KEY"], ENV["LANGFUSE_SECRET_KEY"])


def fetch_traces(limit: int) -> list[dict]:
    with httpx.Client(timeout=60.0, auth=AUTH) as client:
        response = client.get(f"{HOST}/api/public/traces", params={"limit": limit})
        response.raise_for_status()
        return response.json().get("data", [])


def fetch_observations(trace_id: str) -> list[dict]:
    with httpx.Client(timeout=60.0, auth=AUTH) as client:
        response = client.get(
            f"{HOST}/api/public/observations", params={"traceId": trace_id, "limit": 100}
        )
        response.raise_for_status()
        return sorted(response.json().get("data", []), key=lambda o: o.get("startTime", ""))


def clean_metadata(metadata: dict | None) -> dict:
    """Bỏ phần resourceAttributes/scope do OTel tự thêm để bảng dễ đọc."""
    if not isinstance(metadata, dict):
        return {}
    return {k: v for k, v in metadata.items() if k not in {"resourceAttributes", "scope"}}


def render(traces: list[dict], waterfall_trace: dict, observations: list[dict]) -> str:
    lines = [
        "# Evidence trace trên Langfuse",
        "",
        f"- Host: `{HOST}`",
        f"- Số trace được liệt kê: **{len(traces)}**",
        "",
        "## Danh sách trace kèm metadata",
        "",
        "| # | Trace ID | Thời điểm (UTC) | Session | prompt_label | prompt_version | "
        "prompt_source | Correlation ID (tag) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for position, trace in enumerate(traces, start=1):
        metadata = clean_metadata(trace.get("metadata"))
        tags = trace.get("tags") or []
        correlation = next((tag for tag in tags if tag.startswith("req-")), "—")
        lines.append(
            f"| {position} | `{trace.get('id')}` | {str(trace.get('timestamp'))[:19]} | "
            f"`{trace.get('sessionId')}` | `{metadata.get('prompt_label')}` | "
            f"`{metadata.get('prompt_version')}` | `{metadata.get('prompt_source')}` | "
            f"`{correlation}` |"
        )

    lines += [
        "",
        "## Trace waterfall",
        "",
        f"- Trace ID: `{waterfall_trace.get('id')}`",
        f"- URL: {HOST}/project/{waterfall_trace.get('projectId', '')}/traces/{waterfall_trace.get('id')}",
        f"- Tags: `{waterfall_trace.get('tags')}`",
        "",
        "| Span | Kiểu | Bắt đầu (UTC) | Thời lượng (ms) | Ghi chú |",
        "|---|---|---|---|---|",
    ]
    for observation in observations:
        metadata = clean_metadata(observation.get("metadata"))
        note = metadata.get("component") or metadata.get("slowest_span") or ""
        # API trả latency theo giây; báo cáo dùng ms cho khớp với log và dashboard.
        latency_ms = round(float(observation.get("latency") or 0) * 1000)
        lines.append(
            f"| `{observation.get('name')}` | {observation.get('type')} | "
            f"{str(observation.get('startTime'))[11:23]} | {latency_ms} | {note} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--trace-id", help="Trace dùng để in waterfall; mặc định là trace mới nhất")
    args = parser.parse_args()

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    traces = fetch_traces(args.limit)
    if not traces:
        raise SystemExit("Langfuse chưa có trace nào. Chạy scripts/load_test.py trước.")

    target = next((t for t in traces if t.get("id") == args.trace_id), traces[0])
    observations = fetch_observations(target["id"])

    (EVIDENCE_DIR / "traces.json").write_text(
        json.dumps(
            {
                "traces": [
                    {
                        "id": trace.get("id"),
                        "timestamp": trace.get("timestamp"),
                        "sessionId": trace.get("sessionId"),
                        "tags": trace.get("tags"),
                        "metadata": clean_metadata(trace.get("metadata")),
                    }
                    for trace in traces
                ],
                "waterfall": {
                    "traceId": target.get("id"),
                    "observations": [
                        {
                            "name": observation.get("name"),
                            "type": observation.get("type"),
                            "startTime": observation.get("startTime"),
                            "endTime": observation.get("endTime"),
                            "latencyMs": round(float(observation.get("latency") or 0) * 1000),
                            "metadata": clean_metadata(observation.get("metadata")),
                        }
                        for observation in observations
                    ],
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = render(traces, target, observations)
    (EVIDENCE_DIR / "traces.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"Đã ghi {EVIDENCE_DIR / 'traces.md'} và traces.json")


if __name__ == "__main__":
    main()
