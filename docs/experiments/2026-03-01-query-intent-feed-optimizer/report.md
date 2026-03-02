# 2026-03-01 Query-Intent Feed Optimizer V1

> Superseded by certification recovery report: `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/report.md`

## Summary

Implemented a narrow V1 query-intent briefing layer for Google and Bing generation in the Python runtime. The feature adds a deterministic, non-provider-backed `<query_intent_brief>` prompt section for eligible title and description tasks, gates it behind `QUERY_INTENT_BRIEF_V1`, and persists diagnostics through existing lineage metadata.

The implementation preserves the current task model:

- `TITLE` remains `TITLE`
- `DESCRIPTION_BASE` remains `DESCRIPTION_BASE`
- `FINISH_SENTENCES` remains unchanged
- no public route contract changes
- no new provider-backed subcalls
- no dashboard routing changes

## Source Intent

Design and implementation artifacts:

- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/plans/2026-03-01-query-intent-feed-optimizer-design.md`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/plans/2026-03-01-query-intent-feed-optimizer-implementation-plan.md`

Runtime code changes:

- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/query_intent_brief.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/feature_flags.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/prompt_builder.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/generation/tasks.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/generation/executor.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/main.py`

New tests:

- `/Users/bobby/Documents/GitHub/Allied-FeedOps/tests/test_query_intent_brief.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/tests/test_query_intent_prompt_builder.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/tests/test_query_intent_executor_integration.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/tests/test_query_intent_lineage.py`

## Implemented Behavior

### Query-intent derivation

- pulls master-SKU search queries via existing runtime search query fetch logic
- reuses `build_relevance_anchor_terms(...)` and `curate_search_queries_by_relevance(...)`
- applies additional deterministic exclusions for:
  - competitor-branded phrases
  - noisy/navigational phrases
  - finish-specific phrases
  - material mismatches
  - unsupported functional claims
- builds bounded emphasis lists:
  - up to 3 `primary_intents`
  - up to 3 `title_emphasis`
  - up to 3 `description_emphasis`
  - up to 5 `excluded_terms`
- self-disables unless curated, evidence-safe search data is strong enough

### Prompt assembly

- adds optional `<query_intent_brief>` only for Google/Bing `title` and `description`
- does not inject into Shopify prompts
- does not inject into finish sentence generation
- does not change the canonical system prompt

### Lineage and diagnostics

- surfaces `query_intent_diagnostics` in the legacy generation payload
- merges query-intent diagnostics into persisted `generation_diagnostics`
- relies on existing `feature_flags_active.generation_diagnostics` lineage storage

## Verification Executed

### Focused query-intent tests

Command:

```bash
.venv/bin/pytest tests/test_query_intent_brief.py tests/test_query_intent_prompt_builder.py tests/test_query_intent_executor_integration.py tests/test_query_intent_lineage.py -q
```

Result:

- `13 passed in 1.45s`

### Broader host regression suite

Command:

```bash
.venv/bin/pytest tests/test_generation_runtime_scope_contract.py tests/test_hybrid_generation_parity.py tests/api/test_hybrid_generation_telemetry_contract.py tests/test_cloud_run_parity.py tests/test_runtime_env_contract.py tests/test_env_parity.py tests/test_prompt_sanitization_contract.py tests/test_keyword_placement.py tests/test_search_query_hygiene.py tests/test_query_intent_brief.py tests/test_query_intent_prompt_builder.py tests/test_query_intent_executor_integration.py tests/test_query_intent_lineage.py -q
```

Result:

- `78 passed`
- `1 failed`

Failing test:

- `/Users/bobby/Documents/GitHub/Allied-FeedOps/tests/test_prompt_sanitization_contract.py`
- `test_generator_v2_imports_only_platform_specific_builders`

Observed blocker:

- the test asserts that `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/generator.py` contains `build_google_prompt`, `build_bing_prompt`, and `build_shopify_prompt`
- `origin/master` reproduces the same mismatch, indicating this is a baseline contract failure unrelated to the query-intent changes

## Release Gate Status

### Source review

- complete for the implemented code path

### Host tests

- partial pass
- focused query-intent coverage passed
- broader host suite blocked by one pre-existing contract failure

### Local container smoke

- not run

Required command still pending:

```bash
ENV_FILE=.env.vercel PORT=18080 scripts/container_generation_smoke.sh
```

### Cloud Run deploy proof

- not run

### Supabase lineage proof

- not run against deployed runtime

### Dashboard readback proof

- not run against deployed runtime

## Certification Metadata

- Commit SHA: `37a0c0b5658ce06a5169f42f3d8293a8e78e98b0`
- Feature branch: `codex/query-intent-feed-optimizer-20260301`
- Cloud Run revision: not collected
- Request IDs: not collected
- Job IDs: not collected
- Image ref: not collected

## GO / NO-GO

## NO-GO

Reason:

- broader host verification is not fully green because of a baseline contract failure that still blocks the required host-test gate
- local container smoke has not been executed
- Cloud Run / Supabase / dashboard certification evidence has not been collected

## Recommended Next Steps

1. Resolve or explicitly quarantine the baseline `generator.py` contract failure in `/Users/bobby/Documents/GitHub/Allied-FeedOps/tests/test_prompt_sanitization_contract.py`.
2. Run the required local container smoke command and review artifacts.
3. Deploy the tested revision, capture the Cloud Run revision, and run an end-to-end certified scenario that proves prompt lineage and dashboard readback.
