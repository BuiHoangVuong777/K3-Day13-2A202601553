# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: K3 — Day 13 Observability (`K3-Day13-2A202601553`)
- Repository URL: https://github.com/BuiHoangVuong777/K3-Day13-2A202601553
- Commit SHA của phần việc Người 5: `76ebb7b` trên nhánh `feat/task5-qa-investigator`
- Commit SHA cuối: lấy bằng `git rev-parse HEAD` sau khi push (SHA này nộp trên Codelabs)
- Thành viên và vai trò:

| Người | Vai trò | Git identity |
|---|---|---|
| Người 1 | API & Middleware — correlation ID, JSON log, exception handler, metadata request | `Le Minh Nguyen <leminhnguyenai@gmail.com>` |
| Người 2 | Security Engineer — PII redaction, regex scrubber | `HungBil <nguyendonghung70@gmail.com>` |
| Người 3 | Metrics & Dashboard — 6 panel, dashboard contract, validator | `HoangVuongBui <buihoangvuong777@gmail.com>` |
| Người 4 | SRE & Alerts — SLO, alert rules, runbook | `ChiQuang <quangnch@gmail.com>` |
| Người 5 | QA & Chief Investigator — load test, tracing sub-component, prompt versioning, challenge, report | `thdatt <ngthdatt915@gmail.com>` |

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (851 record, 278 correlation ID duy nhất, 0 PII leak) — [`validate_logs_final.txt`](evidence/validate_logs_final.txt); baseline đầu buổi ở [`validate_logs_baseline.txt`](evidence/validate_logs_baseline.txt)
- Tổng số traces: **150 trace** trên Langfuse Cloud. Ảnh [`trace_list.png`](evidence/trace_list.png) chụp view Observations: `Is Root Observation = True` đếm được **150** (mỗi root observation là một trace) và **436 SPAN** con mang tên `rag-retrieval` / `prompt-resolve` / `llm-generate`. 45 trace gần nhất được xuất kèm metadata (session, tag correlation ID, prompt label/version) trong [`traces.md`](evidence/traces.md) / [`traces.json`](evidence/traces.json)
- Số PII leak còn lại: **0** (email, số điện thoại VN, CCCD, số thẻ đều bị che trước khi ghi log) — [`log_correlation_and_pii.md`](evidence/log_correlation_and_pii.md)
- Link/đường dẫn dashboard: [`dashboard_overview.png`](evidence/dashboard_overview.png), [`dashboard_incident.png`](evidence/dashboard_incident.png); contract tại [`config/dashboard.yaml`](../config/dashboard.yaml)

## 3. Logging và tracing

- **Evidence correlation ID**: [`log_correlation_and_pii.md`](evidence/log_correlation_and_pii.md) mục 1. Mỗi request sinh 5 dòng log ở 2 service (`api` và `agent`) mang cùng `correlation_id`, cùng `user_id_hash`, `session_id`, `feature`, `model`, `env`. Correlation ID do middleware sinh theo dạng `req-<8 hex>` hoặc nhận lại từ header `x-request-id`, và được trả về client qua header cùng tên.
- **Evidence PII redaction**: [`log_correlation_and_pii.md`](evidence/log_correlation_and_pii.md) mục 2. Ví dụ `student@vinuni.edu.vn` → `[REDACTED_EMAIL]`, `0987654321` → `[REDACTED_PHONE_VN]`, `4111 1111 1111 1111` → `[REDACTED_CREDIT_CARD]`. `scrub_event` chạy trong chuỗi processor của structlog **trước** khi JSON được render và ghi xuống file, nên dữ liệu gốc không bao giờ chạm đĩa.
- **Evidence trace waterfall**: ảnh [`trace_waterfall.png`](evidence/trace_waterfall.png), số liệu tương ứng trong [`traces.md`](evidence/traces.md) mục "Trace waterfall" — trace `053fbbc125f8a22af4573b797b297c13`.

| Span | Kiểu | Thời lượng |
|---|---|---|
| `run` | generation (root) | 2665 ms |
| `rag-retrieval` | span | 2507 ms |
| `prompt-resolve` | span | 0 ms |
| `llm-generate` | span | 151 ms |

  Ảnh này cũng là bằng chứng gọn nhất cho cả chuỗi ba tầng: waterfall chỉ ra span chậm, tag `req-46f915b6` là correlation ID trong log, metadata mang `slowest_span`, `retrieval_ms`, `llm_ms`.

