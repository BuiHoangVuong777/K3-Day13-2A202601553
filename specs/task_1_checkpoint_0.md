# Checkpoint 0 — Setup & baseline (0:00–0:30)

> Phần việc của **Người 1 — API & Middleware** trong mốc Setup & baseline.
> Mục tiêu: chuẩn bị môi trường, chạy được app, ghi nhận **trạng thái gốc** (chưa sửa code) để làm điểm đối chiếu sau khi hoàn thiện ở Checkpoint 1.

## 1. Hiện trạng đã xác nhận (baseline repo)

- `python -m pytest -q` → **22 passed** (toàn bộ test public pass).
- `data/logs.jsonl` **chưa tồn tại** — cần chạy app + gửi request (load_test) để sinh log.
- `app/main.py` **chưa có** global exception handler.
- `CorrelationIdMiddleware` đã đăng ký trong `app.main`; `merge_contextvars` đã trong processor chain → chỉ cần hoàn thiện thân middleware ở Checkpoint 1.
- Chuẩn log: `scripts/validate_logs.py` yêu cầu mọi request API có `correlation_id` khác `MISSING`, đủ `{user_id_hash, session_id, feature, model}`, không lộ PII. Mục tiêu đạt **≥ 80/100**.

## 2. Việc cần làm

1. Làm theo [SETUP.md](../SETUP.md): cài môi trường, tạo `.env` từ `.env.example` (điền Langfuse nếu có; không bắt buộc cho vai này).
2. Chạy app và xác minh nó khởi động **không lỗi**:
   ```bash
   uvicorn app.main:app --env-file .env --port 8000
   ```
3. Gửi request load practice để sinh dữ liệu log:
   ```bash
   python scripts/load_test.py --concurrency 3
   ```
4. Xác nhận `data/logs.jsonl` được tạo (sẽ có nhưng **chưa hợp lệ** vì các `TODO` chưa làm):
   ```bash
   python scripts/validate_logs.py
   ```
5. **Lưu kết quả baseline** (điểm/thiếu field) vào `submission/REPORT.md` để đối chiếu sau.

## 3. Tự kiểm tra checkpoint này

- [ ] `uvicorn app.main:app` khởi động không lỗi import.
- [ ] `/health` trả `{"ok": true, ...}`.
- [ ] `data/logs.jsonl` có dữ liệu sau khi chạy load_test.
- [ ] Đã ghi nhận baseline (điểm `validate_logs` và danh sách field thiếu) vào report.

> Ghi chú: ở mốc này **chưa sửa code**. Chỉ ghi nhận trạng thái gốc. Sang Checkpoint 1 mới hoàn thiện `TODO`.
