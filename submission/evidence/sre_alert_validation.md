# Evidence kiểm chứng SLO và alert — Người 4

## Phạm vi

- Owner: `sre-alerts (ChiQuang - Người 4)`
- Challenge: `day13-k3-observability-v1`, incident `rag_slow`, feature `refund`
- Alert được kiểm chứng: `HighUserLatency`
- Điều kiện cấu hình: `latency_p95_ms > 2000 for 5m`
- SLO liên quan: P95 không vượt quá 3000 ms

## Metrics trước, trong và sau incident

| Giai đoạn | Requests | P50 (ms) | P95 (ms) | Request > 2000 ms | Error rate |
|---|---:|---:|---:|---:|---:|
| Trước incident | 10 | 152 | 1673 | 0/10 | 0% |
| Trong incident | 15 | 2654 | 2663 | 15/15 | 0% |
| Sau khi tắt incident | 10 | 152 | 153 | 0/10 | 0% |

P95 trước incident bị một request cold start kéo lên 1673 ms, trong khi P50 là 152 ms và không request nào vượt ngưỡng 2000 ms. Trong incident, cả 15 request đều vượt ngưỡng; sau mitigation, chỉ số trở về mức ổn định.

## Metrics → Traces → Logs

1. Metrics ghi nhận P95 2663 ms, vượt ngưỡng cảnh báo sớm 2000 ms.
2. Trace `053fbbc125f8a22af4573b797b297c13` có tổng latency 2663 ms.
3. Correlation ID `req-46f915b6` nối trace với log của cùng request.
4. Event `span_timings` xác định `rag-retrieval` là span chậm nhất: retrieval 2507 ms, prompt 0 ms, LLM 150 ms.

```json
{"service":"agent","trace_id":"053fbbc125f8a22af4573b797b297c13","latency_ms":2663,"retrieval_ms":2507,"prompt_ms":0,"llm_ms":150,"slowest_span":"rag-retrieval","event":"span_timings","correlation_id":"req-46f915b6","feature":"refund"}
```

Trace URL: https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/053fbbc125f8a22af4573b797b297c13

## Kết luận alert và recovery

- Threshold `> 2000 ms` được kiểm chứng: P95 đạt 2663 ms và 15/15 request vi phạm.
- Severity `High` phù hợp: request vẫn trả HTTP 200 và error rate bằng 0%, nhưng latency ảnh hưởng trực tiếp tới trải nghiệm người dùng.
- Root cause nằm ở retrieval, không phải LLM hay prompt: `rag-retrieval` chiếm khoảng 94% tổng latency.
- Mitigation đã dùng: tắt incident `rag_slow`.
- Recovery được kiểm chứng: P95 giảm về 153 ms và 0/10 request vượt 2000 ms.
- Incident kéo dài 171 giây, ngắn hơn duration 300 giây. Evidence này không tuyên bố alert đã chuyển sang trạng thái firing; muốn chứng minh đầy đủ cần duy trì cùng triệu chứng thêm ít nhất 5 phút.

Số liệu gốc được nhóm QA thu trong commit `9269326` của nhánh `feat/task5-qa-investigator`; evidence này trích riêng những dữ liệu cần thiết để giải thích quyết định SRE/Alerts.
