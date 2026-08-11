"""Kiểm tra bài nộp trước khi push (vai QA).

Script trả lời đúng một câu hỏi: bài đã đủ để nộp chưa?

- Mọi đường dẫn evidence trong ``submission/REPORT.md`` có tồn tại không.
- Các mục bắt buộc trong ``SUBMISSION.md`` đã có file tương ứng chưa.
- Report còn chỗ nào bỏ trống không.
- Repo có lỡ commit secret hoặc `.env` không.

    python scripts/qa_check_submission.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio  # noqa: E402

REPORT = REPO_ROOT / "submission" / "REPORT.md"
EVIDENCE = REPO_ROOT / "submission" / "evidence"

# Từng mục bắt buộc trong SUBMISSION.md -> file chấp nhận được (chỉ cần một file có mặt).
REQUIRED_EVIDENCE = {
    "kết quả validate_logs.py": ["validate_logs_final.txt"],
    "danh sách tối thiểu 10 traces": ["traces.md", "traces_list.png"],
    "một trace waterfall": ["trace_waterfall.png", "traces.md"],
    "hai prompt version + trace đúng version/label": ["prompt_versions.png", "prompt_versions.md"],
    "bằng chứng đổi label hoặc rollback": ["prompt_rollback_v1.png", "prompt_rollback_v2.png"],
    "log có correlation ID": ["log_correlation_and_pii.md"],
    "bằng chứng PII đã redact": ["log_correlation_and_pii.md"],
    "kết quả validate_dashboard.py": ["validate_dashboard.txt"],
    "dashboard đủ 6 nhóm chỉ số": ["dashboard_overview.png"],
    "bằng chứng điều tra challenge": ["investigation.md"],
}


def check_report_links() -> list[str]:
    text = REPORT.read_text(encoding="utf-8")
    links = sorted(set(re.findall(r"\]\((evidence/[^)]+)\)", text)))
    return [link for link in links if not (REPORT.parent / link).exists()]


def check_required() -> list[str]:
    return [
        requirement
        for requirement, candidates in REQUIRED_EVIDENCE.items()
        if not any((EVIDENCE / name).exists() for name in candidates)
    ]


def check_blank_fields() -> list[str]:
    """Bắt các mục `- Nhãn:` còn bỏ trống trong biểu mẫu report gốc.

    Một mục chỉ coi là trống khi phần sau dấu hai chấm rỗng **và** dòng có nội
    dung kế tiếp không phải bảng, danh sách con hay code block — vì nhiều mục
    dùng dấu hai chấm làm tiêu đề rồi liệt kê nội dung bên dưới.
    """
    lines = REPORT.read_text(encoding="utf-8").splitlines()
    blanks = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if re.fullmatch(r"\|(\s*\|)+", stripped):
            blanks.append(f"dòng {index + 1}: hàng bảng rỗng")
            continue
        if not re.fullmatch(r"-\s*[^:]{1,60}:\s*", stripped):
            continue
        following = next(
            (nxt.strip() for nxt in lines[index + 1:] if nxt.strip()),
            "",
        )
        if not following.startswith(("|", "-", "*", "`", "1.", "2.")):
            blanks.append(f"dòng {index + 1}: {stripped}")
    return blanks


def check_git() -> list[str]:
    problems = []
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.split()
    if ".env" in tracked:
        problems.append(".env đang được Git theo dõi")
    secrets = subprocess.run(
        ["git", "grep", "-l", "-E", r"(sk|pk)-lf-[0-9a-f]{8}", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if secrets:
        problems.append(f"key Langfuse thật xuất hiện trong: {secrets}")
    dirty = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        problems.append(f"còn thay đổi chưa commit:\n    " + dirty.replace("\n", "\n    "))
    return problems


def report_section(title: str, problems: list[str]) -> bool:
    if problems:
        print(f"[FAIL] {title}")
        for problem in problems:
            print(f"  - {problem}")
        return False
    print(f"[OK]   {title}")
    return True


def main() -> None:
    configure_utf8_stdio()
    print("=== Kiểm tra bài nộp Day 13 ===\n")
    results = [
        report_section("Mọi link evidence trong REPORT.md đều tồn tại", check_report_links()),
        report_section("Đủ evidence bắt buộc theo SUBMISSION.md", check_required()),
        report_section("REPORT.md không còn mục bỏ trống", check_blank_fields()),
        report_section("Git sạch, không lộ secret", check_git()),
    ]
    if all(results):
        print("\nSẵn sàng nộp. Lấy commit SHA bằng: git rev-parse HEAD")
    else:
        print("\nCòn thiếu như trên; sửa xong chạy lại script này.")
        sys.exit(1)


if __name__ == "__main__":
    main()
