# Spec — Người 1: API & Middleware

> Spec tổng hợp của **Người 1 — API & Middleware** cho toàn bộ lab, theo mốc thời gian trong [CHECKPOINTS.md](../CHECKPOINTS.md).
> File này thay thế các spec checkpoint tách rời (`task_1_checkpoint_N.md`) — toàn bộ phần việc của vai được gom về một nơi.
> Chi tiết triển khai (mã đầy đủ) tập trung ở **Checkpoint 1**.

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

### Ngoài phạm vi (bàn giao cho vai khác — theo bảng phân vai 5 người)

> Đối chiếu với bảng "Phân vai 5 người": đầu việc ngoài phạm vi dưới đây thuộc về đúng chủ trong bảng; vai này **không sửa** các file đó trừ khi ảnh hưởng trực tiếp log.

- `app/pii.py:11` — thêm pattern PII (Passport, address…) → **Người 2 — Security Engineer** (PII redaction, regex scrubber). `validate_logs.py` đạt ≥ 80/100 là **evidence chính của Người 2**, không phải của vai này.
- `app/tracing.py`, `app/agent.py` — trace, prompt metadata → **Người 5 — QA & Chief Investigator** (tạo 10 traces, prompt versioning v1/v2). **Không sửa** trừ khi ảnh hưởng trực tiếp log.
- `app/metrics.py`, `config/dashboard.yaml` — metrics latency/error/token/cost/quality, dashboard contract → **Người 3 — Metrics & Dashboard** và **Người 4 — SRE & Alerts Engineer** (SLO/alert/threshold/runbook). **Không sửa** trừ khi ảnh hưởng trực tiếp log.

> Lưu ý nối đầu việc: correlation ID/header của vai này là cầu nối để **Người 5 — QA & Chief Investigator** dựng luồng Metrics → Traces → Logs khi điều tra challenge ở Checkpoint 3.

---

## Tóm tắt luồng thực hiện theo thời gian

1. **Checkpoint 0**: setup + baseline (chưa sửa code — ghi nhận trạng thái gốc).
2. **Checkpoint 1**: hoàn thiện toàn bộ `TODO` của vai → sinh log hợp lệ, header `x-request-id` xuyên suốt, JSON log sạch. Điểm `validate_logs ≥ 80/100` là **kiểm tra dùng chung**: vai này chịu phần `correlation_id` + đủ field, phần PII/điểm số thuộc **Người 2 — Security Engineer**.
3. **Checkpoint 2–3**: không sở hữu; phối hợp để correlation ID/export header tiếp tục khớp với trace của **Người 5 — QA & Chief Investigator**.
4. **Hoàn tất**: gom evidence vào `submission/evidence/`, khai báo trong `submission/REPORT.md`, commit theo vai.

---

## Checkpoint 0 — Setup & baseline (0:00–0:30)

> Phần việc của **Người 1 — API & Middleware** trong mốc Setup & baseline.
> Mục tiêu: chuẩn bị môi trường, chạy được app, ghi nhận **trạng thái gốc** (chưa sửa code) để làm điểm đối chiếu sau khi hoàn thiện ở Checkpoint 1.

### 1. Hiện trạng đã xác nhận (baseline repo)

- `python -m pytest -q` → **22 passed** (toàn bộ test public pass).
- `data/logs.jsonl` **chưa tồn tại** — cần chạy app + gửi request (load_test) để sinh log.
- `app/main.py` **chưa có** global exception handler.
- `CorrelationIdMiddleware` đã đăng ký trong `app.main`; `merge_contextvars` đã trong processor chain → chỉ cần hoàn thiện thân middleware ở Checkpoint 1.
- Chuẩn log: `scripts/validate_logs.py` yêu cầu mọi request API có `correlation_id` khác `MISSING`, đủ `{user_id_hash, session_id, feature, model}`, không lộ PII. Mục tiêu đạt **≥ 80/100** — **kiểm tra dùng chung**: vai này đảm bảo phần `correlation_id` + đủ field, còn PII redaction và điểm số là **evidence chính của Người 2 — Security Engineer**.

### 2. Việc cần làm

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

### 3. Tự kiểm tra checkpoint này

- [ ] `uvicorn app.main:app` khởi động không lỗi import.
- [ ] `/health` trả `{"ok": true, ...}`.
- [ ] `data/logs.jsonl` có dữ liệu sau khi chạy load_test.
- [ ] Đã ghi nhận baseline (điểm `validate_logs` và danh sách field thiếu) vào report.

