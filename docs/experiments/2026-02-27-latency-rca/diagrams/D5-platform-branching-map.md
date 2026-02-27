# D5 Platform Branching Map (AS-IS)

```mermaid
flowchart TD
  subgraph INIT["Initial State"]
    I1["Inputs: platform, content_type, mode, finish_code"]
    I2["Prompt authority: code-owned system prompt"]
    I3["Generator uses per-platform schema contracts"]
  end

  I1 --> G1["_execute_regeneration_request"]
  G1 --> G2{"content_type=description and platform in google/bing?"}
  G2 -->|"Yes"| G3["selected_platforms=[platform, finish]"]
  G2 -->|"No"| G4["selected_platforms=[platform]"]

  G3 --> H1["generate_per_platform"]
  G4 --> H1

  H1 --> H2["Build prompts: google, bing, shopify, finish"]
  H2 --> H3["Build system prompts + prompt hashes + schemas"]
  H3 --> H4["Loop requested platforms in canonical order"]

  H4 --> P1{"platform branch"}
  P1 -->|"google"| PG["GOOGLE_SCHEMA -> google_title/google_description"]
  P1 -->|"bing"| PB["BING_SCHEMA -> bing_title/bing_description"]
  P1 -->|"shopify"| PS["SHOPIFY_SCHEMA -> shopify_title/shopify_description"]
  P1 -->|"finish"| PF["FINISH_SENTENCES_SCHEMA -> finish sentence array"]

  PF --> N1["_normalize_finish_sentence_payload"]
  PG --> O1["raw_by_platform + usage + parse + latency"]
  PB --> O1
  PS --> O1
  N1 --> O1

  O1 --> R1["Return platform payload + diagnostics + finish_sentences"]
```

## Legend
- Execution fanout function: `src/feedops/pipeline/generator.py:377`
- Description+finish expansion trigger: `src/feedops/api/main.py:1428`
- Placeholder/finish rules live in prompt builder and platform skills.
