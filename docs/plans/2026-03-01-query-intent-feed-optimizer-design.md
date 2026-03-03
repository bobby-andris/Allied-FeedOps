# Query-Intent Feed Optimizer V1 Design

## 1. Problem statement

Google Shopping / Performance Max and Bing Shopping performance depend heavily on whether feed titles and descriptions align with live high-intent query language. The current runtime already includes curated search-query evidence and deterministic keyword placement hints, but that signal reaches generation in a flattened form. We need a tighter, more auditable query-intent layer that improves paid-query relevance without changing task graphs, introducing hallucinated product claims, or weakening prompt lineage and runtime certification guarantees.

## 2. Business hypothesis

If Google and Bing generation receives a bounded, deterministic query-intent brief distilled from real search-query and keyword-performance data, then titles and descriptions will better match high-intent shopping demand, improving CTR and likely conversion rate for SKUs with meaningful query coverage. The fastest path to sales impact is to improve the existing paid-feed generation prompts rather than build a new workflow.

## 3. User/operator workflow

1. Operator runs the normal generation flow through the Python pipeline.
2. The generation bundle builds the existing evidence table once.
3. For eligible Google/Bing title and description tasks, runtime derives a `QueryIntentBrief` from live search-query inputs plus product evidence.
4. If the brief passes sufficiency checks, prompt assembly injects a small `<query_intent_brief>` section into the user prompt.
5. Provider-backed generation runs exactly as it does today for the same task kinds.
6. Existing persistence stores generated content and prompt lineage, now including the query-intent brief inside the `user_prompt` plus diagnostics in the feature-flag snapshot.
7. Operators review results through the existing dashboard history/readback surfaces and use stored prompt lineage to verify the brief’s effect.

## 4. Data inputs and source-of-truth tables

Runtime truth for this feature stays in Python and uses live Supabase-backed data only:

- `search_queries_by_master_sku`
- `search_queries` only for finish/noise filtering when needed, not for per-variant prompt expansion
- `keyword_metrics`
- `product_catalog`
- existing evidence from `build_evidence_table(...)`

Table and column names are validated against `docs/database/SCHEMA.md`.

Supporting runtime helpers reused where possible:

- `build_relevance_anchor_terms`
- `curate_search_queries_by_relevance`
- `build_keyword_placement_plan`
- `filter_evidence_for_copy_context`

## 5. Prompt assembly changes

The canonical Python system prompt remains unchanged.

We add one optional user-prompt section for Google and Bing title/description generation only:

```xml
<query_intent_brief>
...
</query_intent_brief>
```

Placement:

- after keyword enrichment hints
- before shopping intelligence / category guidance

Behavior:

- strictly additive dynamic evidence
- never authoritative over product facts
- bounded to a small number of emphasis cues
- explicit anti-stuffing and anti-raw-query instructions
- disabled automatically when data is insufficient

The brief will contain distilled demand-signal guidance such as:

- primary shopper intents
- title emphasis cues
- description emphasis cues
- excluded/noisy terms

It will not include raw query dumps or unsupported claims.

## 6. Runtime/task-graph impact

No task-graph shape changes are allowed.

Required invariants remain true:

- single title-only executes exactly `TITLE`
- single description-only executes exactly `DESCRIPTION_BASE` plus `FINISH_SENTENCES` when required
- batch remains orchestration only
- hybrid remains one shared base generation, one shared finish generation when required, and variant adaptation only
- no hidden per-variant provider-backed regeneration

The only runtime change is that eligible Google/Bing tasks receive an additional deterministic prompt section.

## 7. Persistence/lineage impact

No new tables or schema migrations are required for V1.

Prompt lineage remains complete by using existing `regeneration_history` fields:

- `system_prompt`
- `user_prompt`
- `prompt_hash`
- `feature_flags_active`
- `tokens_used`
- `latency_ms`

The query-intent feature will be auditable by:

- embedding the final brief into `user_prompt`
- adding `QUERY_INTENT_BRIEF_V1` to the runtime feature-flag snapshot
- storing structured query-intent diagnostics inside the existing `generation_diagnostics` payload embedded in `feature_flags_active`

Expected diagnostics:

- `query_intent_brief_enabled`
- `query_intent_data_sufficiency`
- `query_intent_primary_count`
- `query_intent_source_query_count`
- `query_intent_disabled_reason`

## 8. Dashboard/readback impact

No public route or dashboard runtime routing changes are planned.

V1 uses existing readback surfaces only:

- review/history components that already display `system_prompt` / `user_prompt`
- existing prompt-lineage API surfaces

Success criteria for dashboard/readback are proof-oriented:

- stored prompt lineage shows the `<query_intent_brief>` section when enabled
- feature-flag snapshot reflects `QUERY_INTENT_BRIEF_V1`
- no dashboard route bypasses `FEEDOPS_PIPELINE_URL`

If a UI affordance for query-intent diagnostics is desired later, it should be a follow-up and not part of V1.

## 9. Rollout plan

V1 rollout is intentionally narrow:

1. Implement behind `QUERY_INTENT_BRIEF_V1`.
2. Enable only for Google/Bing generation paths.
3. Let the brief self-disable when query data is weak.
4. Evaluate first on `samples/eval-skus-google-ads-90d.json`.
5. Use `samples/eval-skus.json` as broader regression coverage.
6. Certify locally, then on a deployed Cloud Run revision.
7. Capture prompt traces, request IDs, request lineage, and dashboard readback evidence before any GO decision.

This preserves a top-SKU-first release shape without adding a new runtime route or operator workflow.

## 10. Risks and mitigations

### Risk: keyword stuffing or awkward phrasing

Mitigations:

- bounded brief size
- explicit instructions that query-intent cues are optional support only
- retain current keyword-placement hygiene rules
- tests for raw-query leakage and unnatural list patterns

### Risk: query data creates unsupported product claims

Mitigations:

- brief may only emphasize evidence-backed attributes
- unsupported modifiers are excluded
- product facts remain sourced from catalog/evidence, not query rows

### Risk: hidden task/runtime expansion

Mitigations:

- no new provider-backed call
- compute brief once per generation bundle
- inject only into existing Google/Bing task prompts

### Risk: lineage ambiguity

Mitigations:

- final brief is stored inside `user_prompt`
- diagnostics land in existing feature-flag snapshot path
- prompt hash changes become auditable through existing lineage tooling

### Risk: low-signal SKUs dilute impact

Mitigations:

- strong sufficiency checks
- certification-first on the high-value 90-day paid set
- no forced enablement for weak-signal requests

## 11. Verification plan

Required before calling the feature complete:

1. Source review of request -> evidence -> query-intent brief -> prompt -> provider -> persistence -> dashboard path
2. Host tests
3. Local container smoke:
   - `ENV_FILE=.env.vercel PORT=18080 scripts/container_generation_smoke.sh`
4. Cloud Run deploy proof on the tested revision
5. Supabase prompt-lineage proof
6. Dashboard readback proof
7. Dated experiment report with GO / NO-GO recommendation

Evaluation rubric comparisons must cover:

- factual accuracy
- platform compliance
- keyword naturalness
- customer readability
- style consistency
- placeholder correctness
- query relevance
- likely paid-performance usefulness

## 12. Explicit “what will not change”

1. Public route contracts
2. Task kinds and task-graph invariants
3. Finish sentence generation shape
4. Shopify generation behavior
5. Dashboard prompt files as runtime authority
6. Dashboard runtime target authority (`FEEDOPS_PIPELINE_URL`)
7. Output schemas for Google/Bing/Shopify
8. Placeholder contracts
9. Provider/model selection
10. Database schema for V1