- **Giải thích một span đáng chú ý**: `rag-retrieval` là span bọc `app/mock_rag.py::retrieve()`. Ở trạng thái bình thường span này gần 0 ms vì corpus nằm trong bộ nhớ; trong incident nó chiếm 2507/2665 ms — tức **94%** thời gian của cả request. Chính span này biến "API chậm" thành một câu trả lời cụ thể: chậm ở tầng retrieval, không phải ở model. Metadata của span mang theo `correlation_id`, `doc_count` và `duration_ms`, nên từ một span có thể quay ngược về đúng dòng log.

### Cách 3 tầng được nối với nhau

Trước khi làm phần này, log và trace là hai thế giới tách rời: log có `correlation_id`, Langfuse có `trace_id`, không có gì nối chúng. Ba thay đổi đã khép kín vòng:

1. `app/agent.py` ghi event `trace_linked` chứa cả `correlation_id` (từ contextvars) lẫn `trace_id` + `trace_url`.
2. `correlation_id` được đẩy lên Langfuse dưới dạng **tag của trace**, nên tra ngược từ Langfuse UI về log chỉ cần dán correlation ID vào ô filter.
3. Event `span_timings` ghi `retrieval_ms` / `prompt_ms` / `llm_ms` / `slowest_span` xuống log, nên on-call quy được trách nhiệm latency mà **không cần** mở UI — hữu ích khi Langfuse không truy cập được.

## 4. Prompt versioning

Đầy đủ trong [`prompt_versions.md`](evidence/prompt_versions.md) / [`prompt_versions.json`](evidence/prompt_versions.json), log chạy trong [`prompt_versions_run.txt`](evidence/prompt_versions_run.txt). Tự động hoá bằng [`scripts/qa_prompt_versions.py`](../scripts/qa_prompt_versions.py).

Ảnh danh sách hai version trên Langfuse: [`prompt_versions.png`](evidence/prompt_versions.png).

- Prompt name: `day13-chat` (type `text`, giữ nguyên 3 biến `{{feature}}`, `{{docs}}`, `{{message}}`)
- Version/label baseline: **v1**, labels `baseline` + `production`
- Version/label candidate: **v2**, labels `candidate` + `latest` — khác v1 đúng một dòng: `Keep the response concise and structured.`
- Trace ID của mỗi version (cùng một input `What is your refund policy?`):

| Bước | Label yêu cầu | Version phục vụ | Correlation ID | Trace ID |
|---|---|---|---|---|
| Chạy với `baseline` | `baseline` | **v1** | `req-prompt-baseline` | `8a812c62cf3a4fcc6227b4fb8abd8e5b` |
| Chạy với `candidate` | `candidate` | **v2** | `req-prompt-candidate` | `c72a35ada92c8ad1b57f90cd75ec74fb` |
| Sau khi chuyển `production` → v2 | `production` | **v2** | `req-prompt-production-v2` | `57e3c36ad37f695058954ae3fb8715b3` |
| Sau khi rollback `production` → v1 | `production` | **v1** | `req-prompt-production-rollback` | `da15ceb6a0802f9255f1116b4ea7b1e6` |

- Bằng chứng đổi label hoặc rollback: trạng thái label được chụp bằng Langfuse API tại ba thời điểm, ghi trong [`prompt_versions.md`](evidence/prompt_versions.md):

| Thời điểm | v1 | v2 |
|---|---|---|
| Trước khi thao tác | `baseline`, `production` | `candidate`, `latest` |
| Sau khi promote | `baseline` | `candidate`, `latest`, **`production`** |
| Sau khi rollback | `baseline`, **`production`** | `candidate`, `latest` |

Hai ảnh chụp metadata của hai trace cùng label `production` là bằng chứng trực quan của thao tác rollback:

| Ảnh | Trace | `prompt_label` | `prompt_version` |
|---|---|---|---|
| [`prompt_rollback_v2.png`](evidence/prompt_rollback_v2.png) | `57e3c36ad37f695058954ae3fb8715b3` | `production` | **2** |
| [`prompt_rollback_v1.png`](evidence/prompt_rollback_v1.png) | `da15ceb6a0802f9255f1116b4ea7b1e6` | `production` | **1** |

