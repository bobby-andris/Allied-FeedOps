# Prompt Source And Generation Flow (Current Runtime)

## Purpose
This document describes how generation works **in the current codebase** after the PlanFix merges.
It is intentionally runtime-focused and excludes legacy v1 routing behavior as an active path.

## Current Runtime Truth
- Runtime prompt authority is code-owned in `src/feedops/pipeline/prompts.py`.
- Dashboard regenerate route orchestrates only; Python API is the single writer for regeneration persistence.
- Per-platform generation is the active path for regenerate/hybrid/batch generation.
- Regeneration persistence is deterministic:
  - changed content => write `generated_content` + one linked `regeneration_history` row
  - unchanged content => no content/history writes; return `state="no_change"`
- Request lineage is first-class: dashboard forwards `X-Request-ID`, Python returns/persists `request_id`.

## End-To-End Regeneration Flow

```mermaid
flowchart LR
  A["Dashboard UI"] --> B["Next.js /api/regenerate route"]
  B -->|"X-Request-ID + payload"| C["Python API /regenerate (FastAPI)"]
  C --> D["Prompt assembly (code-owned prompt + evidence + rules)"]
  D --> E["GPT-5.2 via OpenAI provider"]
  E --> F["Strict parse and required-key validation"]
  F --> G{"Content changed?"}
  G -->|"No"| H["Return no_change (idempotent=true)"]
  G -->|"Yes"| I["Upsert generated_content (version+1)"]
  I --> J["Insert regeneration_history with request_id"]
  J --> K["Return completed response"]
  H --> K
  K --> L["Dashboard response + operator visibility"]
```

## Prompt Source Lineage (Current)

```mermaid
flowchart TD
  A["src/feedops/pipeline/prompts.py"] --> B["Canonical runtime system prompt"]
  B --> C["Prompt builder / generation pipeline"]
  C --> D["OpenAI provider call"]

  E["prompt_templates table"] --> F["Examples/guidance/reference data"]
  F --> C

  G["dashboard/src/lib/regeneration/prompts.ts"] --> H["Dashboard reference only"]

  style A fill:#e8f5e9
  style B fill:#e8f5e9
  style E fill:#fff8e1
  style G fill:#ffebee
```

Notes:
- `prompt_templates.system_prompt` is not runtime authority for Python generation.
- Dashboard prompt files are not the source of truth for pipeline generation.

## Deterministic Persistence Lifecycle

```mermaid
flowchart LR
  A["/regenerate request"] --> B["Read current generated_content row"]
  B --> C["Generate candidate content"]
  C --> D{"candidate == current?"}
  D -->|"Yes"| E["state=no_change"]
  E --> F["idempotent=true"]
  F --> G["No generated_content write"]
  G --> H["No regeneration_history insert"]

  D -->|"No"| I["version = current + 1"]
  I --> J["Upsert generated_content"]
  J --> K["Insert exactly one regeneration_history row"]
  K --> L["state=completed, idempotent=false"]
```

## Runtime Module Map

```mermaid
flowchart TD
  A["dashboard/src/app/api/regenerate/route.ts"] --> B["src/feedops/api/main.py:/regenerate"]
  B --> C["src/feedops/api/prompt_builder.py"]
  B --> D["src/feedops/pipeline/generator.py"]
  D --> E["src/feedops/providers/openai_provider.py"]
  B --> F["src/feedops/api/prompt_loader.py"]
  B --> G["src/feedops/pipeline/prompts.py"]
  B --> H["Supabase: generated_content / regeneration_history / prompt_templates"]
```

## Response Contract (Regenerate)
Current response contract includes these operational fields:
- `state`: `completed | no_change`
- `idempotent`: boolean
- `generated_content_id`: string | null
- `version`: number
- `request_id`: string

Backward-compatible fields remain available (`content`, `model`, `prompt_hash`, `validation_errors`).

## Policy And Quality Guardrails In Runtime
- Required platform keys are enforced during model payload parse.
- Missing required keys are treated as parse failure and retried.
- If retries still fail contract, API returns actionable error and does not persist partial payload.
- Post-generation quality/policy checks remain in place for channel constraints.

## What This Means For Optimization Work
The v1.3a planning artifacts are still useful as **goal context**, but this runtime architecture document is scoped to what the code does now.
Current optimization work should iterate on:
- better evidence quality
- stronger product-specific prompt constraints
- deterministic parser contracts
- measurable title/description quality outcomes

