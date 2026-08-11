"""QA driver cho prompt versioning (Checkpoint 2).

Script chạy đúng 6 bước trong docs/PROMPT_VERSIONING.md và thu evidence tự động:

1. Bảo đảm prompt ``day13-chat`` có version 1 (``baseline``) và version 2 (``candidate``).
2. Chụp trạng thái label trước khi thao tác.
3. Chạy cùng một input với ``LANGFUSE_PROMPT_LABEL=baseline`` rồi ``candidate``.
4. Đổi label ``production`` sang version 2, chạy lại một request.
5. Rollback ``production`` về version 1, chạy lại một request.
6. Ghi ``submission/evidence/prompt_versions.json`` và ``prompt_versions.md``.

Mỗi lần đổi label, app được khởi động lại vì ``LANGFUSE_PROMPT_LABEL`` được đọc
từ môi trường, đúng như khi deploy thật.

    python scripts/qa_prompt_versions.py
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio  # noqa: E402

PORT = 8100
BASE_URL = f"http://127.0.0.1:{PORT}"
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
PROMPT_NAME = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")
PROBE_MESSAGE = "What is your refund policy?"
EXPORT_WAIT_SECONDS = 9

PROMPT_V1 = (
    "Feature={{feature}}\n"
    "Docs={{docs}}\n"
    "Question={{message}}\n\n"
    "Answer the user's question clearly using the provided documents."
)
PROMPT_V2 = PROMPT_V1 + "\nKeep the response concise and structured."


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
AUTH = (ENV["LANGFUSE_PUBLIC_KEY"], ENV["LANGFUSE_SECRET_KEY"])
HOST = ENV["LANGFUSE_HOST"].rstrip("/")


# --------------------------------------------------------------------------- #
# Langfuse prompt API
# --------------------------------------------------------------------------- #
def with_retry(description: str, action, attempts: int = 5):
    """Langfuse Cloud thỉnh thoảng timeout TLS; thao tác label không được bỏ dở."""
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as exc:
            if attempt == attempts:
                raise
            print(f"[retry] {description} lỗi {type(exc).__name__}, thử lại ({attempt}/{attempts})")
            time.sleep(3 * attempt)


def prompt_state() -> dict[str, list[str]]:
    """{version: labels} của mọi version hiện có trên Langfuse."""
    state: dict[str, list[str]] = {}
    with httpx.Client(timeout=30.0, auth=AUTH) as client:
        for version in range(1, 11):
            response = with_retry(
                f"đọc {PROMPT_NAME} v{version}",
                lambda v=version: client.get(
                    f"{HOST}/api/public/v2/prompts/{PROMPT_NAME}", params={"version": v}
                ),
            )
            if response.status_code == 404:
                break
            response.raise_for_status()
            state[f"v{version}"] = sorted(response.json().get("labels", []))
    return state


def ensure_prompt_versions() -> None:
    from langfuse import get_client

    for key, value in ENV.items():
        os.environ[key] = value
    client = get_client()
    state = prompt_state()
    if "v1" not in state:
        client.create_prompt(
            name=PROMPT_NAME,
            prompt=PROMPT_V1,
            type="text",
            labels=["production", "baseline"],
            commit_message="v1 baseline",
        )
        print(f"[prompt] tạo mới {PROMPT_NAME} v1 (production, baseline)")
    if "v2" not in state:
        client.create_prompt(
            name=PROMPT_NAME,
            prompt=PROMPT_V2,
            type="text",
            labels=["candidate"],
            commit_message="v2 candidate: câu trả lời ngắn và có cấu trúc",
        )
        print(f"[prompt] tạo mới {PROMPT_NAME} v2 (candidate)")


def move_label(version: int, label: str) -> None:
    from langfuse import get_client

    with_retry(
        f"gán label '{label}' -> v{version}",
        lambda: get_client().update_prompt(
            name=PROMPT_NAME, version=version, new_labels=[label]
        ),
    )
    print(f"[prompt] gán label '{label}' -> v{version}")


# --------------------------------------------------------------------------- #
# App process
# --------------------------------------------------------------------------- #
class AppProcess:
    """Chạy uvicorn với một LANGFUSE_PROMPT_LABEL cụ thể rồi tắt sạch."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.process: subprocess.Popen | None = None

    def __enter__(self) -> AppProcess:
        env = dict(ENV)
        env["LANGFUSE_PROMPT_LABEL"] = self.label
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", str(PORT)],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                if httpx.get(f"{BASE_URL}/health", timeout=2.0).json().get("ok"):
                    print(f"[app ] sẵn sàng với label={self.label}")
                    return self
            except Exception:
                time.sleep(0.5)
        raise RuntimeError(f"app không khởi động được với label={self.label}")

    def __exit__(self, *exc_info) -> None:
        assert self.process is not None
        # BatchSpanProcessor của OTel đẩy batch mỗi 5s và tiến trình bị tắt cứng trên
        # Windows sẽ không kịp flush, nên phải chờ qua ít nhất một chu kỳ export.
        time.sleep(EXPORT_WAIT_SECONDS)
        try:
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
            self.process.wait(timeout=20)
        except Exception:
            self.process.kill()
        print(f"[app ] đã tắt (label={self.label})")


def read_agent_events(correlation_id: str) -> dict[str, dict]:
    events: dict[str, dict] = {}
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("correlation_id") == correlation_id:
            events[record.get("event", "")] = record
    return events


