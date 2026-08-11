# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`:
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence correlation ID:
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
- Evidence dashboard: [`submission/evidence/dashboard_overview.png`](evidence/dashboard_overview.png) (toàn bộ 6 panel, đơn vị, threshold, time range 60 phút, refresh 30s), [`submission/evidence/dashboard_incident.png`](evidence/dashboard_incident.png) (giai đoạn incident `rag_slow` + `tool_fail`)

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

- **Latency p95 ≤ 3000ms**: phần lớn request phải trả lời trong 3 giây; vi phạm cho thấy pipeline AI/RAG đang chậm bất thường. Trong evidence, incident `rag_slow` đẩy p95/p99 lên ~2650ms — gần ngưỡng nhưng chưa vượt SLO, đúng như mục đích của scenario "chậm nhưng chưa chết".
- **Error rate ≤ 2%**: hệ thống được kỳ vọng hiếm khi lỗi; spike vượt ngưỡng phải kích hoạt điều tra theo chuỗi metrics → traces → logs. Khi bật incident `tool_fail`, error rate đo được là 33.33% (30/90 request) với `error_type=RuntimeError` — vượt xa SLO, đúng như kỳ vọng khi mô phỏng sự cố.
- **Cost và tokens (total ≤ $2.5, tokens ≤ 50000)**: bảo vệ khỏi chi phí tăng đột biến do prompt sai cấu hình hoặc vòng lặp gọi model không kiểm soát. Baseline hiện tại (~$0.12, ~9.6k tokens cho 90 request) còn cách xa ngưỡng, cho thấy dư địa an toàn ở mức traffic thử nghiệm.
- **Quality score ≥ 0.75**: chất lượng câu trả lời AI phải duy trì trên mức chấp nhận được; điểm giảm có thể báo hiệu vấn đề ở model, dữ liệu retrieval hoặc prompt. Mean đo được là 0.88, đạt SLO.
- **Alert rules và runbook**: cấu hình alert theo đúng `threshold` trong `config/dashboard.yaml` — cảnh báo khi `error_rate_pct` > 2% hoặc `latency_p95` > 3000ms trong cửa sổ 60 phút. Khi alert nổ, runbook là: (1) mở panel Errors để xem `error_type` chiếm ưu thế, (2) lọc `data/logs.jsonl` theo `correlation_id` của request lỗi gần nhất, (3) mở trace tương ứng trên Langfuse để xác nhận span nào timeout/raise, (4) đối chiếu với trạng thái incident (`/health` → `incidents`) trước khi kết luận root cause.

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
| | | | |
