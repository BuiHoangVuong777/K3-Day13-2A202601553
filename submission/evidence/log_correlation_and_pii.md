# Evidence log: correlation ID và PII redaction

Kiểm chứng lại: `python scripts/validate_logs.py` (kết quả trong `validate_logs_final.txt`).

## 1. Correlation ID xuyên suốt một request

Một request duy nhất sinh ra 5 dòng log, tất cả mang cùng `correlation_id = req-prompt-baseline`,
và dòng `trace_linked` nối correlation ID này sang trace ID trên Langfuse.

```json
{"service": "api", "payload": {"message_preview": "What is your refund policy?"}, "event": "request_received", "session_id": "prompt-baseline", "user_id_hash": "f3f4d06481ce", "model": "claude-sonnet-4-5", "env": "dev", "correlation_id": "req-prompt-baseline", "feature": "refund", "level": "info", "ts": "2026-08-11T07:59:33.613000Z"}
{"service": "agent", "trace_id": "8a812c62cf3a4fcc6227b4fb8abd8e5b", "trace_url": "https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/8a812c62cf3a4fcc6227b4fb8abd8e5b", "event": "trace_linked", "session_id": "prompt-baseline", "user_id_hash": "f3f4d06481ce", "model": "claude-sonnet-4-5", "env": "dev", "correlation_id": "req-prompt-baseline", "feature": "refund", "level": "info", "ts": "2026-08-11T07:59:35.221320Z"}
{"service": "agent", "trace_id": "8a812c62cf3a4fcc6227b4fb8abd8e5b", "prompt_name": "day13-chat", "prompt_label": "baseline", "prompt_version": "1", "prompt_source": "langfuse", "prompt_fetch_error": null, "event": "prompt_resolved", "session_id": "prompt-baseline", "user_id_hash": "f3f4d06481ce", "model": "claude-sonnet-4-5", "env": "dev", "correlation_id": "req-prompt-baseline", "feature": "refund", "level": "info", "ts": "2026-08-11T07:59:35.530276Z"}
{"service": "agent", "trace_id": "8a812c62cf3a4fcc6227b4fb8abd8e5b", "latency_ms": 1709, "retrieval_ms": 0, "prompt_ms": 306, "llm_ms": 150, "slowest_span": "prompt-resolve", "event": "span_timings", "session_id": "prompt-baseline", "user_id_hash": "f3f4d06481ce", "model": "claude-sonnet-4-5", "env": "dev", "correlation_id": "req-prompt-baseline", "feature": "refund", "level": "info", "ts": "2026-08-11T07:59:35.683085Z"}
{"service": "api", "latency_ms": 1709, "tokens_in": 45, "tokens_out": 138, "cost_usd": 0.002205, "quality_score": 0.9, "payload": {"answer_preview": "Starter answer. Teams should improve this output logic and add better quality ch..."}, "event": "response_sent", "session_id": "prompt-baseline", "user_id_hash": "f3f4d06481ce", "model": "claude-sonnet-4-5", "env": "dev", "correlation_id": "req-prompt-baseline", "feature": "refund", "level": "info", "ts": "2026-08-11T07:59:35.683974Z"}
```

## 2. PII bị che trước khi ghi log

Tổng số dòng log chứa marker `[REDACTED_*]`: **69**. Số PII còn lộ nguyên văn theo `validate_logs.py`: **0**.

| Input gốc gửi vào API | Loại PII | Nội dung được ghi xuống log |
|---|---|---|
| `What is your refund policy? My email is student@vinuni.edu.vn` | EMAIL | `What is your refund policy? My email is [REDACTED_EMAIL]` |
| `Here is my phone 0987654321, what should be logged?` | PHONE_VN | `Here is my phone [REDACTED_PHONE_VN], what should be logged?` |
| `What is the policy for PII and credit card 4111 1111 1111 1111?` | CREDIT_CARD | `What is the policy for PII and credit card [REDACTED_CREDIT_CARD]?` |
