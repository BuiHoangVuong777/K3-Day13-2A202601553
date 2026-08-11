# Điều tra challenge — Metrics → Traces → Logs

- Challenge ID: `day13-k3-observability-v1` (cohort `K3`)
- Incident được release: `rag_slow`
- Feature bị ảnh hưởng theo contract: `refund`
- Ngưỡng latency của challenge: **2000 ms**
- Nguồn dữ liệu: `data/logs.jsonl` (815 bản ghi)
- Cửa sổ so sánh: ±30 phút quanh incident (2026-08-11 07:22:53Z → 07:25:44Z, kéo dài 171s)

## Bước 0 — Dòng thời gian incident (dựng lại từ log)

| Incident | Bật lúc (UTC) | Tắt lúc (UTC) | Kéo dài | Dùng cho báo cáo |
|---|---|---|---|---|
| `rag_slow` | 2026-08-11 05:40:09 | 2026-08-11 05:41:15 | 66s | không |
| `rag_slow` | 2026-08-11 07:22:53 | 2026-08-11 07:25:44 | 171s | **có** |

## Bước 1 — Metrics: triệu chứng

| Cửa sổ | Khoảng (UTC) | Requests | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | Error % | Cost (USD) | Tokens/request | Quality |
|---|---|---|---|---|---|---|---|---|---|---|
| Trước incident | 06:52:53–07:22:53 | 10 | 152 | 1673 | 1673 | 1673 | 0.0 | 0.021819 | 184.9 | 0.88 |
| Trong incident | 07:22:53–07:25:44 | 15 | 2654 | 2663 | 2663 | 2663 | 0.0 | 0.031908 | 180.5 | 0.86 |
| Sau khi tắt incident | 07:25:44–07:55:44 | 10 | 152 | 153 | 153 | 153 | 0.0 | 0.019377 | 167.9 | 0.86 |

- p95 tăng **1.6×** (1673 ms → 2663 ms), rồi trở lại 153 ms sau khi tắt incident.
- p50 tăng **17.5×** (152 ms → 2654 ms): mọi request đều chậm, không phải chỉ phần đuôi.
- Request vượt ngưỡng 2000 ms: trước 0/10, trong **15/15**, sau 0/10.
- Error rate không đổi (0.0% → 0.0%): sự cố làm **chậm** chứ không làm request thất bại, nên alert dựa trên error rate hoàn toàn không bắt được — chỉ alert latency p95 mới bắt.
- Token/request (184.9 → 180.5) và quality (0.88 → 0.86) gần như không đổi: loại trừ giả thuyết model sinh dài hơn hoặc prompt bị đổi.
- Lưu ý đọc số: p95 của cửa sổ trước (1673 ms) bị kéo lên bởi đúng một request cold start — lần gọi đầu tiên phải fetch prompt từ Langfuse và resolve URL project. p50 = 152 ms mới là mức bình thường của hệ thống.

## Bước 2 — Traces: span nào chậm

| Span | Mean trước (ms) | Mean trong incident (ms) | Max trong incident (ms) | % tổng latency incident |
|---|---|---|---|---|
| `rag-retrieval` | 0 | 2500.8 | 2507 | 94.2% |
| `prompt-resolve` | 33.9 | 0 | 0 | 0.0% |
| `llm-generate` | 150.1 | 150.4 | 156 | 5.7% |

- Span chậm nhất của từng request trong incident: `rag-retrieval` 15/15, `prompt-resolve` 0/15, `llm-generate` 0/15.
- Kết luận tầng trace: **`rag-retrieval`** là span gây chậm; `prompt-resolve` và `llm-generate` giữ nguyên thời lượng.

## Bước 3 — Logs: 5 request vi phạm nặng nhất

| # | Latency (ms) | Feature | Correlation ID | Trace ID | retrieval_ms | prompt_ms | llm_ms |
|---|---|---|---|---|---|---|---|
| 1 | 2663 | `refund` | `req-46f915b6` | `053fbbc125f8a22af4573b797b297c13` | 2507 | 0 | 150 |
| 2 | 2663 | `refund` | `req-35c8171b` | `5022e8e1fdf0c43611a242abe6647fe1` | 2502 | 0 | 156 |
| 3 | 2655 | `refund` | `req-52b66bf8` | `f2dbba7e124d1256886fc54a4c6cdc90` | 2500 | 0 | 150 |
| 4 | 2655 | `refund` | `req-6df2a8fe` | `237955b707990c019ea7d33b2263aa79` | 2501 | 0 | 150 |
| 5 | 2655 | `refund` | `req-c1dc4744` | `929e7fa2fddcfb5ca24bd9a3857da0a0` | 2500 | 0 | 150 |

