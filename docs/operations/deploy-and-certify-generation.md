# Deploy And Certify Generation

## Purpose
This is the production playbook for generation-affecting changes.

## Deploy Inputs To Capture

- tested commit SHA
- Cloud Build ID
- image ref
- Cloud Run service URL
- Cloud Run revision

## Deploy Sequence

1. merge the feature branch into `master`
2. deploy through the normal Cloud Build path
3. confirm traffic is on the expected revision
4. record the deploy metadata in the report

## Certification Matrix

Run these six scenarios against the fresh deployed revision:

1. single Google title-only
2. single Google description-only
3. batch Google title-only
4. batch Google description-only
5. hybrid Google title-only
6. hybrid Google description-only

## Required Runtime Checks

For each scenario, capture:

- response payload
- request ID
- job ID when applicable
- Cloud Run log evidence
- provider call count
- task summary

## Required Persistence Checks

- `generated_content`
- `regeneration_history`
- `variant_finish_sentences`
- `batch_generation_jobs`
- `batch_generation_job_skus`

## Required Dashboard Checks

- single proof SKU review page
- hybrid base SKU review page
- hybrid variant alias SKU review page
- confirm readback matches fresh persisted rows

## Rollback Rule

Rollback immediately if the deployed revision:

- widens generation scope,
- skips required finish generation,
- leaks unexpected placeholders,
- breaks route contracts,
- or diverges from the certified task model.
