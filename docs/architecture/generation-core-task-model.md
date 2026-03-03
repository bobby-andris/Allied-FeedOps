# Generation Core Task Model

## Purpose
This document defines the intended task model for single-route, batch, and hybrid generation. It is the semantic contract that source code, container runtime, Cloud Run behavior, Supabase lineage, and dashboard readback must all obey.

## Task Kinds

The scoped runtime uses three provider-backed task kinds:

1. `TITLE`
2. `DESCRIPTION_BASE`
3. `FINISH_SENTENCES`

Hybrid adaptation is a separate follow-on operation derived from shared generation output. It is not a license to run hidden per-variant full regeneration.

## Single Regenerate Contract

### Title-only

Expected task graph:

- `TITLE`

Expected behavior:

- exactly one provider-backed call
- no finish generation
- no hidden description work
- one title lineage row

### Description-only

Expected task graph for Google and Bing:

- `DESCRIPTION_BASE`
- `FINISH_SENTENCES`

Expected behavior:

- exactly two provider-backed calls
- no title work
- one base description lineage row
- one finish prompt lineage row
- one refreshed `variant_finish_sentences` row

Expected task graph for Shopify:

- `DESCRIPTION_BASE`

## Batch Contract

Batch is scheduler/orchestration only. It must not widen generation scope beyond requested platforms and content types.

### Batch title-only

Per SKU expected task graph:

- `TITLE`

Must not do:

- `DESCRIPTION_BASE`
- `FINISH_SENTENCES`

### Batch description-only for Google/Bing

Per SKU expected task graph:

- `DESCRIPTION_BASE`
- `FINISH_SENTENCES`

Must not do:

- title generation
- extra hidden provider-backed work

## Hybrid Contract

Hybrid generation is intentionally different from batch. It uses one shared source generation for a family, then adapts for family members.

### Hybrid title-only

Expected family task graph:

- one shared `TITLE`
- variant adaptation for family members

Must not do:

- per-variant provider-backed full title generation

### Hybrid description-only for Google/Bing

Expected family task graph:

- one shared `DESCRIPTION_BASE`
- one shared `FINISH_SENTENCES`
- variant adaptation for family members

Must not do:

- per-variant provider-backed full description regeneration

## Persistence Expectations

### `generated_content`

Stores current candidate/baseline/approved content artifacts for route outputs.

### `regeneration_history`

Stores lineage rows for every provider-backed prompt call, including:

- base title generation
- base description generation
- finish generation
- hybrid adaptation generation

### `variant_finish_sentences`

Stores product-specific finish maps for Google/Bing description expansion.

### `batch_generation_jobs` and `batch_generation_job_skus`

Track orchestration only. They must not imply hidden task scope that the runtime did not actually execute.

## Dashboard Contract

The dashboard is a read path and orchestration client. It must not create its own shadow generation semantics.

Required behavior:

- read current generated artifacts from Supabase
- read finish maps from `variant_finish_sentences`
- expand variant templates at publish time
- route pipeline calls only through `FEEDOPS_PIPELINE_URL`

## Violation Examples

These are blocking divergences:

1. title-only routes producing finish rows
2. description-only Google/Bing routes skipping `FINISH_SENTENCES`
3. hybrid running full per-variant provider-backed regeneration without being explicitly redesigned and documented
4. dashboard reading stale rows that no longer match the live runtime
5. Cloud Run revision behavior differing from local source intent

## Success Definition

The task model is only satisfied when the exact same graph is visible in:

1. source code
2. local container smoke
3. Cloud Run logs
4. Supabase lineage
5. dashboard readback
