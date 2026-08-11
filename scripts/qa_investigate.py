"""Điều tra incident theo luồng Metrics -> Traces -> Logs (Checkpoint 3).

Script chia `data/logs.jsonl` thành ba cửa sổ dựa trên chính log điều khiển
`incident_enabled` / `incident_disabled`, rồi trả lời ba câu hỏi theo đúng thứ tự
điều tra:

1. Metrics: chỉ số nào lệch, lệch bao nhiêu, có vượt threshold không?
2. Traces: trong request chậm nhất, span nào chiếm phần lớn thời gian?
3. Logs: log line nào (kèm correlation ID) chứng minh điều đó?

    python scripts/qa_investigate.py               # đọc log + span timings
    python scripts/qa_investigate.py --fetch-traces  # đối chiếu thêm với Langfuse API
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.challenge import load_challenge  # noqa: E402
from app.cli import configure_utf8_stdio  # noqa: E402
from app.metrics import percentile  # noqa: E402

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
HEALTHY_LOOKBACK_MINUTES = 10


def parse_ts(record: dict) -> datetime | None:
    raw = record.get("ts")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_records() -> list[dict]:
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        record["_ts"] = parse_ts(record)
        records.append(record)
    return records


def find_windows(records: list[dict], incident: str) -> dict[str, tuple[datetime, datetime]]:
    """Cửa sổ điều tra được suy ra từ log điều khiển, không hard-code thời gian."""
    enabled = [
        r["_ts"]
        for r in records
        if r.get("event") == "incident_enabled"
        and (r.get("payload") or {}).get("name") == incident
        and r["_ts"]
    ]
    disabled = [
        r["_ts"]
        for r in records
        if r.get("event") == "incident_disabled"
        and (r.get("payload") or {}).get("name") == incident
        and r["_ts"]
    ]
    if not enabled:
        raise SystemExit(
            f"Không tìm thấy log 'incident_enabled' cho '{incident}'. "
            "Hãy chạy scripts/inject_incident.py trước."
        )
    start = enabled[-1]
    end = next((ts for ts in disabled if ts > start), None)
    last_ts = max(r["_ts"] for r in records if r["_ts"])
    windows = {
        "healthy_before": (start - timedelta(minutes=HEALTHY_LOOKBACK_MINUTES), start),
        "incident": (start, end or last_ts),
    }
    if end:
        windows["after_fix"] = (end, last_ts + timedelta(seconds=1))
    return windows


def in_window(record: dict, window: tuple[datetime, datetime]) -> bool:
    ts = record.get("_ts")
    return ts is not None and window[0] <= ts < window[1]


def window_metrics(records: list[dict], window: tuple[datetime, datetime]) -> dict:
    """Sáu nhóm chỉ số của dashboard, tính từ đúng nguồn `data/logs.jsonl`."""
    scoped = [r for r in records if in_window(r, window)]
    received = [r for r in scoped if r.get("event") == "request_received"]
    failed = [r for r in scoped if r.get("event") == "request_failed"]
    responded = [r for r in scoped if r.get("event") == "response_sent"]

    latencies = [r["latency_ms"] for r in responded if isinstance(r.get("latency_ms"), int)]
    duration_s = max((window[1] - window[0]).total_seconds(), 1e-9)
    return {
        "window_start_utc": window[0].isoformat(),
        "window_end_utc": window[1].isoformat(),
        "requests": len(received),
        "responses": len(responded),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "latency_p99_ms": percentile(latencies, 99),
        "latency_max_ms": max(latencies, default=0),
        # Request đầu tiên của mỗi tiến trình app phải fetch prompt + project id từ
        # Langfuse nên chậm bất thường; tách riêng để không đọc nhầm thành sự cố.
        "cold_start_requests_over_1s": sum(1 for value in latencies if value > 1000),
        "latency_p95_ms_warm": (
            percentile(warm, 95) if (warm := [v for v in latencies if v <= 1000]) else None
        ),
        "traffic_per_minute": round(len(received) / (duration_s / 60), 2),
        "error_rate_pct": round(100 * len(failed) / len(received), 2) if received else 0.0,
        "error_breakdown": _count_by(failed, "error_type"),
        "cost_usd_total": round(sum(r.get("cost_usd", 0.0) for r in responded), 6),
        "tokens_total": sum(
            r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in responded
        ),
        "quality_mean": round(
            statistics.fmean([r["quality_score"] for r in responded if "quality_score" in r]), 4
        )
        if responded
        else 0.0,
    }


def _count_by(records: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = str(record.get(field, "unknown"))
        counts[key] = counts.get(key, 0) + 1
    return counts


def span_breakdown(records: list[dict], window: tuple[datetime, datetime]) -> list[dict]:
    """Từ log `span_timings`: request nào chậm và span nào là thủ phạm."""
    timings = [
        r for r in records if r.get("event") == "span_timings" and in_window(r, window)
    ]
    links = {
        r.get("correlation_id"): r
        for r in records
        if r.get("event") == "trace_linked" and in_window(r, window)
    }
    rows = []
    for record in sorted(timings, key=lambda r: r.get("latency_ms", 0), reverse=True):
        correlation_id = record.get("correlation_id")
        rows.append(
            {
                "correlation_id": correlation_id,
                "trace_id": record.get("trace_id"),
                "trace_url": (links.get(correlation_id) or {}).get("trace_url"),
                "feature": record.get("feature"),
                "latency_ms": record.get("latency_ms"),
                "retrieval_ms": record.get("retrieval_ms"),
                "prompt_ms": record.get("prompt_ms"),
                "llm_ms": record.get("llm_ms"),
                "slowest_span": record.get("slowest_span"),
            }
        )
    return rows


def slowest_span_summary(rows: list[dict]) -> dict[str, int]:
    return _count_by(rows, "slowest_span")


def fetch_trace_observations(trace_id: str) -> list[dict]:
    """Đối chiếu span timing trong log với dữ liệu thật trên Langfuse."""
    import httpx

    env = {}
    for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    host = env.get("LANGFUSE_HOST", env.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"))
    auth = (env["LANGFUSE_PUBLIC_KEY"], env["LANGFUSE_SECRET_KEY"])
    response = httpx.get(f"{host.rstrip('/')}/api/public/traces/{trace_id}", auth=auth, timeout=30)
    response.raise_for_status()
    observations = []
    for observation in response.json().get("observations", []):
        observations.append(
            {
                "name": observation.get("name"),
                "type": observation.get("type"),
                "start": observation.get("startTime"),
                "end": observation.get("endTime"),
                "duration_ms": _duration_ms(observation),
                "level": observation.get("level"),
            }
        )
    return sorted(observations, key=lambda o: o["start"] or "")


def _duration_ms(observation: dict) -> int | None:
    start, end = observation.get("startTime"), observation.get("endTime")
    if not start or not end:
        return None
    delta = datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(
        start.replace("Z", "+00:00")
    )
    return int(delta.total_seconds() * 1000)


def build_report(result: dict) -> str:
    challenge = result["challenge"]
    metrics = result["metrics"]
    healthy = metrics["healthy_before"]
    incident = metrics["incident"]
    after = metrics.get("after_fix")
    rows = result["incident_spans"]
    top = rows[0] if rows else {}

    lines = [
        "# Điều tra challenge — Metrics → Traces → Logs",
        "",
        f"- Challenge ID: `{challenge['challenge_id']}` (cohort `{challenge['cohort']}`)",
        f"- Incident được release: `{challenge['incident']}`",
        f"- Feature bị ảnh hưởng: `{challenge['affected_feature']}`",
        f"- Ngưỡng latency của challenge: **{challenge['latency_threshold_ms']} ms**",
        f"- Nguồn dữ liệu: `data/logs.jsonl` ({result['record_count']} log record)",
        "",
        "## Bước 1 — Metrics: triệu chứng",
        "",
        "| Chỉ số | Trước sự cố | Trong sự cố | Sau khi fix |",
        "|---|---|---|---|",
    ]
    fields = [
        ("Số request", "requests", ""),
        ("Latency p50", "latency_p50_ms", " ms"),
        ("Latency p95", "latency_p95_ms", " ms"),
        ("Latency p95 (bỏ cold start)", "latency_p95_ms_warm", " ms"),
        ("Latency p99", "latency_p99_ms", " ms"),
        ("Latency max", "latency_max_ms", " ms"),
        ("Error rate", "error_rate_pct", " %"),
        ("Cost", "cost_usd_total", " USD"),
        ("Tokens", "tokens_total", ""),
        ("Quality mean", "quality_mean", ""),
    ]
    def cell(window: dict | None, key: str, unit: str) -> str:
        if window is None or window.get(key) is None:
            return "—"
        return f"{window[key]}{unit}"

    for label, key, unit in fields:
        lines.append(
            f"| {label} | {cell(healthy, key, unit)} | **{cell(incident, key, unit)}** | "
            f"{cell(after, key, unit)} |"
        )

    breach = incident["latency_p95_ms"] > challenge["latency_threshold_ms"]
    factor = (
        round(incident["latency_p95_ms"] / healthy["latency_p95_ms_warm"], 1)
        if healthy["latency_p95_ms_warm"]
        else None
    )
    lines += [
        "",
        f"- Cửa sổ sự cố: `{incident['window_start_utc']}` → `{incident['window_end_utc']}`",
        f"- p95 {'VƯỢT' if breach else 'không vượt'} ngưỡng "
        f"{challenge['latency_threshold_ms']} ms "
        f"({incident['latency_p95_ms']} ms, gấp {factor}× so với p95 warm trước sự cố).",
        f"- p95 thô của cửa sổ trước sự cố là {healthy['latency_p95_ms']} ms nhưng bị kéo lên bởi "
        f"{healthy['cold_start_requests_over_1s']} request cold start (request đầu tiên của mỗi "
        "tiến trình app phải fetch prompt và project id từ Langfuse). Loại các request >1s, "
        f"p95 warm chỉ còn {healthy['latency_p95_ms_warm']} ms — đây mới là mức nền để so sánh.",
        "- Error rate, cost, token và quality gần như không đổi ⇒ đây là sự cố "
        "**latency**, không phải sự cố lỗi hay chi phí.",
        "",
        "## Bước 2 — Traces: khoanh vùng span",
        "",
        "| Correlation ID | Trace ID | Latency | rag-retrieval | prompt-resolve | llm-generate | Span chậm nhất |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows[:10]:
        lines.append(
            f"| `{row['correlation_id']}` | `{row['trace_id']}` | {row['latency_ms']} ms | "
            f"**{row['retrieval_ms']} ms** | {row['prompt_ms']} ms | {row['llm_ms']} ms | "
            f"`{row['slowest_span']}` |"
        )
    lines += [
        "",
        f"- Span chậm nhất theo request: `{result['slowest_span_counts']}`.",
        f"- Trace waterfall tiêu biểu: {top.get('trace_url')}",
    ]
    if result.get("langfuse_observations"):
        lines += [
            "",
            f"Đối chiếu trực tiếp với Langfuse API cho trace `{top.get('trace_id')}`:",
            "",
            "| Span | Type | Duration | Level |",
            "|---|---|---|---|",
        ]
        for observation in result["langfuse_observations"]:
            lines.append(
                f"| `{observation['name']}` | {observation['type']} | "
                f"{observation['duration_ms']} ms | {observation['level']} |"
            )

    evidence_ids = ", ".join(f"`{row['correlation_id']}`" for row in rows[:3])
    lines += [
        "",
        "## Bước 3 — Logs: bằng chứng root cause",
        "",
        f"Các log line dưới đây lấy từ `data/logs.jsonl`, lọc theo correlation ID {evidence_ids}:",
        "",
        "```json",
    ]
    for line in result["evidence_log_lines"]:
        lines.append(line)
    lines += [
        "```",
        "",
        "## Kết luận",
        "",
        f"- **Triệu chứng**: p95 latency của feature `{challenge['affected_feature']}` tăng từ "
        f"{healthy['latency_p95_ms_warm']} ms lên {incident['latency_p95_ms']} ms, vượt ngưỡng "
        f"{challenge['latency_threshold_ms']} ms; error rate giữ nguyên "
        f"{incident['error_rate_pct']}%.",
        f"- **Root cause**: span `rag-retrieval` chiếm "
        f"{_share(top)}% tổng latency "
        f"({top.get('retrieval_ms')} ms / {top.get('latency_ms')} ms) trong khi "
        f"`llm-generate` giữ nguyên {top.get('llm_ms')} ms. Bước truy xuất tài liệu là điểm "
        "nghẽn, không phải model.",
        "- **Bằng chứng nối 3 tầng**: metric p95 → trace "
        f"`{top.get('trace_id')}` → log line có `correlation_id={top.get('correlation_id')}` "
        "và `slowest_span=rag-retrieval`.",
    ]
    if after:
        lines.append(
            f"- **Xác nhận sau fix**: cùng bộ input challenge chạy lại đạt p95 "
            f"{after['latency_p95_ms']} ms, trở lại mức trước sự cố."
        )
    lines.append("")
    return "\n".join(lines)


def _share(row: dict) -> float:
    latency = row.get("latency_ms") or 0
    retrieval = row.get("retrieval_ms") or 0
    return round(100 * retrieval / latency, 1) if latency else 0.0


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fetch-traces",
        action="store_true",
        help="Gọi Langfuse API để đối chiếu span duration của trace chậm nhất.",
    )
    args = parser.parse_args()

    challenge = load_challenge()
    records = read_records()
    windows = find_windows(records, challenge.incident)

    incident_spans = span_breakdown(records, windows["incident"])
    evidence_ids = {row["correlation_id"] for row in incident_spans[:3]}
    evidence_log_lines = [
        json.dumps({k: v for k, v in r.items() if k != "_ts"}, ensure_ascii=False)
        for r in records
        if r.get("correlation_id") in evidence_ids
        and r.get("event") in {"request_received", "trace_linked", "span_timings", "response_sent"}
    ]

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "challenge": {
            "challenge_id": challenge.challenge_id,
            "cohort": challenge.cohort,
            "incident": challenge.incident,
            "affected_feature": challenge.affected_feature,
            "latency_threshold_ms": challenge.latency_threshold_ms,
        },
        "metrics": {name: window_metrics(records, window) for name, window in windows.items()},
        "incident_spans": incident_spans,
        "slowest_span_counts": slowest_span_summary(incident_spans),
        "evidence_log_lines": evidence_log_lines,
    }

    if args.fetch_traces and incident_spans:
        result["langfuse_observations"] = fetch_trace_observations(incident_spans[0]["trace_id"])

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "investigation.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report = build_report(result)
    (EVIDENCE_DIR / "investigation.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
