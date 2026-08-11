# Spec — Người 1: API & Middleware (Index)

> Spec này được chia theo từng checkpoint trong [CHECKPOINTS.md](../CHECKPOINTS.md).
> Mỗi file `task_1_checkpoint_N.md` chứa phần việc của vai trò trong đúng mốc thời gian đó.
> Chi tiết triển khai (mã đầy đủ) nằm trong file của checkpoint mà phần code được hoàn thiện — chủ yếu là **Checkpoint 1**.

## Vai trò, phạm vi và bằng chứng

| Mục | Nội dung |
|---|---|
| Vai trò chính | API & Middleware |
| Việc phải làm | Hoàn thiện các `TODO` trong `app/` liên quan **correlation ID**, **JSON log**, **exception handler**, **gắn metadata request** |
| Evidence phải bàn giao | Log mẫu có correlation ID, `request-id` xuyên suốt (trong response header), chạy app không lỗi |

### Phạm vi TODOs thuộc nhiệm vụ này

| File | Dòng | TODO | Bản chất |
|---|---|---|---|
| `app/middleware.py` | 13–28 | Correlation ID: clear context, lấy/sinh `x-request-id`, bind vào structlog, trả header | **Correlation ID** |
| `app/main.py` | 47 | Enrich log bằng request context (`user_id_hash`, `session_id`, `feature`, `model`, `env`) | **Gắn metadata request** |
| `app/main.py` | (mới) | Thêm **global exception handler** ghi log lỗi chưa bắt với correlation ID | **Exception handler** |
| `app/logging_config.py` | 45 | Đăng ký processor `scrub_event` để JSON log sạch PII trước khi render | **JSON log** |

### Ngoài phạm vi (bàn giao cho vai khác)
- `app/pii.py:11` — thêm pattern PII (Passport, address…) → vai Logging & PII.
- `app/tracing.py`, `app/agent.py`, `app/metrics.py` — trace/prompt/metrics → vai khác. **Không sửa** trừ khi ảnh hưởng trực tiếp log.

---

## Điều hướng theo checkpoint

| File | Mốc (CHECKPOINTS.md) | Trọng tâm cho vai này |
|---|---|---|
| [`task_1_checkpoint_0.md`](task_1_checkpoint_0.md) | Checkpoint 0 — 0:00–0:30: Setup & baseline | Chạy app, sinh `data/logs.jsonl`, lưu baseline `validate_logs` |
| [`task_1_checkpoint_1.md`](task_1_checkpoint_1.md) | Checkpoint 1 — 0:30–1:30: Logging & PII | **Code chính**: middleware, metadata, exception handler, scrub_event + tự kiểm thử |
| [`task_1_checkpoint_2.md`](task_1_checkpoint_2.md) | Checkpoint 2 — 1:30–2:30: Metrics, traces & dashboard | Ngoài phạm vi; vai này giữ `correlation_id` hoạt động để nối trace |
| [`task_1_checkpoint_3.md`](task_1_checkpoint_3.md) | Checkpoint 3 — 2:30–3:30: Challenge chính thức | Ngoài phạm vi; hỗ trợ nối Metrics → Traces → Logs bằng correlation ID |
| [`task_1_checkpoint_4.md`](task_1_checkpoint_4.md) | Hoàn tất — 3:30–4:00: Báo cáo & demo | Thu evidence, báo cáo, commit, Definition of Done, rủi ro |

---

## Tóm tắt luồng thực hiện theo thời gian

1. **Checkpoint 0**: setup + baseline (chưa sửa code — ghi nhận trạng thái gốc).
2. **Checkpoint 1**: hoàn thiện toàn bộ `TODO` của vai → sinh log hợp lệ, `validate_logs ≥ 80/100`, header `x-request-id` xuyên suốt.
3. **Checkpoint 2–3**: không sở hữu; phối hợp để correlation ID/export header tiếp tục khớp với trace của vai Tracing.
4. **Hoàn tất**: gom evidence vào `submission/evidence/`, khai báo trong `submission/REPORT.md`, commit theo vai.
