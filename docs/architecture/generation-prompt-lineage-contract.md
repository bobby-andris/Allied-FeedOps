# Generation Prompt Lineage Contract

## Purpose
This document defines how prompt-bearing generation calls are assembled, hashed, persisted, and audited.

## Why This Matters

The production-divergence incident proved that prompt parity cannot be asserted from source review alone. We must be able to compare:

- the prompt source code expected to run,
- the prompt the runtime actually sent to the provider,
- and the prompt persisted to lineage tables.

## Canonical Prompt Assembly

### Base generation prompts

Base task prompts are assembled from the Python runtime using task-scoped helpers in:

- `src/feedops/generation/tasks.py`
- `src/feedops/api/prompt_loader.py`
- `src/feedops/api/prompt_builder.py`

The canonical prompt shape is:

1. system prompt from Python runtime authority
2. task-specific user prompt built from product data, evidence, route intent, and task kind

### Hybrid adaptation prompts

Hybrid variant adaptation prompts are assembled separately and are expected to differ from base prompts because they operate on shared family output plus variant-specific spec deltas.

### Finish generation prompts

Finish generation is its own provider-backed call for Google/Bing descriptions and is now a first-class lineage event.

## Persistence Contract

Every provider-backed prompt call must persist a `regeneration_history` row.

That includes:

1. base title generation
2. base description generation
3. finish generation
4. hybrid adaptation generation

## Required Stored Fields

Every lineage row must persist, when available:

- `request_id`
- `master_sku`
- `platform`
- `content_type`
- `system_prompt`
- `user_prompt`
- `prompt_hash`
- `model_version`
- token counts
- cost
- latency
- provider attempt count
- parse retry count

## Finish Prompt Convention

Finish generation rows use:

- `platform = "finish"`
- `content_type = "finish_sentences"`

The generated finish map is also persisted to `variant_finish_sentences` for Google/Bing description expansion.

## Hashing Contract

The system must support exact parity comparisons between expected and stored prompts by persisting the final prompt fields and the computed hashes.

At minimum, prompt audit must compare:

1. exact `system_prompt`
2. exact `user_prompt`
3. exact `prompt_hash`

## Audit Requirements

For a certified live run, we must be able to reconstruct the expected prompt from source and prove it matches the stored lineage row.

The audit should cover:

- single title-only
- single description-only
- batch title-only
- batch description-only
- hybrid title-only
- hybrid description-only
- finish generation rows for Google/Bing description paths

## What Does Not Count As Prompt Authority

These are not runtime prompt authorities:

- `dashboard/src/lib/regeneration/prompts.ts`
- historical prompt docs under `docs/prompts/`
- Supabase `prompt_templates.system_prompt`

They may exist for legacy reference, examples, or historical lineage, but they must not override the Python runtime prompt path.