> Ghi chú: ở mốc này **chưa sửa code**. Chỉ ghi nhận trạng thái gốc. Sang Checkpoint 1 mới hoàn thiện `TODO`.

---

## Checkpoint 1 — Logging & PII (0:30–1:30)

> Phần việc chính của **Người 1 — API & Middleware**: hoàn thiện toàn bộ `TODO` của vai (correlation ID, metadata, exception handler, JSON log) tại đúng mốc Logging & PII. Trong mốc này, **phần PII redaction (`app/pii.py`) và điểm `validate_logs ≥ 80/100` thuộc Người 2 — Security Engineer**; vai này chỉ đảm bảo JSON log không vỡ validator do `correlation_id`/field thiếu.

### Mục tiêu mốc này
- Mỗi request có correlation ID hợp lệ (`req-<hex>`), không rò rỉ giữa request.
- Log API có `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- Global exception handler ghi lỗi chưa bắt kèm correlation ID.
- JSON log không chứa PII nguyên văn.
- `python scripts/validate_logs.py` đạt **≥ 80/100** — **kiểm tra dùng chung**: vai này chịu phần `correlation_id` + đủ field, PII/điểm số là **evidence chính của Người 2 — Security Engineer**.

---

#### 1. Thay đổi theo file

##### 1.1 `app/middleware.py` — `CorrelationIdMiddleware.dispatch`

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

##### 1.2 `app/main.py` — gắn metadata request trước `request_received`

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

##### 1.3 `app/main.py` — Global exception handler (mới)

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

##### 1.4 `app/logging_config.py` — đăng ký `scrub_event`

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

**Phạm vi:** vai này chỉ `đăng ký processor` để JSON log sạch. Việc `thêm/bổ sung pattern` PII và regex scrubber nằm ở `app/pii.py` thuộc **Người 2 — Security Engineer** (xem phần *Ngoài phạm vi* ở đầu spec này); nếu validator vẫn lộ PII do thiếu pattern, phối hợp với Người 2 thay vì tự sửa `app/pii.py`.

---

#### 2. Tự kiểm tra trước khi bàn giao

##### 2.1 Kiểm tra tĩnh / đơn vị
- `python -m pytest -q` → vẫn **22 passed** (chú ý `test_chat_observability.py`, `test_validate_logs.py`, `test_cli_windows_encoding.py`).
- `uvicorn app.main:app` khởi động không lỗi import; `/health` trả `{"ok": true, ...}`.

##### 2.2 Kiểm tra runtime
```bash
# Terminal 1
uvicorn app.main:app --env-file .env --port 8000
# Terminal 2
python scripts/load_test.py --concurrency 3
```

##### 2.3 Kiểm tra log
Mở `data/logs.jsonl`, xác nhận từng dòng `service=api`:
- `correlation_id` dạng `req-<hex>` (khác `MISSING`), **không trùng** giữa các request.
- đủ `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- không có email/SĐT/số thẻ/CCCD nguyên văn (chỉ `[REDACTED_...]`).
- một request `/chat` đi `request_received` → `response_sent` (hoặc `request_failed`) có **cùng** `correlation_id`.

##### 2.4 Kiểm tra header “request-id xuyên suốt”
```bash
curl -i -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u01","session_id":"s01","feature":"qa","message":"hello"}'
```
- Thấy `x-request-id: req-xxxxxxxx` và `x-response-time-ms: <ms>`.
- (Tuỳ chọn) gửi kèm header `x-request-id: foo` để xác nhận middleware tôn trọng header client.

##### 2.5 Validator
- Chạy `python scripts/validate_logs.py` để xác nhận **phần của vai này không làm mất điểm**: mọi request API có `correlation_id != MISSING` và đủ `{user_id_hash, session_id, feature, model, env}`.
- Điểm tổng **≥ 80/100** là kiểm tra dùng chung với **Người 2 — Security Engineer** (PII redaction/điểm số); vai này chỉ cam kết không vỡ phần field/correlation.

---

#### 3. Tự kiểm tra checkpoint này
- [ ] Hết `TODO` thuộc nhiệm vụ (middleware x4, main x1, logging_config x1).
- [ ] `pytest -q` = 22 passed.
- [ ] `data/logs.jsonl` mọi request API có đủ field + `correlation_id` hợp lệ, không PII thô.
- [ ] Header `x-request-id` + `x-response-time-ms` hiện diện trong response.
- [ ] `validate_logs.py` không lỗi phần `correlation_id`/field do vai này gây ra; điểm ≥ 80/100 phối hợp với **Người 2 — Security Engineer**.

---

