# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.
Các SLO threshold đồng bộ với `config/slo.yaml` và `config/dashboard.yaml`. Alert latency dùng ngưỡng cảnh báo sớm 2000 ms theo challenge contract để nhóm phản ứng trước khi vi phạm SLO 3000 ms.

Các alert yêu cầu điều kiện duy trì 5 phút để tránh cảnh báo do một vài request bất thường hoặc spike ngắn, qua đó giảm false positive và alert fatigue. Official challenge kéo dài 171 giây đã chứng minh metric vượt threshold nhưng chưa đủ 300 giây để khẳng định alert thực sự chuyển sang trạng thái firing. Nhóm giữ giới hạn này minh bạch thay vì suy diễn evidence; chi tiết nằm tại [`submission/evidence/sre_alert_validation.md`](../submission/evidence/sre_alert_validation.md).

## Alert 1

- Tên: `HighUserLatency`
- Severity: High
- Lý do severity: Hệ thống vẫn có thể trả response nhưng độ trễ cao làm trải nghiệm người dùng suy giảm đáng kể, nên cần xử lý sớm nhưng chưa ở mức mất dịch vụ hoàn toàn.
- SLI/SLO liên quan: Latency P95 không vượt quá 3000 ms.
- Điều kiện và thời gian duy trì: Latency P95 lớn hơn 2000 ms liên tục trong 5 phút.
- Cơ sở chọn ngưỡng: Sau recovery, P95 ổn định khoảng 153 ms; official challenge `rag_slow` đẩy P95 lên 2663 ms và 15/15 request vượt 2000 ms. Ngưỡng 2000 ms phát hiện sớm suy giảm rõ rệt trước khi SLO 3000 ms bị vi phạm.
- Kiểm chứng runtime: Trace `053fbbc125f8a22af4573b797b297c13` gắn với correlation ID `req-46f915b6` có tổng latency 2663 ms; span `rag-retrieval` chiếm 2507 ms, trong khi `llm-generate` chỉ 150 ms. Error rate vẫn là 0%, vì vậy severity High phù hợp hơn Critical cho sự cố này.
- Ảnh hưởng tới người dùng: Người dùng phải chờ lâu, có thể gửi lại request hoặc rời khỏi luồng đang sử dụng.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency, xác định thời điểm bắt đầu tăng và feature bị ảnh hưởng.
  2. Mở một trace chậm trong khoảng thời gian đó, so sánh thời lượng API, retrieval và LLM span.
  3. Dùng correlation ID để tìm các log liên quan, kiểm tra `response_sent.latency_ms` và log của component có span bất thường.
- Mitigation tạm thời: Chuyển sang fallback hoặc bypass dependency chậm nếu có, giảm concurrency và rollback thay đổi gần nhất có liên quan.
- Điều kiện đóng alert: P95 trở lại không quá 2000 ms trong ít nhất 5 phút và request kiểm tra hoàn thành bình thường.
- Owner: `sre-alerts (ChiQuang - Người 4)`

## Alert 2

- Tên: `HighRequestErrorRate`
- Severity: Critical
- Lý do severity: Request thất bại khiến người dùng không nhận được kết quả, tác động trực tiếp tới tính sẵn sàng của dịch vụ và cần phản ứng ngay.
- SLI/SLO liên quan: Error rate không vượt quá 2%.
- Điều kiện và thời gian duy trì: Error rate lớn hơn 2% liên tục trong 5 phút.
- Cơ sở chọn ngưỡng: Practice `tool_fail` tạo 30 request lỗi trên 90 request, tương ứng 33.33%, vượt xa ngưỡng 2% và thể hiện ảnh hưởng rõ tới người dùng.
- Kiểm chứng runtime: Panel Errors trong [`dashboard_incident.png`](../submission/evidence/dashboard_incident.png) thể hiện error rate 33.33% với `RuntimeError`; đây là practice evidence, không phải incident chính thức `rag_slow`.
- Ảnh hưởng tới người dùng: Một phần request thất bại và người dùng không nhận được câu trả lời hợp lệ.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors, xác định `error_type`, thời điểm và feature có số lỗi tăng mạnh nhất.
  2. Mở một failed trace, tìm span lỗi đầu tiên và dependency liên quan.
  3. Dùng correlation ID tìm log `request_failed`, sau đó đối chiếu exception và metadata với trace.
- Mitigation tạm thời: Bật fallback, tạm cô lập dependency lỗi, giảm traffic tới feature bị ảnh hưởng hoặc rollback thay đổi gần nhất.
- Điều kiện đóng alert: Error rate trở lại không quá 2% trong ít nhất 5 phút và request kiểm tra thành công.
- Owner: `sre-alerts (ChiQuang - Người 4)`

## Alert 3

- Tên: `CostBudgetAtRisk`
- Severity: Warning
- Lý do severity: Cost tăng chưa làm request lỗi ngay nhưng có nguy cơ vượt ngân sách và buộc nhóm giới hạn dịch vụ nếu không xử lý kịp thời.
- SLI/SLO liên quan: Tổng chi phí trong cửa sổ 60 phút không vượt quá 2.5 USD.
- Điều kiện và thời gian duy trì: Tổng cost của 60 phút gần nhất lớn hơn 2.5 USD trong 5 phút.
- Cơ sở chọn ngưỡng: Baseline khoảng 0.1212 USD cho 90 request, còn đủ khoảng an toàn so với ngân sách 2.5 USD nhưng vẫn phát hiện được cost spike lớn.
- Trạng thái kiểm chứng: Nhóm mới kiểm chứng baseline và mapping `response_sent.cost_usd`; chưa kích hoạt `cost_spike` trong official challenge nên không tuyên bố alert này đã firing.
- Ảnh hưởng tới người dùng: Chưa nhất thiết gây lỗi trực tiếp, nhưng hệ thống có nguy cơ vượt ngân sách và phải giới hạn dịch vụ.
- Ba bước kiểm tra đầu tiên:
  1. So sánh Cost với Traffic để xác định chi phí tăng do số request hay do chi phí trên mỗi request.
  2. Kiểm tra tổng `tokens_in`, `tokens_out`, model và prompt version trong cùng khoảng thời gian.
  3. Mở trace generation có cost cao và đối chiếu log `response_sent` bằng correlation ID.
- Mitigation tạm thời: Giới hạn output token, giảm context retrieval, rollback prompt làm tăng token hoặc chuyển sang cấu hình model tiết kiệm hơn nếu được phép.
- Điều kiện đóng alert: Cost của cửa sổ 60 phút trở lại không quá 2.5 USD và không tiếp tục tăng bất thường.
- Owner: `sre-alerts (ChiQuang - Người 4)`
