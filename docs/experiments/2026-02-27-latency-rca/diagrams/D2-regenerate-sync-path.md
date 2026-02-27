# D2 Regenerate Sync Path (AS-IS)

```mermaid
flowchart TD
  subgraph INIT["Initial State"]
    I1["Request: async_mode=false"]
    I2["Platform/content_type selected"]
    I3["Request ID bound in middleware"]
  end

  I1 --> A1["POST /regenerate"]
  A1 --> A2["ensure_generation_enabled"]
  A2 --> A3["_require_request_id(get_request_id())"]
  A3 --> A4["_execute_regeneration_request"]

  A4 --> B1["resolve_canonical_master_sku + load_parent_sku"]
  B1 --> B2["get_provider + get_platform_system_prompt_hash"]
  B2 --> B3["build feedback layer and selected_platforms"]
  B3 --> B4["generate_per_platform"]

  B4 --> C1{"Required field present?"}
  C1 -->|"No"| E1["HTTP 502 regenerate_missing_required_platform_field"]
  C1 -->|"Yes"| C2["extract usage_by_platform/latency_by_platform/parse_by_platform"]
  C2 --> C3["_persist_regeneration_result"]

  C3 --> D1{"Current content equals new content?"}
  D1 -->|"Yes"| D2["state=no_change idempotent=true no new write"]
  D1 -->|"No"| D3["update/insert generated_content + insert regeneration_history"]

  D3 --> D4{"Google/Bing description with finish payload?"}
  D4 -->|"Yes"| D5["upsert variant_finish_sentences"]
  D4 -->|"No"| D6["skip finish sentence persistence"]

  D2 --> R1["RegenerateResponse"]
  D5 --> R1
  D6 --> R1

  R1 --> O1["Return success content + state/idempotent/version + request_id"]
```

## Legend
- Primary orchestration: `src/feedops/api/main.py`
- Platform generation fanout: `src/feedops/pipeline/generator.py`
- Idempotent write path: `_persist_regeneration_result`
