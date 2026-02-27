# D6 Persistence + Lineage Map (AS-IS)

```mermaid
flowchart TD
  subgraph INIT["Initial State"]
    I1["Request has request_id context"]
    I2["Regeneration mode simple/with_feedback"]
    I3["Content may be unchanged or changed"]
  end

  I1 --> P1["_persist_regeneration_result"]
  P1 --> P2["_load_generated_content_row"]
  P2 --> P3{"candidate_content unchanged?"}

  P3 -->|"Yes"| P4["Return state=no_change idempotent=true"]
  P3 -->|"No"| P5["Upsert/update generated_content (version++)"]

  P5 --> P6["_require_request_id"]
  P6 --> P7["Insert regeneration_history"]
  P7 --> P8["feature_flags_active + generation_diagnostics"]
  P7 --> P9["tokens_used + cost_usd + latency_ms + prompt_hash"]

  P5 --> P10{"finish_sentences present and completed?"}
  P10 -->|"Yes"| P11["Upsert variant_finish_sentences"]
  P10 -->|"No"| P12["Skip finish sentence write"]

  I1 --> A1["async_mode=true branch"]
  A1 --> A2["_create_regeneration_job"]
  A2 --> A3["generation_jobs.input_params stores request_id + idempotency_key"]
  A3 --> A4["process_regenerate_job updates status lifecycle"]

  A4 --> A5["status=running -> completed(result) OR failed(error)"]
```

## Legend
- Tables: `generated_content`, `regeneration_history`, `generation_jobs`, `variant_finish_sentences`
- Lineage hard requirement: `_require_request_id` blocks placeholder `"-"` IDs
- Diagnostic attribution currently lands in `regeneration_history`.