### Chuỗi bằng chứng đầy đủ của một request

1. **Metric**: `latency_ms=2663` vượt ngưỡng 2000 ms.
2. **Trace**: `053fbbc125f8a22af4573b797b297c13` — https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/053fbbc125f8a22af4573b797b297c13
3. **Log**: lọc `data/logs.jsonl` theo `correlation_id=req-46f915b6` được đúng 5 dòng dưới đây.

```json
{"service": "api", "payload": {"message_preview": "Summarize the refund policy for a support agent."}, "event": "request_received", "env": "dev", "session_id": "k3-challenge-s05", "user_id_hash": "5da42a0d3d01", "feature": "refund", "correlation_id": "req-46f915b6", "model": "claude-sonnet-4-5", "level": "info", "ts": "2026-08-11T07:22:59.182028Z"}
{"service": "agent", "trace_id": "053fbbc125f8a22af4573b797b297c13", "trace_url": "https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/053fbbc125f8a22af4573b797b297c13", "event": "trace_linked", "env": "dev", "session_id": "k3-challenge-s05", "user_id_hash": "5da42a0d3d01", "feature": "refund", "correlation_id": "req-46f915b6", "model": "claude-sonnet-4-5", "level": "info", "ts": "2026-08-11T07:22:59.183070Z"}
{"service": "agent", "trace_id": "053fbbc125f8a22af4573b797b297c13", "prompt_name": "day13-chat", "prompt_label": "production", "prompt_version": "1", "prompt_source": "langfuse", "prompt_fetch_error": null, "event": "prompt_resolved", "env": "dev", "session_id": "k3-challenge-s05", "user_id_hash": "5da42a0d3d01", "feature": "refund", "correlation_id": "req-46f915b6", "model": "claude-sonnet-4-5", "level": "info", "ts": "2026-08-11T07:23:01.693573Z"}
{"service": "agent", "trace_id": "053fbbc125f8a22af4573b797b297c13", "latency_ms": 2663, "retrieval_ms": 2507, "prompt_ms": 0, "llm_ms": 150, "slowest_span": "rag-retrieval", "event": "span_timings", "env": "dev", "session_id": "k3-challenge-s05", "user_id_hash": "5da42a0d3d01", "feature": "refund", "correlation_id": "req-46f915b6", "model": "claude-sonnet-4-5", "level": "info", "ts": "2026-08-11T07:23:01.846125Z"}
{"service": "api", "latency_ms": 2663, "tokens_in": 50, "tokens_out": 142, "cost_usd": 0.00228, "quality_score": 0.8, "payload": {"answer_preview": "Starter answer. Teams should improve this output logic and add better quality ch..."}, "event": "response_sent", "env": "dev", "session_id": "k3-challenge-s05", "user_id_hash": "5da42a0d3d01", "feature": "refund", "correlation_id": "req-46f915b6", "model": "claude-sonnet-4-5", "level": "info", "ts": "2026-08-11T07:23:01.848131Z"}
```

## Bước 4 — Đối chiếu giả thuyết

| Giả thuyết | Bằng chứng | Kết luận |
|---|---|---|
| Model sinh nhiều token hơn | token/request 184.9 → 180.5; span `llm-generate` 150.1 → 150.4 ms | Loại |
| Lỗi/timeout gây retry | error rate 0.0%, 0 bản ghi `request_failed` | Loại |
| Fetch prompt từ Langfuse chậm | span `prompt-resolve` mean 0 ms, `prompt_source=langfuse` không đổi | Loại |
| Chất lượng retrieval giảm nên phải sinh lại | quality 0.88 → 0.86, `doc_count` không đổi | Loại |
| Retrieval chậm | span `rag-retrieval` mean 2500.8 ms (trước: 0 ms), chiếm 94.2% latency, 15/15 request có span này chậm nhất | **Nhận** |

## Bước 5 — Xác minh sau khi khắc phục

Sau khi tắt incident lúc 07:25:44Z, cùng bộ input challenge cho p95 = 153 ms và 0/10 request vượt ngưỡng — hệ thống trở lại trạng thái trước sự cố.
