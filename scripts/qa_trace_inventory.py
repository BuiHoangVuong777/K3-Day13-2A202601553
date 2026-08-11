"""Xuất danh sách trace trên Langfuse kèm metadata (Checkpoint 2).

Evidence yêu cầu "tối thiểu 10 traces có metadata". Script gọi thẳng Langfuse API
để không phải tin vào ảnh chụp màn hình: mỗi dòng có trace ID, session, tag,
prompt name/label/version và span chậm nhất.

    python scripts/qa_trace_inventory.py --limit 30
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio  # noqa: E402

EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
REQUIRED_METADATA = ("prompt_name", "prompt_label", "prompt_version", "prompt_source")


def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--hours", type=int, default=6, help="Chỉ lấy trace trong N giờ gần nhất.")
    args = parser.parse_args()

    env = read_env()
    host = env.get("LANGFUSE_HOST", env.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"))
    auth = (env["LANGFUSE_PUBLIC_KEY"], env["LANGFUSE_SECRET_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(hours=args.hours)).isoformat()

    response = httpx.get(
        f"{host.rstrip('/')}/api/public/traces",
        params={"limit": args.limit, "fromTimestamp": since},
        auth=auth,
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()

    rows = []
    for trace in payload.get("data", []):
        metadata = trace.get("metadata") or {}
        rows.append(
            {
                "trace_id": trace.get("id"),
                "timestamp": trace.get("timestamp"),
                "name": trace.get("name"),
                "session_id": trace.get("sessionId"),
                "user_id_hash": trace.get("userId"),
                "tags": trace.get("tags") or [],
                "latency_s": trace.get("latency"),
                "total_cost_usd": trace.get("totalCost"),
                "observations": len(trace.get("observations") or []),
                "prompt_name": metadata.get("prompt_name"),
                "prompt_label": metadata.get("prompt_label"),
                "prompt_version": metadata.get("prompt_version"),
                "prompt_source": metadata.get("prompt_source"),
                "has_required_metadata": all(metadata.get(key) is not None for key in REQUIRED_METADATA),
            }
        )

    complete = [row for row in rows if row["has_required_metadata"]]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "window_hours": args.hours,
        "total_traces_in_window": payload.get("meta", {}).get("totalItems"),
        "traces_listed": len(rows),
        "traces_with_full_prompt_metadata": len(complete),
        "traces": rows,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "traces_inventory.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Danh sách trace trên Langfuse",
        "",
        f"- Host: `{host}`",
        f"- Cửa sổ: {args.hours} giờ gần nhất (tính tới `{summary['generated_at_utc']}`)",
        f"- Tổng trace trong cửa sổ: **{summary['total_traces_in_window']}**",
        f"- Trace liệt kê ở đây: **{len(rows)}**, trong đó "
        f"**{len(complete)}** trace có đủ metadata prompt "
        f"(`{'`, `'.join(REQUIRED_METADATA)}`)",
        "",
        "| # | Trace ID | Session | Prompt | Label | Ver | Spans | Latency | Cost (USD) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(rows, start=1):
        latency = f"{row['latency_s']:.3f}s" if isinstance(row["latency_s"], (int, float)) else "—"
        cost = f"{row['total_cost_usd']:.6f}" if isinstance(row["total_cost_usd"], (int, float)) else "—"
        lines.append(
            f"| {index} | `{row['trace_id']}` | `{row['session_id']}` | "
            f"`{row['prompt_name']}` | `{row['prompt_label']}` | `{row['prompt_version']}` | "
            f"{row['observations']} | {latency} | {cost} |"
        )
    lines.append("")
    (EVIDENCE_DIR / "traces_inventory.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines[:8]))
    print(f"... {len(rows)} dòng, đã ghi {EVIDENCE_DIR / 'traces_inventory.md'}")


if __name__ == "__main__":
    main()
