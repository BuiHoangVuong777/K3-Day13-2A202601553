# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (xem [`submission/evidence/validator_result.txt`](evidence/validator_result.txt))
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard: xem ảnh `submission/evidence/dashboard_overview.png` (dashboard dựng từ `data/logs.jsonl`, không có URL công khai trong môi trường lab).

## 3. Logging và tracing

- Evidence correlation ID: [`submission/evidence/api_log_sample.jsonl`](evidence/api_log_sample.jsonl) — hai dòng log `request_received` → `response_sent` của cùng một request `/chat` cùng `correlation_id=req-40b35680` (correlation ID ổn định xuyên suốt request).
- Evidence PII redaction:
- Evidence trace waterfall:
- Giải thích một span đáng chú ý:

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.`
- Evidence dashboard: [`submission/evidence/dashboard_overview.png`](evidence/dashboard_overview.png) (toàn bộ 6 panel, đơn vị, threshold, time range 60 phút, refresh 30s), [`submission/evidence/dashboard_incident.png`](evidence/dashboard_incident.png) (practice incident `rag_slow` + `tool_fail`). Evidence riêng cho quyết định alert và chuỗi Metrics → Traces → Logs: [`submission/evidence/sre_alert_validation.md`](evidence/sre_alert_validation.md).

### Nguồn log cho metrics

Ba event trong `data/logs.jsonl` cấp dữ liệu cho toàn bộ 6 panel:

- `request_received`: log mỗi request đến, kèm metadata (`correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`). Dùng cho panel Traffic và làm mẫu số của Errors.
- `request_failed`: log khi request lỗi, kèm `error_type` (ví dụ `RuntimeError` khi bật incident `tool_fail`). Dùng cho panel Errors.
- `response_sent`: log khi trả lời thành công, kèm `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`. Dùng cho panel Latency, Cost, Tokens, Quality.

### Panel mapping

| Panel   | Event(s)            | Field(s)                    | Aggregation         | Unit            | Threshold / SLO        |
|--------|---------------------|-----------------------------|---------------------|-----------------|------------------------|
| Latency | `response_sent`    | `latency_ms`                | p50 / p95 / p99     | ms              | p95 ≤ 3000             |
| Traffic | `request_received` | `event` (count)             | requests per minute | requests/min    | rate ≥ 1               |
| Errors  | `request_received`, `request_failed` | `error_type` | `error_rate_pct`, count by value | percent | `error_rate_pct` ≤ 2 |
| Cost    | `response_sent`    | `cost_usd`                  | sum per minute, total | usd           | total ≤ 2.5           |
| Tokens  | `response_sent`    | `tokens_in`, `tokens_out`   | sum                 | tokens          | sum ≤ 50000           |
| Quality | `response_sent`    | `quality_score`             | mean                | 0–1 score       | mean ≥ 0.75           |

### SLO / alert đã chọn và ý nghĩa

- **Latency p95 ≤ 3000ms**: phần lớn request phải trả lời trong 3 giây; vi phạm cho thấy pipeline AI/RAG đang chậm bất thường. Official challenge `rag_slow` đẩy p95 lên 2663 ms và 15/15 request vượt 2000 ms — chưa vượt SLO nhưng đã vượt ngưỡng cảnh báo sớm của challenge contract. Sau khi tắt incident, p95 trở lại 153 ms.
- **Error rate ≤ 2%**: hệ thống được kỳ vọng hiếm khi lỗi; spike vượt ngưỡng phải kích hoạt điều tra theo chuỗi metrics → traces → logs. Khi bật incident `tool_fail`, error rate đo được là 33.33% (30/90 request) với `error_type=RuntimeError` — vượt xa SLO, đúng như kỳ vọng khi mô phỏng sự cố.
- **Cost và tokens (total ≤ $2.5, tokens ≤ 50000)**: bảo vệ khỏi chi phí tăng đột biến do prompt sai cấu hình hoặc vòng lặp gọi model không kiểm soát. Baseline hiện tại (~$0.12, ~9.6k tokens cho 90 request) còn cách xa ngưỡng, cho thấy dư địa an toàn ở mức traffic thử nghiệm.
- **Quality score ≥ 0.75**: chất lượng câu trả lời AI phải duy trì trên mức chấp nhận được; điểm giảm có thể báo hiệu vấn đề ở model, dữ liệu retrieval hoặc prompt. Mean đo được là 0.88, đạt SLO.

Các target được chọn theo mức dung sai của từng SLI: latency target 99.5% cho phép tối đa 0.5% cửa sổ đo vi phạm; error target 99% cho phép tối đa 1%; cost target 100% vì 2.5 USD là hard budget; quality target 95% cho phép 5% dao động vì đây là proxy chứ không phải đánh giá chất lượng tuyệt đối.

### Alert rules và runbook

Ba alert symptom-based nằm tại [`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook chi tiết nằm tại [`docs/alerts.md`](../docs/alerts.md):

