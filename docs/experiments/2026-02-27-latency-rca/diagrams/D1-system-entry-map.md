# D1 System Entry Map (AS-IS)

```mermaid
flowchart TD
  subgraph INIT["Initial State"]
    U1["Trigger: UI regenerate click or API call"]
    U2["Env: Vercel FEEDOPS_PIPELINE_URL, Cloud Run runtime vars"]
    U3["Mode: simple or with_feedback, async_mode true/false"]
    U4["Target: platform and content_type"]
  end

  U1 --> V1["Dashboard API /api/regenerate"]
  U1 --> V2["Dashboard API /api/regenerate/status/[jobId]"]

  V1 --> V3{"Validate request + pipeline URL?"}
  V3 -->|"No"| E1["HTTP errorResponse (code/step/actionable_message)"]
  V3 -->|"Yes"| V4["resolveCanonicalMasterSku + ensureSkuData"]
  V4 --> V5["POST Cloud Run /regenerate with X-Request-ID"]

  V5 --> P1{"Pipeline status OK?"}
  P1 -->|"No"| E1
  P1 -->|"Yes async"| V6["Return queued job_id/status/request_id/deduplicated"]
  P1 -->|"Yes sync"| V7["Return content/state/idempotent/version/request_id"]

  V6 --> UI1["RegenerateButton poll loop (<=180s)"]
  UI1 --> V2
  V2 --> V8["GET Cloud Run /regenerate/status/{job_id}"]
  V8 --> UI2{"Job state"}
  UI2 -->|"pending/running"| UI1
  UI2 -->|"completed"| UI3["Show success + reload"]
  UI2 -->|"failed"| UI4["Show actionable error"]

  V7 --> UI3
```

## Legend
- Dashboard entrypoints: `/dashboard/src/app/api/regenerate/*`
- Pipeline endpoints: `/src/feedops/api/main.py` (`/regenerate`, `/regenerate/status/{job_id}`)
- Polling semantics: client-side in `RegenerateButton.tsx`
