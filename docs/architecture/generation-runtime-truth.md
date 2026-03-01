# Generation Runtime Truth

## Purpose
This document defines the runtime truth hierarchy for every generation-affecting change. It exists to prevent the exact source/runtime drift that caused the 2026-02-28 production-divergence closure incident.

## Canonical Runtime Hierarchy

1. **Current source code** under `src/feedops/` and `dashboard/src/` defines intended behavior.
2. **Local container smoke** proves what the Docker/Cloud Run image shape actually executes.
3. **Deployed Cloud Run revision** is the final runtime truth for production behavior.
4. **Supabase lineage and persisted artifacts** prove what the live runtime actually wrote.
5. **Dashboard readback** proves what users actually see.

No generation-affecting work is complete unless all five layers agree.

## Why This Exists

The historical failure pattern was not a single code bug. It was divergence between:

- the code developers intended,
- the container image they tested,
- the Cloud Run revision actually serving traffic,
- the rows persisted to Supabase,
- and the dashboard pages reading those rows back.

That means host tests and source review alone are insufficient.

## Hard Rules

1. Do not claim a generation fix from host tests alone.
2. Do not claim a generation fix from local container smoke alone.
3. Do not assume the deployed Cloud Run revision matches the source branch under review.
4. Any mismatch between source, container, Cloud Run, Supabase, or dashboard is a blocking divergence.
5. The system is only production-ready when the end-to-end path is explainable with concrete evidence.

## What Must Be Proven For Generation Work

For any change affecting prompts, task scope, retries, cost controls, persistence, batch orchestration, hybrid generation, or dashboard generation routing, proof must include:

1. **Source review**
   - exact route entry point
   - exact task graph
   - exact prompt-building path
   - exact persistence path
2. **Local container proof**
   - `ENV_FILE=.env.vercel PORT=18080 scripts/container_generation_smoke.sh`
   - artifact review of `summary.json` and `container.log`
3. **Cloud Run proof**
   - deployed revision id
   - request IDs and job IDs
   - log evidence for provider calls and task summaries
4. **Supabase proof**
   - `generated_content`
   - `regeneration_history`
   - `variant_finish_sentences`
   - `batch_generation_jobs`
   - `batch_generation_job_skus`
5. **Dashboard proof**
   - review page loads the fresh persisted rows
   - no placeholder leaks beyond intentional template contracts

## Runtime Authorities

### Generation runtime
- `src/feedops/api/main.py`
- `src/feedops/api/hybrid_generation.py`
- `src/feedops/generation/`

### Prompt authority
- canonical prompt text and task-scoped prompt assembly live in Python
- dashboard prompt files are reference-only and must not override runtime prompts

### Pipeline endpoint authority
- runtime dashboard routes must resolve the pipeline through `FEEDOPS_PIPELINE_URL`
- hardcoded legacy Cloud Run hostnames are bugs in runtime code paths

### Persistence authority
- Python runtime is the single writer for generation lineage and finish maps

## Required Certification Matrix

Every generation-affecting PR must certify these six scenarios:

1. single Google title-only
2. single Google description-only
3. batch Google title-only
4. batch Google description-only
5. hybrid Google title-only
6. hybrid Google description-only

## Canonical Evidence Documents

Read these first in any future generation-affecting session:

1. `AGENTS.md`
2. `docs/architecture/generation-runtime-truth.md`
3. `docs/architecture/generation-core-task-model.md`
4. `docs/architecture/generation-prompt-lineage-contract.md`
5. `docs/architecture/generation-pipeline-routing-reference.md`
6. `docs/experiments/2026-02-28-production-divergence-closure/report.md`

## If A Fresh Session Starts Mid-Investigation

The first task is not patching. The first task is reconstructing the path:

1. request intent
2. task graph
3. provider call scope
4. persistence rows
5. dashboard readback

If any one of those cannot be tied to live evidence, the system is not yet understood well enough to change safely.
