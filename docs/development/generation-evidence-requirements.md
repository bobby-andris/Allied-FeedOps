# Generation Evidence Requirements

## Purpose
This document defines what counts as acceptable evidence for a generation-affecting change.

## Evidence Standard

Statements like “fixed,” “ready,” “passing,” and “production-ready” require concrete artifacts. Screenshots or source snippets alone are not enough.

## Required Evidence Layers

### 1. Source evidence

Must include:

- touched files
- route entry point
- task graph summary
- prompt assembly path
- persistence path

### 2. Local container evidence

Must include:

- container smoke run directory
- `summary.json`
- `container.log`

### 3. Cloud Run evidence

Must include:

- deployed commit SHA
- deploy mode
- image ref
- Cloud Run revision
- request IDs and job IDs
- log extract proving actual task execution
- Cloud Build ID when the post-merge `origin/master` production-trigger path was used

### 4. Supabase evidence

Must include reads from:

- `generated_content`
- `regeneration_history`
- `variant_finish_sentences`
- `batch_generation_jobs`
- `batch_generation_job_skus`

### 5. Dashboard evidence

Must include:

- review page URL or route form tested
- proof SKU(s)
- readback result aligned to the fresh Supabase rows

## Prompt Evidence Requirements

If prompts or task scope were touched, the report must show:

- exact prompt authority used
- exact stored prompt parity result
- prompt hashes or exact prompt comparison output

## Minimum Artifacts To Record In The Report

- branch name
- baseline SHA
- final tested SHA
- deploy mode
- image ref
- Cloud Run revision
- Cloud Build ID when applicable
- request IDs
- job IDs where applicable
- report artifact directory
- final decision

## What Does Not Count

These do not count as sufficient production evidence on their own:

- host test pass only
- local manual curl only
- reading source without runtime proof
- dashboard UI check without Supabase row comparison
- Cloud Run logs without request IDs
