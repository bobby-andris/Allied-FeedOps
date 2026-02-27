# Prompt Source And Generation Flow (Current Runtime)

## Scope
This document describes the current production architecture only.
It excludes retired v1/v2 runtime routing decisions and focuses on the code path active on `master` after deterministic regeneration + async enqueue landing.

## Runtime Authority

1. Canonical system prompt authority is code-owned in `src/feedops/pipeline/prompts.py`.
2. Platform system prompt assembly is in `src/feedops/pipeline/skill_loader.py`.
3. Generation orchestration is in `src/feedops/pipeline/generator.py` via `generate_per_platform()`.
4. Regeneration persistence authority is in `src/feedops/api/main.py` (`_persist_regeneration_result`).
5. Dashboard route `dashboard/src/app/api/regenerate/route.ts` is orchestration only.
6. Supabase `prompt_templates` is guidance/evidence input, not system-prompt authority.

## What Is Explicitly Not Runtime Authority

1. `dashboard/src/lib/regeneration/prompts.ts` (legacy/reference only).
2. `prompt_templates.system_prompt` in Supabase (historical lineage only).
3. `FEEDOPS_PROMPT_VERSION` runtime branching for generation behavior.

## Codebase Module Map

```mermaid
flowchart TD
  subgraph UI["Dashboard (Next.js)"]
    RB["RegenerateButton.tsx"]
    NXREG["POST /api/regenerate"]
    NXSTAT["GET /api/regenerate/status/{jobId}"]
  end

  subgraph API["Cloud Run FastAPI"]
    REG["POST /regenerate"]
    JOB["process_regenerate_job"]
    STAT["GET /regenerate/status/{job_id}"]
    EXEC["_execute_regeneration_request"]
    PERSIST["_persist_regeneration_result"]
  end

  subgraph PIPE["Prompt + Generation Pipeline"]
    PB["prompt_builder.py"]
    PL["prompt_loader.py"]
    SK["skill_loader.py"]
    GEN["generate_per_platform()"]
    OPROV["OpenAIProvider.generate()"]
    PARSE["_parse_json_payload()"]
  end

  subgraph DB["Supabase"]
    GJ["generation_jobs"]
    GC["generated_content"]
    RH["regeneration_history"]
    PT["prompt_templates"]
    VF["variant_finish_sentences"]
    SC["sku_corrections"]
  end

  RB --> NXREG
  NXREG --> REG
  NXSTAT --> STAT
  REG --> GJ
  REG --> JOB
  JOB --> EXEC
  EXEC --> PB
  EXEC --> PL
  EXEC --> SK
  EXEC --> GEN
  GEN --> OPROV
  OPROV --> PARSE
  EXEC --> PERSIST
  PERSIST --> GC
  PERSIST --> RH
  EXEC --> VF
  EXEC --> SC
  PB --> PT
  STAT --> GJ
```

## Exact GPT-5.2 Invocation Path

```mermaid
sequenceDiagram
  participant UI as "Dashboard UI"
  participant NX as "Next.js API"
  participant API as "FastAPI"
  participant GEN as "Generator"
  participant OAI as "OpenAI Provider"
  participant GPT as "OpenAI Chat Completions (gpt-5.2)"
  participant DB as "Supabase"

  UI->>NX: "POST /api/regenerate (async_mode=true)"
  NX->>API: "POST /regenerate + X-Request-ID"
  API->>DB: "INSERT generation_jobs(status=pending)"
  API-->>NX: "RegenerateJobResponse(job_id, request_id)"
  NX-->>UI: "Queued response"

  API->>API: "process_regenerate_job(job_id, request_payload)"
  API->>DB: "UPDATE generation_jobs(status=running)"
  API->>GEN: "generate_per_platform(parent_sku, provider, ...)"

  GEN->>OAI: "provider.generate(prompt, schema, system_prompt)"
  OAI->>GPT: "chat.completions.create(model='gpt-5.2')"
  GPT-->>OAI: "structured JSON text"
  OAI->>OAI: "_parse_json_payload(expected_keys)"

  alt "required keys missing / parse fail"
    OAI->>OAI: "retry loop"
    OAI-->>GEN: "LLMError if retries exhausted"
  else "parse success"
    OAI-->>GEN: "platform payload"
  end

  GEN-->>API: "generated payload + hashes + usage + parse diagnostics"
  API->>API: "_persist_regeneration_result()"

  alt "candidate unchanged"
    API->>DB: "no generated_content write"
    API->>DB: "no regeneration_history write"
  else "candidate changed"
    API->>DB: "upsert/update generated_content (version +1)"
    API->>DB: "insert regeneration_history (single row)"
  end

  API->>DB: "UPDATE generation_jobs(status=completed|failed, result|error)"
```

## Deterministic Persistence State Machine

```mermaid
flowchart TD
  A["Load current generated_content row by (master_sku, platform, content_type)"] --> B["Compute candidate_content"]
  B --> C{"candidate == current?"}

  C -->|"Yes"| D["state = no_change"]
  D --> E["idempotent = true"]
  E --> F["version = current version"]
  F --> G["skip generated_content write"]
  G --> H["skip regeneration_history insert"]

  C -->|"No"| I["state = completed"]
  I --> J["idempotent = false"]
  J --> K["version = current + 1"]
  K --> L["write generated_content"]
  L --> M["insert one regeneration_history row"]
```

## Async Job Lifecycle

```mermaid
flowchart LR
  P["pending"] --> R["running"]
  R --> C["completed"]
  R --> F["failed"]
  P --> F
```

`process_regenerate_job()` now catches failures that occur during the initial `pending -> running` transition and writes terminal `failed` status when possible.

## Prompt Construction (Current)

1. `generate_per_platform()` loads platform-specific system prompts via `get_platform_system_prompt(platform)`.
2. User prompts are built per platform via:
   - `build_google_prompt()`
   - `build_bing_prompt()`
   - `build_shopify_prompt()`
   - `build_finish_prompt()`
3. Prompt evidence inputs include:
   - product evidence table
   - keyword placement plan
   - category guidance (`prompt_templates.category_guidance`)
   - gold example bundle (`prompt_templates.gold_standard_examples`)
4. Prompt hash lineage is stored per platform and propagated into persistence/history surfaces.

## Request-ID Lineage

1. Dashboard forwards `X-Request-ID` to FastAPI.
2. FastAPI includes `request_id` in regenerate responses.
3. `request_id` is persisted in `regeneration_history` for traceability.
4. `generation_jobs.request_id` links async polling and final lineage queries.

## Deployment Pipeline (Current)

```mermaid
flowchart LR
  GH["Merge to master"] --> GHA["GitHub Actions checks"]
  GHA --> CB["Cloud Build"]
  CB --> IMG["Container image"]
  IMG --> CR["Cloud Run revision"]
  CR --> API["Live /regenerate + /regenerate/status"]
```

Operational note: a merged PR is not equivalent to an active Cloud Run revision until Cloud Build deploy completes and traffic moves to the new revision.

## Why A Single Regenerate Can Feel Slow

A synchronous regenerate may include multiple sequential provider calls (`google`, `bing`, `shopify`, `finish`) plus parsing/retries and persistence. Async mode avoids UI timeout by queueing work and returning immediately.

## Runtime Drift Guards

1. `backend-parity` workflow enforces parity suites on `master` and `main` branch PR/push triggers.
2. `scripts/verify_locked_parity.sh` runs frozen tests and fails on lockfile drift.
3. Strict parse contract rejects missing required keys instead of accepting partial payloads.
4. Deterministic single-writer persistence prevents duplicate or conflicting DB writes.