## Checkpoint 2 — Metrics, traces & dashboard (1:30–2:30)

> Phần việc của **Người 1 — API & Middleware** trong mốc này **chủ yếu ngoài phạm vi** (metrics/traces/dashboard thuộc vai khác).
> Vai này chỉ giữ trách nhiệm phụ trợ: đảm bảo `correlation_id`/header vẫn hoạt động và khớp với trace mà **Người 5 — QA & Chief Investigator** (trace/prompt) và **Người 3 — Metrics & Dashboard** sinh ra.

### Vai trò của API & Middleware ở mốc này

1. **Không sở hữu** metrics, traces, prompt version hay dashboard — không sửa `app/metrics.py`, `config/dashboard.yaml` (thuộc **Người 3 — Metrics & Dashboard**), `app/tracing.py`, `app/agent.py` (thuộc **Người 5 — QA & Chief Investigator**).
2. **Đảm bảo correlation ID ổn định** để **Người 5 — QA & Chief Investigator** (trace) và **Người 3 — Metrics & Dashboard** dùng chung: một request `/chat` phải có cùng `correlation_id` trong log và phản ánh đúng trace của request đó.
3. **Header request-id vẫn xuất hiện** trong response (đã hoàn thiện ở Checkpoint 1) — hỗ trợ nối log → trace cho bước điều tra.

### Kiểm tra phụ trợ ở mốc này (của vai này)

- [ ] Khi **Người 5 — QA & Chief Investigator** tạo ≥ 10 traces, mỗi trace vẫn đi kèm log có `correlation_id` tương ứng (không mất tính nhất quán sau khi mốc này chạy thêm).
- [ ] `data/logs.jsonl` không bị ghi đè/sai format bởi bất kỳ thay đổi nào trong mốc này.

### Bàn giao / phối hợp
- Nếu phát hiện `correlation_id` không khớp trace, kiểm tra lại middleware (Checkpoint 1) trước khi cho rằng lỗi thuộc vai **Người 5 — QA & Chief Investigator**.
- Không tự ý thêm field vào log trừ khi validator/schema yêu cầu.

> Mốc này không có code thay đổi thuộc vai Người 1. Nếu cần thay đổi, chỉ trong phạm vi giữ cho correlation ID vận hành đúng.

---

## Checkpoint 3 — Challenge chính thức (2:30–3:30)

> Phần việc của **Người 1 — API & Middleware** trong mốc Challenge **ngoài phạm vi**. Điều tra incident và báo cáo root cause thuộc **Người 5 — QA & Chief Investigator** (theo bảng phân vai 5 người).
> Vai này hỗ trợ bằng cách đảm bảo pipeline log với correlation ID hoạt động để dùng làm bằng chứng root cause.

### Vai trò của API & Middleware ở mốc này
1. **Không tự chạy/không sửa** incident (`app/challenge.py`, `app/incidents.py`, `scripts/inject_incident.py`) trừ khi được **Người 5 — QA & Chief Investigator** yêu cầu.
2. **Cung cấp log có correlation ID đáng tin cậy** để **Người 5 — QA & Chief Investigator** nối **Metrics → Traces → Logs**:
   - Exception handler (Checkpoint 1) đảm bảo lỗi chưa bắt luôn ghi thành `unhandled_exception` kèm `correlation_id`.
   - `request_failed` trong `/chat` ghi `error_type` để khoanh vùng triệu chứng.
3. Nếu **Người 5** cần một field/header mới để truy vết, phối hợp đánh giá trước khi sửa (tránh vỡ validator).

### Kiểm tra phụ trợ (của vai này)
- [ ] Khi chạy incident, log `request_failed`/`unhandled_exception` vẫn có `correlation_id` — đủ để dùng làm log evidence cho root cause.
- [ ] Không có lỗi app mới phát sinh từ middleware/logging khi incident được bật.

### Lưu ý tuân thủ
- **Không sửa** `config/challenge.json` (cấm theo RULES.md).
- Mọi kết luận incident phải có trace ID/log line/metric cụ thể — vai này chịu trách nhiệm phần log, cần để log sạch và đủ field.

> Mốc này không có code thay đổi thuộc vai Người 1 trừ khi **Người 5 — QA & Chief Investigator** yêu cầu hỗ trợ truy vết cụ thể.

---

## Hoàn tất — Báo cáo & demo (3:30–4:00)

> Phần việc của **Người 1 — API & Middleware** ở mốc hoàn tất: gom evidence, khai báo trong report, commit theo vai, và tự kiểm tra Definition of Done.

