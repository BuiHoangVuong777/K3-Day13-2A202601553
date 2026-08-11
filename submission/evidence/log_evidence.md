# Evidence log: correlation ID và PII redaction

Nguồn: `data/logs.jsonl` (637 record). File log là dữ liệu runtime nên bị `.gitignore`; phần trích dưới đây là bằng chứng nộp kèm.

## 1. Correlation ID xuyên suốt một request

Một request duy nhất (`correlation_id=req-3de0f877`) sinh ra 4 log event ở 2 service, tất cả mang cùng correlation ID, cùng `user_id_hash`, `session_id`, `feature`, `model`, `env`:

```json
{"service": "api", "payload": {"message_preview": "What is your refund policy? My email is [REDACTED_EMAIL]"}, "event": "request_received", "correlation_id": "req-3de0f877", "session_id": "s01", "model": "claude-sonnet-4-5", "env": "dev", "feature": "qa", "user_id_hash": "2055254ee30a", "level": "info", "ts": "2026-08-11T05:31:28.393763Z"}
{"service": "agent", "trace_id": "ba8545817f03239a698df44bec586fc2", "trace_url": "https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/ba8545817f03239a698df44bec586fc2", "event": "trace_linked", "correlation_id": "req-3de0f877", "session_id": "s01", "model": "claude-sonnet-4-5", "env": "dev", "feature": "qa", "user_id_hash": "2055254ee30a", "level": "info", "ts": "2026-08-11T05:31:29.848305Z"}
{"service": "agent", "trace_id": "ba8545817f03239a698df44bec586fc2", "latency_ms": 1527, "retrieval_ms": 0, "prompt_ms": 285, "llm_ms": 150, "slowest_span": "prompt-resolve", "event": "span_timings", "correlation_id": "req-3de0f877", "session_id": "s01", "model": "claude-sonnet-4-5", "env": "dev", "feature": "qa", "user_id_hash": "2055254ee30a", "level": "info", "ts": "2026-08-11T05:31:30.286098Z"}
{"service": "api", "latency_ms": 1527, "tokens_in": 53, "tokens_out": 123, "cost_usd": 0.002004, "quality_score": 0.9, "payload": {"answer_preview": "Starter answer. Teams should improve this output logic and add better quality ch..."}, "event": "response_sent", "correlation_id": "req-3de0f877", "session_id": "s01", "model": "claude-sonnet-4-5", "env": "dev", "feature": "qa", "user_id_hash": "2055254ee30a", "level": "info", "ts": "2026-08-11T05:31:30.287214Z"}
```

## 2. PII đã được redact trước khi ghi log

66/637 record chứa marker `[REDACTED_*]`. Phân bố loại PII bị che: `[REDACTED_CREDIT_CARD]` × 22, `[REDACTED_EMAIL]` × 22, `[REDACTED_PHONE_VN]` × 22.

Input gốc trong `data/sample_queries.jsonl` có email, số điện thoại và số thẻ thật; log chỉ giữ bản đã che:

```json
{"service": "api", "payload": {"message_preview": "Here is my phone [REDACTED_PHONE_VN], what should be logged?"}, "event": "request_received", "model": "claude-sonnet-4-5", "session_id": "s05", "user_id_hash": "64f6ec689229", "correlation_id": "req-f0af613f", "env": "dev", "feature": "qa", "level": "info", "ts": "2026-08-11T04:43:04.084552Z"}
{"service": "api", "payload": {"message_preview": "What is your refund policy? My email is [REDACTED_EMAIL]"}, "event": "request_received", "model": "claude-sonnet-4-5", "session_id": "s01", "user_id_hash": "2055254ee30a", "correlation_id": "req-4629e531", "env": "dev", "feature": "qa", "level": "info", "ts": "2026-08-11T04:43:05.200149Z"}
{"service": "api", "payload": {"message_preview": "What is the policy for PII and credit card [REDACTED_CREDIT_CARD]?"}, "event": "request_received", "model": "claude-sonnet-4-5", "session_id": "s09", "user_id_hash": "4d14d5d4f719", "correlation_id": "req-adaba75b", "env": "dev", "feature": "qa", "level": "info", "ts": "2026-08-11T04:43:12.734761Z"}
```

## 3. Kết quả validator

```text
--- Lab Verification Results ---
Total log records analyzed: 637
Records with missing required fields: 0
Records with missing enrichment (context): 0
Unique correlation IDs found: 241
Potential PII leaks detected: 0

--- Grading Scorecard (Estimates) ---
+ [PASSED] Basic JSON schema
+ [PASSED] Correlation ID propagation
+ [PASSED] Log enrichment
+ [PASSED] PII scrubbing

Estimated Score: 100/100
```
