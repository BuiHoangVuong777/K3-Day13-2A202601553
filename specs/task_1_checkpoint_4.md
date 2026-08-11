# Hoàn tất — Báo cáo & demo (3:30–4:00)

> Phần việc của **Người 1 — API & Middleware** ở mốc hoàn tất: gom evidence, khai báo trong report, commit theo vai, và tự kiểm tra Definition of Done.

## 1. Evidence phải thu thập (lưu vào `submission/evidence/`)

1. **Log mẫu có correlation ID** — trích 3–4 dòng JSON từ `data/logs.jsonl` của cùng một request `/chat` (cùng `correlation_id`), chứng minh rõ `user_id_hash`, `session_id`, `feature`, `model`, `env`.
2. **Chạy app không lỗi** — ảnh/screenshot (hoặc capture terminal) `/health` trả `ok: true` + app log khởi động `app_started`.
3. **Header request-id xuyên suốt** — output `curl -i` (hoặc ảnh) thể hiện `x-request-id` + `x-response-time-ms` trong response.
4. **Kết quả validator** — output `python scripts/validate_logs.py` (≥ 80/100).
5. **Commit** — commit phân vai rõ ràng trên `app/middleware.py`, `app/main.py`, `app/logging_config.py` (khớp khai báo trong `submission/REPORT.md` để lấy điểm B2).

> KHÔNG commit `.env`, key, `.venv/`, hoặc log chứa PII. Mẫu log đưa vào `submission/evidence/` phải đã scrub hoặc an toàn.

## 2. Khai báo trong `submission/REPORT.md`
- Mô tả phần việc cá nhân: correlation ID, JSON log, exception handler, gắn metadata request.
- Dẫn evidence cụ thể (log line / screenshot / commit SHA) để có thể kiểm chứng.
- Nêu trade-off/lựa chọn thiết kế (vd: tôn trọng header `x-request-id` từ client, đọc `correlation_id` từ `request.state` ở exception handler).

## 3. Commit theo vai
```bash
git add app/middleware.py app/main.py app/logging_config.py specs/
git commit -m "feat(api): correlation ID, JSON log, exception handler, request metadata"
```
- Đảm bảo Git không chứa secret hoặc PII (`.env` đã nằm trong `.gitignore`).

## 4. Definition of Done (kiểm tra tổng thể)

- [ ] Hết `TODO` thuộc nhiệm vụ (middleware x4, main x1, logging_config x1).
- [ ] App chạy được, `/health` trả `ok: true`, không lỗi import/runtime.
- [ ] Mỗi request có `correlation_id` hợp lệ, không rò rỉ giữa request, xuất hiện trong toàn bộ log + trả về header `x-request-id`.
- [ ] Log API có đủ `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- [ ] Global exception handler hoạt động: lỗi chưa bắt ghi `unhandled_exception` kèm `correlation_id`, client nhận JSON 500 ổn định.
- [ ] JSON log không chứa PII nguyên văn; `validate_logs.py` **≥ 80/100**.
- [ ] `python -m pytest -q` vẫn **22 passed**.
- [ ] Evidence đã lưu vào `submission/evidence/` và khai báo trong `submission/REPORT.md`.

## 5. Chuẩn bị demo (phần của vai này)
- Trình bày: gửi request → chỉ ra header `x-request-id` → mở `data/logs.jsonl` dòng cùng `correlation_id` → giải thích JSON log và exception handler.
- Sẵn sàng trả lời câu hỏi: correlation ID sinh/lan truyền thế nào, vì sao `clear_contextvars`, thứ tự processor structlog, vì sao không log `user_id` thô, PII được scrub ở đâu.

---

## Rủi ro / lưu ý (xuyên suốt)

- **Rò rỉ context**: quên `clear_contextvars()` trước khi bind → request sau thừa hưởng `correlation_id`/metadata của request trước (mất điểm correlation ID propagation).
- **Thứ tự processor structlog**: phải đặt `scrub_event` trước `JSONRenderer`/`JsonlFileProcessor`, nếu không PII trong `payload`/`event` vẫn bị ghi thô.
- **Không log `user_id` thô** — luôn qua `hash_user_id`.
- **Không sửa** `config/challenge.json` (cấm theo RULES.md).
- **Phụ thuộc vai khác**: `app/pii.py` thêm pattern thuộc vai Logging & PII; nếu validator báo PII do pattern thiếu, phối hợp với vai đó thay vì tự xử lý vượt phạm vi.
- **`on_event("startup")` deprecation warning** — không bắt buộc đụng tới; tránh refactor ngoài phạm vi.