def probe(step: str, label: str) -> dict:
    """Gửi đúng một request và thu correlation_id -> trace_id -> prompt version."""
    correlation_id = f"req-prompt-{step}"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{BASE_URL}/chat",
            headers={"x-request-id": correlation_id},
            json={
                "user_id": "qa-prompt-versioning",
                "session_id": f"prompt-{step}",
                "feature": "refund",
                "message": PROBE_MESSAGE,
            },
        )
    response.raise_for_status()
    time.sleep(0.5)
    events = read_agent_events(correlation_id)
    resolved = events.get("prompt_resolved", {})
    linked = events.get("trace_linked", {})
    result = {
        "step": step,
        "env_label": label,
        "correlation_id": correlation_id,
        "trace_id": linked.get("trace_id"),
        "trace_url": linked.get("trace_url"),
        "prompt_name": resolved.get("prompt_name"),
        "prompt_label": resolved.get("prompt_label"),
        "prompt_version": resolved.get("prompt_version"),
        "prompt_source": resolved.get("prompt_source"),
        "latency_ms": response.json().get("latency_ms"),
    }
    print(
        f"[run ] {step:<18} label={result['prompt_label']:<10} "
        f"version={result['prompt_version']:<8} source={result['prompt_source']:<14} "
        f"trace={result['trace_id']}"
    )
    return result


def run_step(step: str, label: str) -> dict:
    with AppProcess(label):
        return probe(step, label)


def verify_ingested(steps: list[dict], timeout_seconds: int = 90) -> None:
    """Trace chỉ là bằng chứng khi thật sự có trên Langfuse, không chỉ có trong log."""
    deadline = time.time() + timeout_seconds
    pending = {step["trace_id"]: step for step in steps if step.get("trace_id")}
    with httpx.Client(timeout=30.0, auth=AUTH) as client:
        while pending and time.time() < deadline:
            for trace_id in list(pending):
                response = client.get(f"{HOST}/api/public/traces/{trace_id}")
                if response.status_code == 200:
                    step = pending.pop(trace_id)
                    step["ingested"] = True
                    metadata = response.json().get("metadata") or {}
                    step["trace_metadata_version"] = metadata.get("prompt_version")
                    step["trace_metadata_label"] = metadata.get("prompt_label")
                    print(f"[check] trace {step['step']} đã lên Langfuse")
            if pending:
                time.sleep(5)
    for step in pending.values():
        step["ingested"] = False
        print(f"[check] CẢNH BÁO: trace {step['step']} ({step['trace_id']}) chưa lên Langfuse")


# --------------------------------------------------------------------------- #
def main() -> None:
    configure_utf8_stdio()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    ensure_prompt_versions()

    evidence: dict = {"prompt_name": PROMPT_NAME, "probe_message": PROBE_MESSAGE, "steps": []}

    evidence["labels_before"] = prompt_state()
    print(f"[state] trước khi thao tác: {evidence['labels_before']}")

    evidence["steps"].append(run_step("baseline", "baseline"))
    evidence["steps"].append(run_step("candidate", "candidate"))

    move_label(2, "production")
    evidence["labels_after_promote"] = prompt_state()
    print(f"[state] sau khi promote:    {evidence['labels_after_promote']}")
    evidence["steps"].append(run_step("production-v2", "production"))

    move_label(1, "production")
    evidence["labels_after_rollback"] = prompt_state()
    print(f"[state] sau khi rollback:   {evidence['labels_after_rollback']}")
    evidence["steps"].append(run_step("production-rollback", "production"))

    verify_ingested(evidence["steps"])

    (EVIDENCE_DIR / "prompt_versions.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (EVIDENCE_DIR / "prompt_versions.md").write_text(render_markdown(evidence), encoding="utf-8")
    print(f"\nĐã ghi evidence vào {EVIDENCE_DIR / 'prompt_versions.json'}")


def render_markdown(evidence: dict) -> str:
    lines = [
        "# Evidence prompt versioning",
        "",
        f"- Prompt name: `{evidence['prompt_name']}`",
        f"- Input dùng chung cho mọi version: `{evidence['probe_message']}`",
        "",
        "## Trạng thái label",
        "",
        "| Thời điểm | Label theo version |",
        "|---|---|",
        f"| Trước khi thao tác | `{evidence['labels_before']}` |",
        f"| Sau khi chuyển `production` sang v2 | `{evidence['labels_after_promote']}` |",
        f"| Sau khi rollback `production` về v1 | `{evidence['labels_after_rollback']}` |",
        "",
        "## Trace của từng bước",
        "",
        "| Bước | Label yêu cầu | Version phục vụ | Source | Correlation ID | Trace ID | "
        "Đã lên Langfuse |",
        "|---|---|---|---|---|---|---|",
    ]
    for step in evidence["steps"]:
        lines.append(
            f"| {step['step']} | `{step['env_label']}` | `v{step['prompt_version']}` | "
            f"`{step['prompt_source']}` | `{step['correlation_id']}` | `{step['trace_id']}` | "
            f"{'có' if step.get('ingested') else 'CHƯA'} |"
        )
    lines += ["", "## Link trace", ""]
    for step in evidence["steps"]:
        lines.append(f"- {step['step']}: {step['trace_url']}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
