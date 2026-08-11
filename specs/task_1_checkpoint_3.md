# Checkpoint 3 — Challenge chính thức (2:30–3:30)

> Phần việc của **Người 1 — API & Middleware** trong mốc Challenge **ngoài phạm vi** (điều tra incident thuộc vai Incident, Report & Demo).
> Vai này hỗ trợ bằng cách đảm bảo pipeline log với correlation ID hoạt động để dùng làm bằng chứng root cause.

## Vai trò của API & Middleware ở mốc này
1. **Không tự chạy/không sửa** incident (`app/challenge.py`, `app/incidents.py`, `scripts/inject_incident.py`) trừ khi được vai Incident yêu cầu.
2. **Cung cấp log có correlation ID đáng tin cậy** để vai Incident nối **Metrics → Traces → Logs**:
   - Exception handler (Checkpoint 1) đảm bảo lỗi chưa bắt luôn ghi thành `unhandled_exception` kèm `correlation_id`.
   - `request_failed` trong `/chat` ghi `error_type` để khoanh vùng triệu chứng.
3. Nếu vai Incident cần một field/header mới để truy vết, phối hợp đánh giá trước khi sửa (tránh vỡ validator).

## Kiểm tra phụ trợ (của vai này)
- [ ] Khi chạy incident, log `request_failed`/`unhandled_exception` vẫn có `correlation_id` — đủ để dùng làm log evidence cho root cause.
- [ ] Không có lỗi app mới phát sinh từ middleware/logging khi incident được bật.

## Lưu ý tuân thủ
- **Không sửa** `config/challenge.json` (cấm theo RULES.md).
- Mọi kết luận incident phải có trace ID/log line/metric cụ thể — vai này chịu trách nhiệm phần log, cần để log sạch và đủ field.

> Mốc này không có code thay đổi thuộc vai Người 1 trừ khi vai Incident yêu cầu hỗ trợ truy vết cụ thể.
