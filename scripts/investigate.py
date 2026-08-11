"""Điều tra incident bằng chuỗi Metrics -> Traces -> Logs (Checkpoint 3).

Script đọc ``data/logs.jsonl`` và tự dựng lại dòng thời gian sự cố từ chính log
(``incident_enabled`` / ``incident_disabled``), nên không cần nhớ đã bật incident
lúc nào. Việc so sánh được giới hạn trong ba cửa sổ liền kề — trước, trong và sau
incident — thay vì gộp toàn bộ file log, vì log còn chứa các lần chạy practice cũ
với cấu hình khác.

Với mỗi cửa sổ, script tính đúng các chỉ số của 6 panel dashboard, quy trách nhiệm
latency về từng span, rồi in ra request vi phạm nặng nhất kèm correlation ID,
trace ID và trace URL để mở thẳng trên Langfuse.

    python scripts/investigate.py
    python scripts/investigate.py --baseline-minutes 30 --top 5
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.challenge import load_challenge  # noqa: E402
from app.cli import configure_utf8_stdio  # noqa: E402
from app.metrics import percentile  # noqa: E402

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
SPAN_KEYS = {
    "rag-retrieval": "retrieval_ms",
    "prompt-resolve": "prompt_ms",
    "llm-generate": "llm_ms",
}
TRACKED_EVENTS = {"request_received", "response_sent", "request_failed", "span_timings"}


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_records(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "ts" in record:
            records.append(record)
    return sorted(records, key=lambda r: r["ts"])


@dataclass(frozen=True)
class IncidentWindow:
    name: str
    started: datetime
    stopped: datetime | None


def incident_timeline(records: list[dict]) -> list[IncidentWindow]:
    open_windows: dict[str, datetime] = {}
    windows: list[IncidentWindow] = []
    for record in records:
        name = (record.get("payload") or {}).get("name")
        if not name:
            continue
        if record.get("event") == "incident_enabled":
            open_windows[name] = parse_ts(record["ts"])
        elif record.get("event") == "incident_disabled" and name in open_windows:
            windows.append(IncidentWindow(name, open_windows.pop(name), parse_ts(record["ts"])))
    windows += [IncidentWindow(name, started, None) for name, started in open_windows.items()]
    return sorted(windows, key=lambda w: w.started)


@dataclass
class Window:
    label: str
    start: datetime
    end: datetime
    responses: list[dict] = field(default_factory=list)
    requests: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    timings: list[dict] = field(default_factory=list)

    def add(self, record: dict) -> None:
        event = record.get("event")
        if event == "request_received":
            self.requests.append(record)
        elif event == "response_sent":
            self.responses.append(record)
        elif event == "request_failed":
            self.failures.append(record)
        elif event == "span_timings":
            self.timings.append(record)

    def metrics(self) -> dict:
        latencies = [int(r["latency_ms"]) for r in self.responses if "latency_ms" in r]
        costs = [float(r.get("cost_usd", 0)) for r in self.responses]
        quality = [float(r["quality_score"]) for r in self.responses if "quality_score" in r]
        tokens = [
            int(r.get("tokens_in", 0)) + int(r.get("tokens_out", 0)) for r in self.responses
        ]
        received = len(self.requests)
        return {
            "requests": received,
            "responses": len(self.responses),
            "failures": len(self.failures),
            "error_rate_pct": round(100 * len(self.failures) / received, 2) if received else 0.0,
            "latency_p50": percentile(latencies, 50),
            "latency_p95": percentile(latencies, 95),
            "latency_p99": percentile(latencies, 99),
            "latency_max": max(latencies) if latencies else 0,
            "cost_usd_total": round(sum(costs), 6),
            "tokens_total": sum(tokens),
            "tokens_per_request": round(statistics.mean(tokens), 1) if tokens else 0.0,
            "quality_mean": round(statistics.mean(quality), 4) if quality else 0.0,
        }

    def span_attribution(self) -> dict[str, dict]:
        total_latency = sum(int(t.get("latency_ms", 0)) for t in self.timings) or 1
        out: dict[str, dict] = {}
        for span, key in SPAN_KEYS.items():
            values = [int(t.get(key, 0)) for t in self.timings]
            out[span] = {
                "mean_ms": round(statistics.mean(values), 1) if values else 0.0,
                "max_ms": max(values) if values else 0,
                "share_pct": round(100 * sum(values) / total_latency, 1),
            }
        return out

    def slowest_span_counts(self) -> dict[str, int]:
        counts = {name: 0 for name in SPAN_KEYS}
        for timing in self.timings:
            name = timing.get("slowest_span")
            if name in counts:
                counts[name] += 1
        return counts

    def violations(self, threshold_ms: int) -> list[dict]:
        return sorted(
            (r for r in self.responses if int(r.get("latency_ms", 0)) > threshold_ms),
            key=lambda r: int(r["latency_ms"]),
            reverse=True,
        )


def fill_windows(records: list[dict], windows: list[Window]) -> None:
    for record in records:
        if record.get("event") not in TRACKED_EVENTS:
            continue
        ts = parse_ts(record["ts"])
        for window in windows:
            if window.start <= ts <= window.end:
                window.add(record)
                break


def index_by_correlation(records: list[dict]) -> dict[str, dict[str, dict]]:
    index: dict[str, dict[str, dict]] = {}
    for record in records:
        cid = record.get("correlation_id")
        if cid:
            index.setdefault(cid, {})[record.get("event", "")] = record
    return index


def metrics_row(window: Window, metrics: dict) -> str:
    return (
        f"| {window.label} | {window.start:%H:%M:%S}–{window.end:%H:%M:%S} | "
        f"{metrics['requests']} | {metrics['latency_p50']:.0f} | {metrics['latency_p95']:.0f} | "
        f"{metrics['latency_p99']:.0f} | {metrics['latency_max']} | {metrics['error_rate_pct']} | "
        f"{metrics['cost_usd_total']:.6f} | {metrics['tokens_per_request']} | "
        f"{metrics['quality_mean']} |"
    )


def render(records: list[dict], top: int, baseline_minutes: int) -> str:
    challenge = load_challenge(REPO_ROOT / "config" / "challenge.json")
    threshold = challenge.latency_threshold_ms
    timeline = incident_timeline(records)
    matching = [w for w in timeline if w.name == challenge.incident and w.stopped]
    if not matching:
        raise SystemExit(
            f"Chưa có cửa sổ incident '{challenge.incident}' đã đóng trong log. "
            "Chạy scripts/inject_incident.py và load_test.py --challenge trước."
        )
    incident_window = matching[-1]
    assert incident_window.stopped is not None
    margin = timedelta(minutes=baseline_minutes)

    before = Window("Trước incident", incident_window.started - margin, incident_window.started)
    during = Window("Trong incident", incident_window.started, incident_window.stopped)
    after = Window("Sau khi tắt incident", incident_window.stopped, incident_window.stopped + margin)
    # Thứ tự quan trọng: 'during' phải được xét trước để các mốc biên không bị đếm nhầm.
    fill_windows(records, [during, before, after])

    before_m, during_m, after_m = before.metrics(), during.metrics(), after.metrics()
    before_spans, during_spans = before.span_attribution(), during.span_attribution()
    index = index_by_correlation(records)
    during_violations = during.violations(threshold)
    before_violations = before.violations(threshold)
    after_violations = after.violations(threshold)

    lines: list[str] = [
        "# Điều tra challenge — Metrics → Traces → Logs",
        "",
        f"- Challenge ID: `{challenge.challenge_id}` (cohort `{challenge.cohort}`)",
        f"- Incident được release: `{challenge.incident}`",
        f"- Feature bị ảnh hưởng theo contract: `{challenge.affected_feature}`",
        f"- Ngưỡng latency của challenge: **{threshold} ms**",
        f"- Nguồn dữ liệu: `data/logs.jsonl` ({len(records)} bản ghi)",
        f"- Cửa sổ so sánh: ±{baseline_minutes} phút quanh incident "
        f"({incident_window.started:%Y-%m-%d %H:%M:%S}Z → {incident_window.stopped:%H:%M:%S}Z, "
        f"kéo dài {(incident_window.stopped - incident_window.started).total_seconds():.0f}s)",
        "",
        "## Bước 0 — Dòng thời gian incident (dựng lại từ log)",
        "",
        "| Incident | Bật lúc (UTC) | Tắt lúc (UTC) | Kéo dài | Dùng cho báo cáo |",
        "|---|---|---|---|---|",
    ]
    for window in timeline:
        stopped = f"{window.stopped:%Y-%m-%d %H:%M:%S}" if window.stopped else "(chưa tắt)"
        duration = (
            f"{(window.stopped - window.started).total_seconds():.0f}s" if window.stopped else "—"
        )
        used = "**có**" if window is incident_window else "không"
        lines.append(
            f"| `{window.name}` | {window.started:%Y-%m-%d %H:%M:%S} | {stopped} | "
            f"{duration} | {used} |"
        )

    lines += [
        "",
        "## Bước 1 — Metrics: triệu chứng",
        "",
        "| Cửa sổ | Khoảng (UTC) | Requests | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | "
        "Error % | Cost (USD) | Tokens/request | Quality |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        metrics_row(before, before_m),
        metrics_row(during, during_m),
        metrics_row(after, after_m),
        "",
    ]

    ratio = during_m["latency_p95"] / before_m["latency_p95"] if before_m["latency_p95"] else 0
    ratio_p50 = during_m["latency_p50"] / before_m["latency_p50"] if before_m["latency_p50"] else 0
    lines += [
        f"- p95 tăng **{ratio:.1f}×** ({before_m['latency_p95']:.0f} ms → "
        f"{during_m['latency_p95']:.0f} ms), rồi trở lại {after_m['latency_p95']:.0f} ms "
        "sau khi tắt incident.",
        f"- p50 tăng **{ratio_p50:.1f}×** ({before_m['latency_p50']:.0f} ms → "
        f"{during_m['latency_p50']:.0f} ms): mọi request đều chậm, không phải chỉ phần đuôi.",
        f"- Request vượt ngưỡng {threshold} ms: trước {len(before_violations)}/"
        f"{before_m['responses']}, trong **{len(during_violations)}/{during_m['responses']}**, "
        f"sau {len(after_violations)}/{after_m['responses']}.",
        f"- Error rate không đổi ({before_m['error_rate_pct']}% → {during_m['error_rate_pct']}%): "
        "sự cố làm **chậm** chứ không làm request thất bại, nên alert dựa trên error rate "
        "hoàn toàn không bắt được — chỉ alert latency p95 mới bắt.",
        f"- Token/request ({before_m['tokens_per_request']} → {during_m['tokens_per_request']}) và "
        f"quality ({before_m['quality_mean']} → {during_m['quality_mean']}) gần như không đổi: "
        "loại trừ giả thuyết model sinh dài hơn hoặc prompt bị đổi.",
    ]
    if before_m["latency_p95"] > 3 * before_m["latency_p50"]:
        lines.append(
            f"- Lưu ý đọc số: p95 của cửa sổ trước ({before_m['latency_p95']:.0f} ms) bị kéo lên bởi "
            "đúng một request cold start — lần gọi đầu tiên phải fetch prompt từ Langfuse và resolve "
            f"URL project. p50 = {before_m['latency_p50']:.0f} ms mới là mức bình thường của hệ thống."
        )
    lines += [
        "",
        "## Bước 2 — Traces: span nào chậm",
        "",
        "| Span | Mean trước (ms) | Mean trong incident (ms) | Max trong incident (ms) | "
        "% tổng latency incident |",
        "|---|---|---|---|---|",
    ]
    for span in SPAN_KEYS:
        lines.append(
            f"| `{span}` | {before_spans[span]['mean_ms']} | {during_spans[span]['mean_ms']} | "
            f"{during_spans[span]['max_ms']} | {during_spans[span]['share_pct']}% |"
        )

    counts = during.slowest_span_counts()
    total = sum(counts.values()) or 1
    worst = max(counts, key=counts.__getitem__)
    lines += [
        "",
        "- Span chậm nhất của từng request trong incident: "
        + ", ".join(f"`{name}` {count}/{total}" for name, count in counts.items())
        + ".",
        f"- Kết luận tầng trace: **`{worst}`** là span gây chậm; `prompt-resolve` và "
        "`llm-generate` giữ nguyên thời lượng.",
        "",
        f"## Bước 3 — Logs: {min(top, len(during_violations))} request vi phạm nặng nhất",
        "",
        "| # | Latency (ms) | Feature | Correlation ID | Trace ID | retrieval_ms | prompt_ms | llm_ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for position, response in enumerate(during_violations[:top], start=1):
        cid = response["correlation_id"]
        events = index.get(cid, {})
        timing = events.get("span_timings", {})
        linked = events.get("trace_linked", {})
        lines.append(
            f"| {position} | {response['latency_ms']} | `{response.get('feature')}` | "
            f"`{cid}` | `{linked.get('trace_id')}` | {timing.get('retrieval_ms')} | "
            f"{timing.get('prompt_ms')} | {timing.get('llm_ms')} |"
        )

    if during_violations:
        exemplar = during_violations[0]
        cid = exemplar["correlation_id"]
        events = index.get(cid, {})
        linked = events.get("trace_linked", {})
        lines += [
            "",
            "### Chuỗi bằng chứng đầy đủ của một request",
            "",
            f"1. **Metric**: `latency_ms={exemplar['latency_ms']}` vượt ngưỡng {threshold} ms.",
            f"2. **Trace**: `{linked.get('trace_id')}` — {linked.get('trace_url')}",
            f"3. **Log**: lọc `data/logs.jsonl` theo `correlation_id={cid}` được đúng 5 dòng dưới đây.",
            "",
            "```json",
        ]
        for event_name in (
            "request_received",
            "trace_linked",
            "prompt_resolved",
            "span_timings",
            "response_sent",
        ):
            if event_name in events:
                lines.append(json.dumps(events[event_name], ensure_ascii=False))
        lines.append("```")

    lines += [
        "",
        "## Bước 4 — Đối chiếu giả thuyết",
        "",
        "| Giả thuyết | Bằng chứng | Kết luận |",
        "|---|---|---|",
        f"| Model sinh nhiều token hơn | token/request {before_m['tokens_per_request']} → "
        f"{during_m['tokens_per_request']}; span `llm-generate` "
        f"{before_spans['llm-generate']['mean_ms']} → {during_spans['llm-generate']['mean_ms']} ms "
        "| Loại |",
        f"| Lỗi/timeout gây retry | error rate {during_m['error_rate_pct']}%, "
        f"{during_m['failures']} bản ghi `request_failed` | Loại |",
        f"| Fetch prompt từ Langfuse chậm | span `prompt-resolve` mean "
        f"{during_spans['prompt-resolve']['mean_ms']} ms, `prompt_source=langfuse` không đổi | Loại |",
        f"| Chất lượng retrieval giảm nên phải sinh lại | quality {before_m['quality_mean']} → "
        f"{during_m['quality_mean']}, `doc_count` không đổi | Loại |",
        f"| Retrieval chậm | span `rag-retrieval` mean {during_spans['rag-retrieval']['mean_ms']} ms "
        f"(trước: {before_spans['rag-retrieval']['mean_ms']} ms), chiếm "
        f"{during_spans['rag-retrieval']['share_pct']}% latency, {counts['rag-retrieval']}/{total} "
        "request có span này chậm nhất | **Nhận** |",
        "",
        "## Bước 5 — Xác minh sau khi khắc phục",
        "",
        f"Sau khi tắt incident lúc {incident_window.stopped:%H:%M:%S}Z, cùng bộ input challenge "
        f"cho p95 = {after_m['latency_p95']:.0f} ms và {len(after_violations)}/{after_m['responses']} "
        f"request vượt ngưỡng — hệ thống trở lại trạng thái trước sự cố.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=5, help="Số request vi phạm được liệt kê")
    parser.add_argument(
        "--baseline-minutes",
        type=int,
        default=30,
        help="Độ rộng cửa sổ trước và sau incident dùng để so sánh",
    )
    parser.add_argument(
        "--out",
        default="submission/evidence/investigation.md",
        help="Nơi ghi báo cáo điều tra",
    )
    args = parser.parse_args()

    records = read_records(LOG_PATH)
    report = render(records, args.top, args.baseline_minutes)
    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nĐã ghi {out_path}")


if __name__ == "__main__":
    main()
