# Evidence prompt versioning

- Prompt name: `day13-chat`
- Input dùng chung cho mọi version: `What is your refund policy?`

## Trạng thái label

| Thời điểm | Label theo version |
|---|---|
| Trước khi thao tác | `{'v1': ['baseline', 'production'], 'v2': ['candidate', 'latest']}` |
| Sau khi chuyển `production` sang v2 | `{'v1': ['baseline'], 'v2': ['candidate', 'latest', 'production']}` |
| Sau khi rollback `production` về v1 | `{'v1': ['baseline', 'production'], 'v2': ['candidate', 'latest']}` |

## Trace của từng bước

| Bước | Label yêu cầu | Version phục vụ | Source | Correlation ID | Trace ID | Đã lên Langfuse |
|---|---|---|---|---|---|---|
| baseline | `baseline` | `v1` | `langfuse` | `req-prompt-baseline` | `8a812c62cf3a4fcc6227b4fb8abd8e5b` | có |
| candidate | `candidate` | `v2` | `langfuse` | `req-prompt-candidate` | `c72a35ada92c8ad1b57f90cd75ec74fb` | có |
| production-v2 | `production` | `v2` | `langfuse` | `req-prompt-production-v2` | `57e3c36ad37f695058954ae3fb8715b3` | có |
| production-rollback | `production` | `v1` | `langfuse` | `req-prompt-production-rollback` | `da15ceb6a0802f9255f1116b4ea7b1e6` | có |

## Link trace

- baseline: https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/8a812c62cf3a4fcc6227b4fb8abd8e5b
- candidate: https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/c72a35ada92c8ad1b57f90cd75ec74fb
- production-v2: https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/57e3c36ad37f695058954ae3fb8715b3
- production-rollback: https://cloud.langfuse.com/project/cmso6invc04raad0dgqjxwdeq/traces/da15ceb6a0802f9255f1116b4ea7b1e6
