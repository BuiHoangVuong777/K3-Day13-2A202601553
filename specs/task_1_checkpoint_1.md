# Checkpoint 1 — Logging & PII (0:30–1:30)

> Phần việc chính của **Người 1 — API & Middleware**: hoàn thiện toàn bộ `TODO` của vai (correlation ID, metadata, exception handler, JSON log) tại đúng mốc Logging & PII.

## Mục tiêu mốc này
- Mỗi request có correlation ID hợp lệ (`req-<hex>`), không rò rỉ giữa request.
- Log API có `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- Global exception handler ghi lỗi chưa bắt kèm correlation ID.
- JSON log không chứa PII nguyên văn.
- `python scripts/validate_logs.py` đạt **≥ 80/100**.

---

## 1. Thay đổi theo file

### 1.1 `app/middleware.py` — `CorrelationIdMiddleware.dispatch`

Thay 4 `TODO` bằng luồng chuẩn, đúng thứ tự:

```python
async def dispatch(self, request: Request, call_next):
    # 1) Clear contextvars để không rò rỉ correlation_id giữa các request
    clear_contextvars()

    # 2) Lấy x-request-id từ header (cho phép client truyền) hoặc sinh mới
    correlation_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:8]}"

    # 3) Bind vào structlog contextvars -> mọi log trong request đều có correlation_id
    bind_contextvars(correlation_id=correlation_id)

    request.state.correlation_id = correlation_id

    start = time.perf_counter()
    response = await call_next(request)

    # 4) Trả lại correlation_id và thời gian xử lý trong response header
    response.headers["x-request-id"] = correlation_id
    response.headers["x-response-time-ms"] = str(int((time.perf_counter() - start) * 1000))
    return response
```

**Lưu ý:**
- `request.headers.get("x-request-id")` — headers của `Request` là dict không phân biệt hoa/thường.
- Thứ tự bắt buộc: `clear_contextvars()` **trước** khi bind, nếu không correlation_id request cũ rò sang request mới (đúng yêu cầu GUIDE.md).
- `correlation_id` cũng gán vào `request.state` để `/chat` và global exception handler đọc.

### 1.2 `app/main.py` — gắn metadata request trước `request_received`

Thay `TODO` tại `chat()` bằng việc bind context **trước** log `request_received`:

```python
bind_contextvars(
    user_id_hash=hash_user_id(body.user_id),
    session_id=body.session_id,
    feature=body.feature,
    model=agent.model,
    env=os.getenv("APP_ENV", "dev"),
)
```

**Nguồn dữ liệu:**
- `hash_user_id(...)` đã có trong `app/pii.py` — **không log `user_id` thô**.
- `agent.model` — `LabAgent` lưu `self.model` (mặc định `claude-sonnet-4-5`).
- `env` đọc từ `APP_ENV` (khớp mặc định `dev` như `startup()`).
- `merge_contextvars` đầu processor chain → các field này tự gắn vào mọi log trong request (gồm `response_sent`).

### 1.3 `app/main.py` — Global exception handler (mới)

Thêm handler toàn cục để **lỗi chưa bắt** được ghi log kèm correlation ID và trả JSON ổn định. Đặt sau `app.add_middleware`:

```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_type = type(exc).__name__
    log.error(
        "unhandled_exception",
        service="api",
        error_type=error_type,
        correlation_id=getattr(request.state, "correlation_id", "MISSING"),
        payload={"detail": str(exc)},
    )
    return JSONResponse(status_code=500, content={"detail": "internal_error"})
```

**Lưu ý:**
- Giữ handler `/chat` cục bộ (ghi `request_failed` + `record_error`) — **không thay thế**, global handler chỉ là lưới an toàn.
- Đọc `correlation_id` từ `request.state`; fallback `"MISSING"` nếu middleware chưa chạy.
- Trả `{"detail": "internal_error"}` → không lộ stack/detail thô.

### 1.4 `app/logging_config.py` — đăng ký `scrub_event`

Bỏ comment trong `processors` để scrub PII **trước khi** JSON render/ghi file:

```python
processors=[
    merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
    scrub_event,                                   # <-- bỏ comment (TODO)
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    JsonlFileProcessor(),
    structlog.processors.JSONRenderer(),
],
```

**Vì sao bắt buộc:** thứ tự processor quyết định dữ liệu được scrub **trước** `JSONRenderer`/`JsonlFileProcessor`. Nếu không, `message_preview`/`answer_preview`/`event` có thể chứa PII thô → validator trừ 30 điểm.

---

## 2. Tự kiểm tra trước khi bàn giao

### 2.1 Kiểm tra tĩnh / đơn vị
- `python -m pytest -q` → vẫn **22 passed** (chú ý `test_chat_observability.py`, `test_validate_logs.py`, `test_cli_windows_encoding.py`).
- `uvicorn app.main:app` khởi động không lỗi import; `/health` trả `{"ok": true, ...}`.

### 2.2 Kiểm tra runtime
```bash
# Terminal 1
uvicorn app.main:app --env-file .env --port 8000
# Terminal 2
python scripts/load_test.py --concurrency 3
```

### 2.3 Kiểm tra log
Mở `data/logs.jsonl`, xác nhận từng dòng `service=api`:
- `correlation_id` dạng `req-<hex>` (khác `MISSING`), **không trùng** giữa các request.
- đủ `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- không có email/SĐT/số thẻ/CCCD nguyên văn (chỉ `[REDACTED_...]`).
- một request `/chat` đi `request_received` → `response_sent` (hoặc `request_failed`) có **cùng** `correlation_id`.

### 2.4 Kiểm tra header “request-id xuyên suốt”
```bash
curl -i -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u01","session_id":"s01","feature":"qa","message":"hello"}'
```
- Thấy `x-request-id: req-xxxxxxxx` và `x-response-time-ms: <ms>`.
- (Tuỳ chọn) gửi kèm header `x-request-id: foo` để xác nhận middleware tôn trọng header client.

### 2.5 Validator
- `python scripts/validate_logs.py` → đạt **≥ 80/100** (mục tiêu 100).

---

## 3. Tự kiểm tra checkpoint này
- [ ] Hết `TODO` thuộc nhiệm vụ (middleware x4, main x1, logging_config x1).
- [ ] `pytest -q` = 22 passed.
- [ ] `data/logs.jsonl` mọi request API có đủ field + `correlation_id` hợp lệ, không PII thô.
- [ ] Header `x-request-id` + `x-response-time-ms` hiện diện trong response.
- [ ] `validate_logs.py` ≥ 80/100.
