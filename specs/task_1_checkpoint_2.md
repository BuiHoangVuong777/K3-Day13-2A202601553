# Checkpoint 2 — Metrics, traces & dashboard (1:30–2:30)

> Phần việc của **Người 1 — API & Middleware** trong mốc này **chủ yếu ngoài phạm vi** (metrics/traces/dashboard thuộc vai khác).
> Vai này chỉ giữ trách nhiệm phụ trợ: đảm bảo `correlation_id`/header vẫn hoạt động và khớp với trace mà vai Tracing sinh ra.

## Vai trò của API & Middleware ở mốc này

1. **Không sở hữu** metrics, traces, prompt version hay dashboard — không sửa `app/metrics.py`, `app/tracing.py`, `app/agent.py`, `config/dashboard.yaml`.
2. **Đảm bảo correlation ID ổn định** để vai Tracing/Dashboard dùng chung: một request `/chat` phải có cùng `correlation_id` trong log và phản ánh đúng trace của request đó.
3. **Header request-id vẫn xuất hiện** trong response (đã hoàn thiện ở Checkpoint 1) — hỗ trợ nối log → trace cho bước điều tra.

## Kiểm tra phụ trợ ở mốc này (của vai này)

- [ ] Khi vai Tracing tạo ≥ 10 traces, mỗi trace vẫn đi kèm log có `correlation_id` tương ứng (không mất tính nhất quán sau khi mốc này chạy thêm).
- [ ] `data/logs.jsonl` không bị ghi đè/sai format bởi bất kỳ thay đổi nào trong mốc này.

## Bàn giao / phối hợp
- Nếu phát hiện `correlation_id` không khớp trace, kiểm tra lại middleware (Checkpoint 1) trước khi cho rằng lỗi thuộc vai Tracing.
- Không tự ý thêm field vào log trừ khi validator/schema yêu cầu.

> Mốc này không có code thay đổi thuộc vai Người 1. Nếu cần thay đổi, chỉ trong phạm vi giữ cho correlation ID vận hành đúng.