- Owner: `sre-alerts (ChiQuang - Người 4)`

| Alert | Severity | Điều kiện | Cơ sở |
|---|---|---|---|
| `HighUserLatency` | High | `latency_p95_ms > 2000 for 5m` | Cảnh báo sớm khi P95 vượt challenge threshold, trước SLO 3000ms |
| `HighRequestErrorRate` | Critical | `error_rate_pct > 2 for 5m` | Practice `tool_fail` đạt 33.33%, thể hiện request thất bại trực tiếp |
| `CostBudgetAtRisk` | Warning | `cost_usd_60m > 2.5 for 5m` | Baseline khoảng 0.1212 USD/90 request, ngưỡng bảo vệ cost spike lớn |

Severity phản ánh mức độ ảnh hưởng: request lỗi là Critical vì người dùng không nhận được kết quả; latency cao là High vì dịch vụ vẫn trả response nhưng trải nghiệm suy giảm; cost là Warning vì chưa gây lỗi trực tiếp nhưng đe dọa ngân sách.

Dashboard hiển thị cửa sổ 60 phút, alert yêu cầu điều kiện duy trì 5 phút để hạn chế cảnh báo do spike ngắn, còn SLO được đánh giá trên cửa sổ 28 ngày. Official challenge kéo dài 171 giây nên evidence chỉ chứng minh điều kiện ngưỡng, không tuyên bố alert đã firing đủ 5 phút. Chuỗi điều tra đã được kiểm chứng bằng metric p95 2663 ms → trace `053fbbc125f8a22af4573b797b297c13` → correlation ID `req-46f915b6` → span `rag-retrieval` 2507 ms; sau mitigation, p95 phục hồi về 153 ms. Khi alert kích hoạt, runbook đi theo luồng: (1) xác định triệu chứng và khoảng thời gian trên metrics, (2) mở trace bất thường để khoanh vùng span, (3) dùng correlation ID tìm log liên quan, (4) áp dụng mitigation và chỉ đóng alert sau khi chỉ số phục hồi ổn định.

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Người 1 — API & Middleware | Correlation ID (middleware, `clear_contextvars` + bind + header `x-request-id`/`x-response-time-ms`), JSON log sạch PII (`scrub_event` trong processor chain), global exception handler (`unhandled_exception` kèm correlation_id), gắn metadata request (`user_id_hash`, `session_id`, `feature`, `model`, `env`) | `21c0623` (app/middleware.py, app/main.py, app/logging_config.py) | Thứ tự processor structlog quyết định dữ liệu được scrub trước khi JSON render; `merge_contextvars` tự gắn context vào mọi log trong request; phải `clear_contextvars()` trước khi bind để tránh rò rỉ correlation ID giữa các request; không log `user_id` thô mà luôn qua `hash_user_id`. |
| Người 4 — Nguyễn Chí Quang | Thiết kế 5 SLI/SLO, 3 alert symptom-based, severity/duration, runbook Metrics → Traces → Logs và kiểm chứng threshold bằng official challenge | `2dd55c6`, `3110b64`; PR từ nhánh `feature/slo-alerts-runbook` | Alert phải dựa trên ảnh hưởng người dùng; evidence phải tách rõ “vượt threshold” với “đủ duration để firing”, đồng thời cần trace ID và correlation ID để chứng minh root cause. |
