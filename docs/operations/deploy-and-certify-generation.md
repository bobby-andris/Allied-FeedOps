# Deploy And Certify Generation

## Purpose
This is the production playbook for generation-affecting changes.

## Two Deploy Paths

### A. Pre-PR exact-branch certification

Use this path when you need to certify the exact current feature branch SHA before opening or merging a PR.

1. from the feature branch, deploy a tagged no-traffic revision:
   - `scripts/deploy_tagged_revision.sh <revision-tag>`
2. use the tagged revision URL for the six-scenario runtime proof
3. record:
   - tested commit SHA
   - image ref
   - Cloud Run service URL
   - Cloud Run revision
   - revision tag

This path is for exact-branch certification only. It does not exercise the GitHub-connected production Cloud Build trigger.

### B. Post-merge production deploy

Use this path after the branch is merged into `origin/master`.

1. merge the feature branch into `master`
2. let the normal GitHub-connected Cloud Build path run `cloudbuild.yaml`
3. confirm traffic is on the expected revision
4. record:
   - tested commit SHA
   - Cloud Build ID
   - image ref
   - Cloud Run service URL
   - Cloud Run revision

## Deploy Inputs To Capture

- tested commit SHA
- image ref
- Cloud Run service URL
- Cloud Run revision
- deploy mode:
  - `pre-pr-tagged-branch-certification`
  - `post-merge-origin-master-production`
- Cloud Build ID when the production-trigger path was used

Hard rule:

Do not claim production readiness from pre-PR exact-branch certification alone. Production readiness requires the post-merge `origin/master` production trigger path to be healthy too.

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