Hai dòng cuối của bảng label ở trên là bằng chứng rollback: cùng một label `production`, cùng một input, nhưng version phục vụ đổi từ v2 về v1 mà không cần sửa code — chỉ đổi label trên Langfuse rồi khởi động lại app. Mỗi trace được script kiểm tra lại bằng API (`ingested: true`) nên không có trace nào chỉ tồn tại trong log.

Version prompt còn được ghi xuống log qua event `prompt_resolved` (`prompt_name`, `prompt_label`, `prompt_version`, `prompt_source`), nên truy được request nào đã dùng prompt nào ngay trong `data/logs.jsonl`. Khi Langfuse không khả dụng, `prompt_source` chuyển thành `local` hoặc `local-fallback` thay vì giả vờ đã lấy được prompt managed.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.`
- Evidence dashboard: [`submission/evidence/dashboard_overview.png`](evidence/dashboard_overview.png) (toàn bộ 6 panel, đơn vị, threshold, time range 60 phút, refresh 30s), [`submission/evidence/dashboard_incident.png`](evidence/dashboard_incident.png) (practice incident `rag_slow` + `tool_fail`)

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

- **Latency p95 ≤ 3000ms**: phần lớn request phải trả lời trong 3 giây; vi phạm cho thấy pipeline AI/RAG đang chậm bất thường. Trong evidence, practice `rag_slow` đẩy p95/p99 lên ~2650ms — chưa vượt SLO nhưng đã vượt ngưỡng cảnh báo sớm 2000ms của challenge contract.
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

Dashboard hiển thị cửa sổ 60 phút, alert yêu cầu điều kiện duy trì 5 phút để hạn chế cảnh báo do spike ngắn, còn SLO được đánh giá trên cửa sổ 28 ngày. Practice hiện mới chứng minh metric đã vượt threshold, chưa chứng minh điều kiện duy trì đủ 5 phút; phần này sẽ được xác nhận trong runtime test cuối. Khi alert kích hoạt, runbook đi theo luồng: (1) xác định triệu chứng và khoảng thời gian trên metrics, (2) mở trace bất thường để khoanh vùng span, (3) dùng correlation ID tìm log liên quan, (4) áp dụng mitigation và chỉ đóng alert sau khi chỉ số phục hồi ổn định.

## 6. Điều tra challenge

Báo cáo điều tra đầy đủ, sinh tự động từ log: [`investigation.md`](evidence/investigation.md) (script [`scripts/investigate.py`](../scripts/investigate.py)). Log chạy: [`challenge_run.txt`](evidence/challenge_run.txt), [`challenge_after_fix.txt`](evidence/challenge_after_fix.txt).

- **Challenge ID**: `day13-k3-observability-v1` (cohort K3, incident `rag_slow`, seed 1303, feature `refund`, ngưỡng latency 2000 ms). Lệnh đã chạy đúng theo README: `python scripts/inject_incident.py` rồi `python scripts/load_test.py --challenge --concurrency 5` (3 vòng, 15 request).

- **Triệu chứng từ metrics**: cửa sổ incident `07:22:53Z → 07:25:44Z`.

| Chỉ số | Trước incident | Trong incident | Sau khi tắt |
|---|---|---|---|
| p50 latency | 152 ms | **2654 ms** (17.5×) | 152 ms |
| p95 latency | 1673 ms¹ | **2663 ms** | 153 ms |
| Request vượt 2000 ms | 0/10 | **15/15** | 0/10 |
| Error rate | 0% | **0%** | 0% |
| Token/request | 184.9 | 180.5 | 167.9 |
| Quality mean | 0.88 | 0.86 | 0.86 |

¹ p95 của cửa sổ trước bị kéo lên bởi đúng một request cold start (lần đầu phải fetch prompt từ Langfuse); p50 = 152 ms mới là mức bình thường.

  Điểm quan trọng: **error rate không đổi**. Sự cố chỉ làm chậm chứ không làm request thất bại, nên alert `HighRequestErrorRate` sẽ không bao giờ bắn — chỉ `HighUserLatency` (p95 > 2000 ms) bắt được. Đây chính là lý do phải có alert theo latency chứ không chỉ theo lỗi.

- **Trace ID liên quan**: `053fbbc125f8a22af4573b797b297c13` — https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/053fbbc125f8a22af4573b797b297c13

  Quy trách nhiệm latency theo span trong toàn bộ cửa sổ incident:

| Span | Mean trước | Mean trong incident | % tổng latency |
|---|---|---|---|
| `rag-retrieval` | 0 ms | **2500.8 ms** | **94.2%** |
| `prompt-resolve` | 33.9 ms | 0 ms | 0.0% |
| `llm-generate` | 150.1 ms | 150.4 ms | 5.7% |

  15/15 request trong incident có `slowest_span = rag-retrieval`.

- **Log line/correlation ID liên quan**: `req-46f915b6` (`latency_ms=2663`, `retrieval_ms=2507`, `llm_ms=150`). Lọc `data/logs.jsonl` theo correlation ID này ra đúng 5 dòng, in đầy đủ trong [`investigation.md`](evidence/investigation.md):

```json
{"service": "agent", "trace_id": "053fbbc125f8a22af4573b797b297c13", "latency_ms": 2663, "retrieval_ms": 2507, "prompt_ms": 0, "llm_ms": 150, "slowest_span": "rag-retrieval", "event": "span_timings", "correlation_id": "req-46f915b6", "feature": "refund", "ts": "2026-08-11T07:23:01.846125Z"}
```

- **Root cause**: `app/mock_rag.py::retrieve()` chèn `time.sleep(2.5)` cố định khi cờ incident `rag_slow` được bật. Vì toàn bộ 5 query chính thức của challenge đều là `feature=refund` và đều đi qua retrieval, mọi request đều cộng thêm đúng ~2.5 giây. Phần còn lại của pipeline không đổi: prompt vẫn là `day13-chat` v1 label `production` từ Langfuse, model vẫn sinh ~180 token trong ~150 ms.

  Các giả thuyết bị loại bằng số liệu: model sinh dài hơn (token/request 184.9 → 180.5, `llm-generate` 150.1 → 150.4 ms), retry do lỗi (0 bản ghi `request_failed`), fetch prompt chậm (`prompt-resolve` = 0 ms, `prompt_source=langfuse` không đổi), retrieval trả tài liệu kém nên phải sinh lại (`doc_count` và quality gần như không đổi).

- **Yếu tố khuếch đại (phát hiện thêm)**: server đo 2.66 s/request nhưng client đo tới **13.3 s** khi chạy `--concurrency 5`. Nguyên nhân là endpoint `/chat` khai báo `async def` nhưng `LabAgent.run` chạy hoàn toàn đồng bộ (`time.sleep`), nên nó **chặn event loop**: 5 request đồng thời bị xếp hàng tuần tự thay vì chạy song song. Một dependency chậm vì thế bị nhân lên theo số request đồng thời — độ trễ người dùng thực tế xấu hơn 5× so với con số server tự báo.

- **Fix action**:
  1. Tức thời: tắt nguồn gây chậm — `python scripts/inject_incident.py --disable`. Đã xác minh: p95 về **153 ms**, 0/10 request vượt ngưỡng ([`challenge_after_fix.txt`](evidence/challenge_after_fix.txt)).
  2. Với hệ thống thật: đặt timeout + fallback cho lời gọi retrieval (trả tài liệu rỗng kèm cảnh báo thay vì chờ vô hạn), và đẩy phần retrieval đồng bộ sang threadpool (`starlette.concurrency.run_in_threadpool`) để một dependency chậm không làm tuần tự hoá toàn bộ traffic.

- **Preventive measure**:
  1. `HighUserLatency` (p95 > 2000 ms trong 5 phút) là alert duy nhất bắt được lớp sự cố này — giữ nguyên và không thay bằng alert error rate.
  2. Thêm SLO riêng cho từng span (ví dụ `rag-retrieval` p95 ≤ 200 ms) để phát hiện suy giảm ở tầng phụ thuộc trước khi nó lan tới latency tổng.
  3. Giữ event `span_timings` trong log: khi Langfuse không truy cập được, on-call vẫn quy được trách nhiệm latency chỉ bằng `data/logs.jsonl`.
  4. Thêm test hồi quy cho instrumentation ([`tests/test_agent_span_instrumentation.py`](../tests/test_agent_span_instrumentation.py)) để chuỗi correlation ID → trace ID → span timing không bị mất khi refactor.

## 7. Đóng góp cá nhân

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Người 1 — Le Minh Nguyen | Middleware correlation ID, bind metadata request, exception handler, JSON log | `21c0623` finish task 1 cp 1 | Context phải được clear và bind trước dòng log đầu tiên thì mọi log sau mới dùng chung được |
| Người 2 — HungBil | PII redaction, regex phone VN, scrubber trong processor chain | `7a57bfb` fix: detect and redact Vietnamese phone PII | Scrub phải nằm trước bước render JSON, nếu không dữ liệu gốc đã kịp chạm đĩa |
| Người 3 — HoangVuongBui | Dashboard contract 6 panel, validator, đo `error_rate_pct` | `f1a02e5`, `0319cfe` | Mỗi panel cần event/field/aggregation/unit/threshold rõ ràng thì mới kiểm chứng được |
| Người 4 — ChiQuang | SLO, 3 alert rule symptom-based, runbook | `2dd55c6`, `3110b64` | Severity phải suy ra từ ảnh hưởng người dùng, và alert cần duration để tránh alert fatigue |
| **Người 5 — thdatt** | **QA & Chief Investigator** (chi tiết bên dưới) | nhánh `feat/task5-qa-investigator` | Xem phần dưới |

### Chi tiết phần việc của Người 5

**Code đã viết**

| File | Thay đổi |
|---|---|
| [`app/tracing.py`](../app/tracing.py) | Thêm `start_span` / `update_span` (context manager an toàn khi client không hỗ trợ span), `current_trace_id`, `trace_url` có cache prefix |
| [`app/agent.py`](../app/agent.py) | Bọc 3 sub-span `rag-retrieval` / `prompt-resolve` / `llm-generate`; đẩy `correlation_id` lên tag trace; ghi 3 event log `trace_linked`, `prompt_resolved`, `span_timings` |
| [`scripts/qa_prompt_versions.py`](../scripts/qa_prompt_versions.py) | Tự động hoá toàn bộ 6 bước prompt versioning + verify trace đã lên Langfuse |
| [`scripts/investigate.py`](../scripts/investigate.py) | Dựng lại dòng thời gian incident từ log, so sánh 3 cửa sổ, quy trách nhiệm latency theo span, in chuỗi bằng chứng |
| [`scripts/qa_export_traces.py`](../scripts/qa_export_traces.py) | Xuất danh sách trace + waterfall từ Langfuse API ra evidence kiểm chứng được |
| [`scripts/qa_check_submission.py`](../scripts/qa_check_submission.py) | Kiểm tra trước khi nộp: link evidence còn sống, đủ mục theo `SUBMISSION.md`, report không bỏ trống, Git không lộ secret |
| [`scripts/load_test.py`](../scripts/load_test.py), [`scripts/inject_incident.py`](../scripts/inject_incident.py) | Cho phép đổi base URL qua `DAY13_BASE_URL` (mặc định vẫn là cổng 8000 như tài liệu) |
| [`tests/test_agent_span_instrumentation.py`](../tests/test_agent_span_instrumentation.py) | 4 test cho instrumentation: thứ tự span, span lỗi khi retrieval hỏng, log nối correlation ID ↔ trace ID, tag correlation ID |

**Một lỗi tự tìm và tự sửa**: bản instrumentation đầu tiên gọi `langfuse.get_trace_url()` ở mỗi request. Hàm này gọi API project của Langfuse mỗi lần khi chạy bên trong một span đang active, làm latency tăng từ 150 ms lên ~380 ms — tức chính công cụ đo lại làm hỏng thứ nó đo. Đã đo lại từng lời gọi để khoanh vùng, rồi cache phần cố định của URL; overhead còn ~2 ms.

**Điều đã học**

- Instrumentation phải được đo chi phí như code production: một lời gọi mạng ẩn trong đường nóng đủ để làm sai lệch mọi số liệu latency của cả buổi lab.
- Trace chỉ là bằng chứng khi nó thật sự nằm trên server. Bốn trace prompt versioning đầu tiên có trong log nhưng không lên Langfuse vì tiến trình bị tắt trước chu kỳ export 5 giây của OTel — từ đó luôn verify lại bằng API thay vì tin vào log.
- Chuỗi metrics → traces → logs chỉ khép kín khi có một khoá chung. Trước khi thêm `trace_linked`, không có cách nào đi từ một điểm bất thường trên dashboard tới đúng trace và đúng dòng log.
- p95 trên mẫu nhỏ rất dễ bị một request cold start kéo lệch; phải đọc kèm p50 và nói rõ nguồn gốc con số thay vì báo cáo tỉ lệ đẹp.

### Danh mục evidence

| Yêu cầu | Ảnh | File kiểm chứng được |
|---|---|---|
| Kết quả `validate_logs.py` | — | [`validate_logs_final.txt`](evidence/validate_logs_final.txt), [`validate_logs_baseline.txt`](evidence/validate_logs_baseline.txt) |
| Danh sách ≥ 10 traces | [`trace_list.png`](evidence/trace_list.png) (150 root observation) | [`traces.md`](evidence/traces.md), [`traces.json`](evidence/traces.json) (45 trace, xuất trực tiếp từ Langfuse API) |
| Một trace waterfall | [`trace_waterfall.png`](evidence/trace_waterfall.png) | [`traces.md`](evidence/traces.md) mục "Trace waterfall" |
| Hai prompt version + trace đúng version/label | [`prompt_versions.png`](evidence/prompt_versions.png) | [`prompt_versions.md`](evidence/prompt_versions.md) |
| Bằng chứng đổi label / rollback | [`prompt_rollback_v2.png`](evidence/prompt_rollback_v2.png), [`prompt_rollback_v1.png`](evidence/prompt_rollback_v1.png) | [`prompt_versions.md`](evidence/prompt_versions.md), [`prompt_versions_run.txt`](evidence/prompt_versions_run.txt) |
| Log có correlation ID | — | [`log_correlation_and_pii.md`](evidence/log_correlation_and_pii.md) mục 1 |
| PII đã redact | — | [`log_correlation_and_pii.md`](evidence/log_correlation_and_pii.md) mục 2 |
| Kết quả `validate_dashboard.py` | — | [`validate_dashboard.txt`](evidence/validate_dashboard.txt) |
| Dashboard 6 nhóm chỉ số | [`dashboard_overview.png`](evidence/dashboard_overview.png), [`dashboard_incident.png`](evidence/dashboard_incident.png) | [`config/dashboard.yaml`](../config/dashboard.yaml) |
| Điều tra challenge | [`trace_waterfall.png`](evidence/trace_waterfall.png) | [`investigation.md`](evidence/investigation.md), [`challenge_run.txt`](evidence/challenge_run.txt), [`challenge_after_fix.txt`](evidence/challenge_after_fix.txt) |
| Snapshot `/metrics` theo 3 pha (bổ sung) | [`metrics_before_challenge.json`](evidence/metrics_before_challenge.json), [`metrics_during_challenge.json`](evidence/metrics_during_challenge.json), [`metrics_after_fix.json`](evidence/metrics_after_fix.json) |

Challenge được chạy hai lần trong buổi (`05:40:09Z–05:41:15Z` và `07:22:53Z–07:25:44Z`), cùng cho một kết luận. Báo cáo này dùng lần chạy thứ hai vì có đủ ba cửa sổ trước/trong/sau. Evidence của lần chạy đầu vẫn được giữ lại để đối chiếu: [`challenge_recovery.txt`](evidence/challenge_recovery.txt), [`investigation.json`](evidence/investigation.json), [`log_evidence.md`](evidence/log_evidence.md), [`traces_inventory.md`](evidence/traces_inventory.md) — sinh bởi [`scripts/qa_investigate.py`](../scripts/qa_investigate.py) và [`scripts/qa_trace_inventory.py`](../scripts/qa_trace_inventory.py).

### Cách chạy lại toàn bộ

```bash
uvicorn app.main:app --env-file .env            # cổng khác: thêm --port 8010 và đặt DAY13_BASE_URL
python scripts/load_test.py                     # baseline 10 request
python scripts/qa_prompt_versions.py            # prompt v1/v2, promote, rollback + evidence
python scripts/inject_incident.py               # đọc config/challenge.json
python scripts/load_test.py --challenge --concurrency 5
python scripts/inject_incident.py --disable
python scripts/investigate.py                   # sinh submission/evidence/investigation.md
python scripts/qa_export_traces.py              # sinh submission/evidence/traces.md
python -m pytest -q
python scripts/qa_check_submission.py           # kiểm tra bài nộp đã đủ evidence chưa
```
