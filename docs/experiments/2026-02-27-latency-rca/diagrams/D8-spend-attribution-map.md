# D8 Spend Attribution Map (AS-IS)

```mermaid
flowchart TD
  subgraph INIT["Initial State"]
    I1["User intent: regenerate one SKU/platform/content"]
    I2["Mode: simple or with_feedback, sync or async"]
    I3["Expectation: one request ~= one provider call"]
  end

  I1 --> S1["Dashboard submitRegeneration"]
  S1 --> S2["Cloud Run /regenerate"]

  S2 --> S3{"Branch expansion"}
  S3 -->|"description google/bing"| S4["selected_platforms includes finish"]
  S3 -->|"otherwise"| S5["single platform only"]

  S4 --> S6["Provider calls per request >= 2"]
  S5 --> S7["Provider calls per request >= 1"]

  S6 --> R1{"Provider retry stack"}
  S7 --> R1

  R1 --> R2["SDK retries (client max_retries)"]
  R1 --> R3["Provider retry loop (self.max_retries)"]
  R1 --> R4["JSON repair loop append + retry"]
  R1 --> R5["Completion budget bump path"]

  R2 --> U1["last_usage prompt/completion/cached tokens"]
  R3 --> U1
  R4 --> U1
  R5 --> U1

  U1 --> A1["_estimate_openai_cost_usd_from_usage"]
  A1 --> A2["Persist tokens_used/cost_usd in regeneration_history"]

  S1 --> D1{"Duplicate submissions?"}
  D1 -->|"Before dedupe"| D2["Repeated identical requests can multiply spend"]
  D1 -->|"After dedupe enabled"| D3["Active job reused, new spend suppressed"]
```

## Legend
- Spend can amplify via branch expansion and layered retries even when user action appears singular.
- Historical rows lacking `tokens_used/cost_usd/request_id` impede post-hoc reconciliation.
