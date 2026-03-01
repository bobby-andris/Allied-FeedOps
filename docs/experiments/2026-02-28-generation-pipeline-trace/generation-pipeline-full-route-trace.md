# 2026-02-28 Generation Pipeline Full Route Trace

## Purpose
This document is the dated route-trace companion to the canonical architecture docs. It exists to capture the concrete request-to-runtime path that was proven during the production-divergence closure work.

## Traced Routes

### `POST /regenerate`

Path:

1. dashboard review or regenerate orchestration route calls the pipeline via `FEEDOPS_PIPELINE_URL`
2. `src/feedops/api/main.py` derives request scope
3. task specs are built in `src/feedops/generation/executor.py`
4. prompts are built in `src/feedops/generation/tasks.py` and `src/feedops/api/prompt_builder.py`
5. provider-backed tasks execute
6. `generated_content` and `regeneration_history` are updated
7. Google/Bing description flows also refresh `variant_finish_sentences`

### `POST /batch-optimize`

Path:

1. dashboard batch route calls the pipeline via `FEEDOPS_PIPELINE_URL`
2. `src/feedops/api/main.py` creates `batch_generation_jobs`
3. per-SKU work executes using the same scoped task model
4. `batch_generation_job_skus` tracks orchestration state
5. generated artifacts and lineage are written the same way as single-route generation

### `POST /hybrid-generate`

Path:

1. dashboard hybrid route calls the pipeline via `FEEDOPS_PIPELINE_URL`
2. `src/feedops/api/main.py` creates the hybrid job
3. shared family generation runs once
4. shared finish generation runs once when required
5. `src/feedops/api/hybrid_generation.py` adapts content for family members
6. adapted artifacts and lineage are persisted

### `GET /batch-status/{job_id}`

Reads orchestration status from `batch_generation_jobs` and `batch_generation_job_skus`.

## Verified Behavioral Contract

- single title-only: `TITLE` only
- single Google/Bing description-only: `DESCRIPTION_BASE` plus `FINISH_SENTENCES`
- batch title-only: scheduler plus per-SKU `TITLE`
- batch Google/Bing description-only: scheduler plus per-SKU `DESCRIPTION_BASE` and `FINISH_SENTENCES`
- hybrid title-only: one shared `TITLE` plus variant adaptation
- hybrid Google/Bing description-only: one shared `DESCRIPTION_BASE`, one shared `FINISH_SENTENCES`, then variant adaptation

## Canonical Follow-Up Docs

For active operating truth, use:

- `docs/architecture/generation-runtime-truth.md`
- `docs/architecture/generation-core-task-model.md`
- `docs/architecture/generation-prompt-lineage-contract.md`
- `docs/architecture/generation-pipeline-routing-reference.md`
- `docs/experiments/2026-02-28-production-divergence-closure/report.md`