### 1. Evidence phải thu thập (lưu vào `submission/evidence/`)

1. **Log mẫu có correlation ID** — trích 3–4 dòng JSON từ `data/logs.jsonl` của cùng một request `/chat` (cùng `correlation_id`), chứng minh rõ `user_id_hash`, `session_id`, `feature`, `model`, `env`.
2. **Chạy app không lỗi** — ảnh/screenshot (hoặc capture terminal) `/health` trả `ok: true` + app log khởi động `app_started`.
3. **Header request-id xuyên suốt** — output `curl -i` (hoặc ảnh) thể hiện `x-request-id` + `x-response-time-ms` trong response.
4. **Kết quả validator (phần đóng góp của vai này)** — output `python scripts/validate_logs.py` thể hiện `correlation_id` và đủ field không mất điểm. Điểm tổng **≥ 80/100** là evidence chính của **Người 2 — Security Engineer**; vai này ghi nhận phần của mình mà không tuyên bố sở hữu riêng điểm PII.
5. **Commit** — commit phân vai rõ ràng trên `app/middleware.py`, `app/main.py`, `app/logging_config.py` (khớp khai báo trong `submission/REPORT.md` để lấy điểm B2).

> KHÔNG commit `.env`, key, `.venv/`, hoặc log chứa PII. Mẫu log đưa vào `submission/evidence/` phải đã scrub hoặc an toàn.

### 2. Khai báo trong `submission/REPORT.md`
- Mô tả phần việc cá nhân: correlation ID, JSON log, exception handler, gắn metadata request.
- Dẫn evidence cụ thể (log line / screenshot / commit SHA) để có thể kiểm chứng.
- Nêu trade-off/lựa chọn thiết kế (vd: tôn trọng header `x-request-id` từ client, đọc `correlation_id` từ `request.state` ở exception handler).

### 3. Commit theo vai
```bash
git add app/middleware.py app/main.py app/logging_config.py specs/
git commit -m "feat(api): correlation ID, JSON log, exception handler, request metadata"
```
- Đảm bảo Git không chứa secret hoặc PII (`.env` đã nằm trong `.gitignore`).

### 4. Definition of Done (kiểm tra tổng thể)

- [ ] Hết `TODO` thuộc nhiệm vụ (middleware x4, main x1, logging_config x1).
- [ ] App chạy được, `/health` trả `ok: true`, không lỗi import/runtime.
- [ ] Mỗi request có `correlation_id` hợp lệ, không rò rỉ giữa request, xuất hiện trong toàn bộ log + trả về header `x-request-id`.
- [ ] Log API có đủ `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- [ ] Global exception handler hoạt động: lỗi chưa bắt ghi `unhandled_exception` kèm `correlation_id`, client nhận JSON 500 ổn định.
- [ ] JSON log không vỡ validator ở phần `correlation_id`/field do vai này gây ra; PII/điểm `validate_logs.py ≥ 80/100` là **kiểm tra dùng chung với Người 2 — Security Engineer**.
- [ ] `python -m pytest -q` vẫn **22 passed**.
- [ ] Evidence đã lưu vào `submission/evidence/` và khai báo trong `submission/REPORT.md`.

### 5. Chuẩn bị demo (phần của vai này)
- Trình bày: gửi request → chỉ ra header `x-request-id` → mở `data/logs.jsonl` dòng cùng `correlation_id` → giải thích JSON log và exception handler.
- Sẵn sàng trả lời câu hỏi: correlation ID sinh/lan truyền thế nào, vì sao `clear_contextvars`, thứ tự processor structlog, vì sao không log `user_id` thô, PII được scrub ở đâu.

---

## Rủi ro / lưu ý (xuyên suốt)

- **Rò rỉ context**: quên `clear_contextvars()` trước khi bind → request sau thừa hưởng `correlation_id`/metadata của request trước (mất điểm correlation ID propagation).
- **Thứ tự processor structlog**: phải đặt `scrub_event` trước `JSONRenderer`/`JsonlFileProcessor`, nếu không PII trong `payload`/`event` vẫn bị ghi thô.
- **Không log `user_id` thô** — luôn qua `hash_user_id`.
- **Không sửa** `config/challenge.json` (cấm theo RULES.md).
- **Phụ thuộc vai khác**: `app/pii.py` thêm pattern thuộc **Người 2 — Security Engineer**; nếu validator báo PII do pattern thiếu, phối hợp với Người 2 thay vì tự xử lý vượt phạm vi.
- **`on_event("startup")` deprecation warning** — không bắt buộc đụng tới; tránh refactor ngoài phạm vi.
