# As-Is Trace Matrix

## Baseline Context
- Repository: `/Users/bobby/Documents/GitHub/Allied-FeedOps`
- Branch: `codex/e245-asis-trace-and-architecture-audit-20260227`
- Commit: `d2aea9335c720c9c445df6133ac57544ee2b743a`
- Case A: `CL-55` (Google title + Google description)
- Case B: `1033` family (hybrid/multi-size, with explicit `1033/18` evidence)

## Branch/Path Coverage Matrix

| Path | Case A | Case B | Evidence | Code anchors |
|---|---|---|---|---|
| Dashboard entry -> Next API regenerate route | Covered | Covered | Request forwarding contract observed in route + async payload handling | `dashboard/src/app/api/regenerate/route.ts:115`, `:202`, `:215`, `:244`, `:264` |
| UI regenerate submit + polling loop | Covered | Covered | `async_mode: true`, poll to `/api/regenerate/status/{job_id}`, dedupe handling | `dashboard/src/components/review/RegenerateButton.tsx:89`, `:95`, `:134`, `:148`, `:153` |
| Python `/regenerate` async dedupe create/return | Covered | Not primary in case run | Async contract and dedupe path present and line-traced; async job row evidence in DB | `src/feedops/api/main.py:1644`, `:1670`, `:1676`, `:1687`, `:1719` |
| Python `/regenerate` sync execute | Covered | Not primary in case run | Sync execution path line-traced; CL-55 rows persisted in `regeneration_history` and `generated_content` | `src/feedops/api/main.py:1335`, `:1606`, `:1710` |
| Python `/hybrid-generate` job creation | Not primary | Covered | Batch job `0c52acdc-ac07-4437-8731-40432ec47a1a` and SKU rows extracted | `src/feedops/api/main.py:1941`, `:2002`, `:2031` |
| Hybrid background worker (`process_hybrid_batch_job`) | Not primary | Covered | Family + single processing and progress update lines traced | `src/feedops/api/main.py:2205`, `:2271`, `:2305`, `:2433` |
| Single-SKU generator (`generate_per_platform`) | Covered | Covered | Prompt assembly, prompt hashes, usage/latency/parse maps, finish payload extraction | `src/feedops/pipeline/generator.py:377`, `:446`, `:462`, `:477`, `:534`, `:555` |
| Prompt source authority (`prompt_loader`) | Covered | Covered | Canonical code-owned system prompt and system prompt hash functions traced | `src/feedops/api/prompt_loader.py:20`, `:143`, `:166`, `:218` |
| Prompt builder (google + finish placeholders) | Covered | Covered | Placeholder contract and per-platform prompt builders traced | `src/feedops/api/prompt_builder.py:278`, `:317`, `:363`, `:396`, `:491` |
| Provider retry/timeout/parse-repair loop | Covered | Covered | Required-key parse validation + retry budget + parse modes line-traced | `src/feedops/providers/openai_provider.py:25`, `:98`, `:170`, `:300`, `:441`, `:539` |
| Provider env parity controls | Covered | Covered | Timeout/retry/max-total env knobs confirmed in factory | `src/feedops/providers/factory.py:45`, `:46`, `:47`, `:48` |
| Finish sentence persistence (`variant_finish_sentences`) | Covered | Covered | `CL-55/google` and `1033/18/google` rows each have 28 keys | Supabase SQL evidence; write paths: `src/feedops/api/main.py:1534`, `src/feedops/api/hybrid_generation.py:411` |
| Variant expansion at publish-time | Covered | Covered | Exactly-one `{FINISH_SENTENCE}` enforcement + 28-finish completeness checks traced | `dashboard/src/lib/publishing/expand-variants.ts:216`, `:229`, `:372`, `:419` |
| Dashboard review read path (`generated_content` + variant tables) | Covered | Covered | Review page queries + baseline extraction + finish sentence fetches traced | `dashboard/src/app/(dashboard)/review/[sku]/page.tsx:114`, `:195`, `:296`, `:309` |
| Regeneration history prompt lineage fields | Covered | Covered (partial telemetry) | Prompt hash + prompt text + request_id present for traced records | Supabase SQL evidence (IDs listed in report section 4) |
| Telemetry fields (`tokens_used`, `cost_usd`, `latency_ms`) | Covered (CL-55) | Partially covered (`latency_ms` yes, tokens/cost null for 1033/18 row) | SQL evidence extracted for all traced IDs | `src/feedops/api/main.py:1513`, `:1570` and SQL |
| Batch lineage (`batch_generation_jobs`, `batch_generation_job_skus`) | N/A | Covered | Job + SKU rows extracted, status and counts present | `src/feedops/api/main.py:2002`, `:2100`, `:2200` |

## Explicit Branch Coverage Checklist

| Branch | Status | Evidence |
|---|---|---|
| Google title generation | Covered | CL-55 row `ec9ecd1e-c1e9-4874-9b88-bec221eabbbf`; generated content `8300a24f-d4c0-439b-87d1-94768f069bbe` |
| Google description generation | Covered | CL-55 row `365a2417-186f-43dc-badb-a0c4cd331642`; generated content `8d276b39-84ff-4fe8-a0d3-3b3f972411c0` |
| Finish sub-generation branch | Covered | `finish` prompt branch in generator + 28-key finish sentence maps for both traced SKUs |
| Async job path | Covered | `generation_jobs` record `c3e89bb8-9550-4704-90d2-2de26ffcb41a` and status endpoint mapping |
| Sync path | Covered | `_execute_regeneration_request` trace and CL-55 persistence rows |
| Hybrid multi-size path | Covered | `/hybrid-generate` + `process_hybrid_batch_job` + batch tables for job `0c52acdc-ac07-4437-8731-40432ec47a1a` |
| Persistence write points | Covered | `_persist_generated_content_and_history`, `variant_finish_sentences` upserts, batch job updates |
| Dashboard read points | Covered | Review page + governance/funnel/intelligence page API hooks traced |

## Open Trace Gaps (As-Is)

| Gap | Impact | Action |
|---|---|---|
| `regeneration_history` has no explicit `state/idempotent/version` columns | Medium lineage expressiveness gap | Preserve current behavior in docs; consider additive columns or jsonb fields in recommendations |
| Hybrid rows may have null `tokens_used`/`cost_usd` in `regeneration_history` | High for spend attribution | Highlight in recommendations for strict telemetry capture in hybrid path |
| `batch_generation_job_skus` for the selected hybrid job returned empty in captured evidence artifact | Medium forensic gap | Re-extract live rows for this job during next controlled hybrid run |
