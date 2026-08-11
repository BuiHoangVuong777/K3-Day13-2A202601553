# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.
Các threshold hiện đồng bộ với `config/slo.yaml` và `config/dashboard.yaml`; nhóm sẽ xác nhận lại sau khi có baseline runtime.

## Alert 1

- Tên: `HighUserLatency`
- Severity: High
- SLI/SLO liên quan: Latency P95 không vượt quá 3000 ms.
- Điều kiện và thời gian duy trì: Latency P95 lớn hơn 3000 ms liên tục trong 5 phút.
- Ảnh hưởng tới người dùng: Người dùng phải chờ lâu, có thể gửi lại request hoặc rời khỏi luồng đang sử dụng.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency, xác định thời điểm bắt đầu tăng và feature bị ảnh hưởng.
  2. Mở một trace chậm trong khoảng thời gian đó, so sánh thời lượng API, retrieval và LLM span.
  3. Dùng correlation ID để tìm các log liên quan, kiểm tra `response_sent.latency_ms` và log của component có span bất thường.
- Mitigation tạm thời: Chuyển sang fallback hoặc bypass dependency chậm nếu có, giảm concurrency và rollback thay đổi gần nhất có liên quan.
- Điều kiện đóng alert: P95 trở lại không quá 3000 ms trong ít nhất 5 phút và request kiểm tra hoàn thành bình thường.
- Owner: `sre-alerts`

## Alert 2

- Tên: `HighRequestErrorRate`
- Severity: Critical
- SLI/SLO liên quan: Error rate không vượt quá 2%.
- Điều kiện và thời gian duy trì: Error rate lớn hơn 2% liên tục trong 5 phút.
- Ảnh hưởng tới người dùng: Một phần request thất bại và người dùng không nhận được câu trả lời hợp lệ.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors, xác định `error_type`, thời điểm và feature có số lỗi tăng mạnh nhất.
  2. Mở một failed trace, tìm span lỗi đầu tiên và dependency liên quan.
  3. Dùng correlation ID tìm log `request_failed`, sau đó đối chiếu exception và metadata với trace.
- Mitigation tạm thời: Bật fallback, tạm cô lập dependency lỗi, giảm traffic tới feature bị ảnh hưởng hoặc rollback thay đổi gần nhất.
- Điều kiện đóng alert: Error rate trở lại không quá 2% trong ít nhất 5 phút và request kiểm tra thành công.
- Owner: `sre-alerts`

## Alert 3

- Tên: `CostBudgetAtRisk`
- Severity: Warning
- SLI/SLO liên quan: Tổng chi phí trong cửa sổ 60 phút không vượt quá 2.5 USD.
- Điều kiện và thời gian duy trì: Tổng cost của 60 phút gần nhất lớn hơn 2.5 USD trong 5 phút.
- Ảnh hưởng tới người dùng: Chưa nhất thiết gây lỗi trực tiếp, nhưng hệ thống có nguy cơ vượt ngân sách và phải giới hạn dịch vụ.
- Ba bước kiểm tra đầu tiên:
  1. So sánh Cost với Traffic để xác định chi phí tăng do số request hay do chi phí trên mỗi request.
  2. Kiểm tra tổng `tokens_in`, `tokens_out`, model và prompt version trong cùng khoảng thời gian.
  3. Mở trace generation có cost cao và đối chiếu log `response_sent` bằng correlation ID.
- Mitigation tạm thời: Giới hạn output token, giảm context retrieval, rollback prompt làm tăng token hoặc chuyển sang cấu hình model tiết kiệm hơn nếu được phép.
- Điều kiện đóng alert: Cost của cửa sổ 60 phút trở lại không quá 2.5 USD và không tiếp tục tăng bất thường.
- Owner: `sre-alerts`
