# D3 Regenerate Async Path (AS-IS)

```mermaid
flowchart TD
  subgraph INIT["Initial State"]
    I1["Request: async_mode=true"]
    I2["Request hash inputs: SKU/platform/content/feedback/structured fields"]
    I3["Request ID available in context"]
  end

  I1 --> A1["POST /regenerate"]
  A1 --> A2["_require_request_id"]
  A2 --> A3["_regeneration_idempotency_key"]
  A3 --> A4["_find_active_regeneration_job (pending/running)"]

  A4 --> B1{"Matching job exists?"}
  B1 -->|"Yes"| B2["Return RegenerateJobResponse deduplicated=true"]
  B1 -->|"No"| B3["_create_regeneration_job status=pending"]

  B3 --> B4["run_async_in_thread(process_regenerate_job)"]
  B4 --> B5["Return RegenerateJobResponse deduplicated=false"]

  B5 --> C1["Client polls /api/regenerate/status/[jobId]"]
  C1 --> C2["Dashboard proxy GET /regenerate/status/{job_id}"]

  subgraph WORKER["Background Worker process_regenerate_job"]
    W1["Update generation_jobs status=running"]
    W2["_execute_regeneration_request (sync path internally)"]
    W3{"Execution success?"}
    W3 -->|"Yes"| W4["Update generation_jobs status=completed result payload"]
    W3 -->|"No"| W5["Update generation_jobs status=failed error"]
  end

  B4 --> W1
  W4 --> C2
  W5 --> C2

  C2 --> C3{"Status"}
  C3 -->|"pending/running"| C1
  C3 -->|"completed"| C4["Result payload returned"]
  C3 -->|"failed"| C5["Error payload returned"]
```

## Legend
- Job table: `generation_jobs`
- Dedupe key stored in `generation_jobs.input_params.idempotency_key`
- Async status contract: `RegenerateJobStatusResponse`
