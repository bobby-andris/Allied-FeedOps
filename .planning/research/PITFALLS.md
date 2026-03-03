# Pitfalls Research

**Domain:** Dead code removal from decomposed Python pipeline + PostgreSQL schema migrations on live production data + entity relationship hardening for a multi-platform e-commerce content pipeline
**Researched:** 2026-03-03
**Confidence:** HIGH (all pitfalls grounded in actual codebase state from `/tmp/dead-code-research.md`, `/tmp/google-ads-import-research.md`, and direct source inspection)

---

## Critical Pitfalls

### Pitfall 1: Removing Dead Code That Tests Import via Backward-Compat Re-exports

**What goes wrong:**
A function appears dead (no runtime callers, grep shows zero production usage) but is still imported by tests through the backward-compat re-export chain. You remove it from `generator.py`, the function is gone, but tests import from `feedops.pipeline.generator` via the re-export block and fail with `ImportError`. The failure only surfaces in CI — local smoke tests pass because the developer only ran the module directly.

The specific instances in this codebase (confirmed from dead-code-research.md):
- `_platform_reasoning_effort()` in `generator.py` — imported by `tests/test_prompt_sanitization_contract.py` line 13
- `_platform_completion_cap()` in `generator.py` — imported by `tests/test_prompt_sanitization_contract.py` line 14
- `build_variant_prompt()` in `generator.py` — imported by `tests/test_pipeline.py`
- `_build_generation_user_prompt()` in `generation.py` — imported by `tests/api/test_generation.py` (3 functions)
- ~60 symbols in `main.py` re-export block (lines 174-304) — imported by 9 test files via `import feedops.api.main as api_main`

**Why it happens:**
The DECOMP-09 decomposition created a re-export shim: "remove code from location A, add re-export from A to B so old imports still work." Over time, some of the re-exported symbols became dead in production but tests never got updated to import from the canonical new location. The test import path and the runtime code path diverged silently.

**How to avoid:**
Never remove a function from its original location until you have:
1. Run `grep -r "function_name" tests/` and verified zero test imports
2. Updated any test imports to point at the canonical new module
3. Run the full test suite (`pytest tests/ -v`) and confirmed green
4. Removed the function from the source module

The correct sequence for each item is: update test → run pytest → remove dead code → run pytest again. Do not batch across multiple functions.

**Warning signs:**
- `grep` of production source shows zero callers but `grep tests/` shows imports
- The function is re-exported from `main.py` or from `generator.py` with a `# noqa: F401` comment
- CI fails with `ImportError` but local `python -m feedops.api.main` succeeds
- The re-export block in `main.py` lines 174-304 still references the symbol after removal

**Phase to address:** Phase: Dead code removal — process every item in the "Requires test updates first" table from dead-code-research.md before touching the corresponding source location.

---

### Pitfall 2: Adding a Unique Constraint to a Table With Existing Duplicate Rows

**What goes wrong:**
`ALTER TABLE performance_snapshots ADD CONSTRAINT uq_snapshots_sku_platform_env_date UNIQUE (master_sku, platform, environment, snapshot_date)` fails with `ERROR: could not create unique index — Key (master_sku, platform, environment, snapshot_date) is duplicated` if any existing rows violate the constraint. The table currently has 179 rows (from early inserts before the ON CONFLICT bug was introduced). If any two rows share the same `(master_sku, platform, environment, snapshot_date)` tuple, the migration fails mid-execution and the table is left in an inconsistent state.

This is especially dangerous because the migration file may have already executed DDL statements before the constraint fails — leaving the schema partially applied.

**Why it happens:**
Developers assume a nearly-empty table (179 rows) has no duplicates. But the ON CONFLICT bug that caused most inserts to fail also meant that when early inserts succeeded (before the bug was introduced or for unique date combinations), they may have inserted duplicate rows across retry attempts or re-runs of the snapshot collector.

**How to avoid:**
Before writing the migration, run the deduplication check:
```sql
SELECT master_sku, platform, environment, snapshot_date, COUNT(*) as cnt
FROM performance_snapshots
GROUP BY master_sku, platform, environment, snapshot_date
HAVING COUNT(*) > 1;
```
If any rows are returned, deduplicate first:
```sql
DELETE FROM performance_snapshots
WHERE id NOT IN (
    SELECT MIN(id)
    FROM performance_snapshots
    GROUP BY master_sku, platform, environment, snapshot_date
);
```
Only then add the constraint. Structure the migration file to run the dedup DELETE before the ALTER TABLE, so it is idempotent.

**Warning signs:**
- Migration fails with `ERROR: could not create unique index`
- Supabase migration history shows the migration as "failed" but the table structure is partially changed
- Running the migration a second time causes a different error than the first (schema already partially altered)

**Phase to address:** Phase: Schema migration for performance_snapshots — run dedup query against production before writing the migration file, not after.

---

### Pitfall 3: ON CONFLICT Upsert Silently Succeeds After Constraint Is Added But Updates Wrong Rows

**What goes wrong:**
The `performance_snapshots` upsert in `performance_impact.py:461` uses `on_conflict="master_sku,platform,environment,snapshot_date"`. After the unique constraint is added, the upsert stops failing — but it may UPDATE existing rows with stale data instead of inserting new rows. The Supabase client's `upsert()` with `on_conflict=` does a `INSERT ... ON CONFLICT DO UPDATE SET ...` which overwrites ALL columns on conflict, including `fetched_at`, `roas`, `impressions`, and critically `cohort_type`.

If the daily snapshot collector runs twice in the same day (e.g., manual trigger + scheduled trigger), the second run overwrites the first run's data for that `snapshot_date`. If the `cohort_type` assignment logic changed between runs (e.g., a new publish event was added), the row silently flips from "control" to "treated" or vice versa.

**Why it happens:**
After fixing the constraint bug, developers verify "the upsert no longer throws 42P10" and consider the fix complete. The semantic correctness of what happens on conflict is not tested — only that the operation no longer errors.

**How to avoid:**
After adding the constraint, verify upsert idempotency:
1. Insert a test snapshot row manually
2. Run the upsert again with the same `(master_sku, platform, environment, snapshot_date)` but different metric values
3. Confirm the row count stays the same (no duplicate inserted)
4. Confirm the metric values are updated (not silently ignored)
5. If you want insert-only semantics (don't update existing snapshots), use `on_conflict="...", ignore_duplicates=True` — but this means re-runs are completely idempotent (existing data wins)

The safer default for time-series snapshot data is `ignore_duplicates=True`: the first write for a given `(sku, platform, env, date)` wins. Re-runs don't corrupt historical data.

**Warning signs:**
- Row count in `performance_snapshots` grows slower than expected after the fix
- `cohort_type` values in `performance_snapshots` differ from what's expected based on `publish_events`
- `performance_impact_scores` shows wildly different pre/post windows than the publish date

**Phase to address:** Phase: Schema migration for performance_snapshots — test upsert semantics with real data immediately after constraint is added.

---

### Pitfall 4: Offer ID Case Mismatch Corrupts Entity Relationships During Bulk Data Operations

**What goes wrong:**
`variant_index` stores offer IDs in lowercase (`shopify_us_{product_id}_{variant_id}`). Google Ads API returns them in uppercase (`shopify_US_{product_id}_{variant_id}`). The search terms code normalizes case before lookup/save (confirmed working). The performance code relies on `variant_index.gmc_offer_id` directly (also lowercase, matching Google Ads API output when query goes through `variant_index` first). But when building a bulk offer ID set for a new data operation — such as "fetch baselines for all 2,500 master SKUs" — it is easy to mix sources: some IDs come from `variant_index` (lowercase), some from Google Ads API responses (uppercase), and some from Google Sheets (mixed or uppercase). Joins fail silently: the offer ID exists in both places but the case mismatch means the lookup returns zero rows instead of an error.

The concrete failure mode: `fetch_batch_product_performance()` receives a mix of cases in its `offer_ids` list, queries Google Ads with those IDs, and Google Ads returns data keyed by the format it received. When results are written back and matched to `variant_index` by `gmc_offer_id`, uppercase IDs don't match lowercase rows — those SKUs appear to have zero impressions, which triggers incorrect "no data" branching.

**Why it happens:**
Each integration layer handles case independently. The search terms integration normalizes deliberately. The performance integration trusts `variant_index` values. New code that assembles offer IDs from multiple sources (e.g., a bulk backfill script) is unlikely to normalize consistently unless there's a shared utility function enforcing the invariant.

**How to avoid:**
Create a single normalization utility used by ALL offer ID assembly points:
```python
def normalize_offer_id(offer_id: str) -> str:
    """Canonical DB format: lowercase shopify_us_..."""
    return offer_id.replace("shopify_US_", "shopify_us_")
```
Apply this at the boundary where offer IDs enter any data pipeline function. Never allow uppercase offer IDs to enter the DB or to be used in DB lookups. The Google Ads query itself uses `product_item_id` which Google returns in its own casing — normalize immediately after receiving the API response, before any join to `variant_index`.

**Warning signs:**
- A master SKU has `variant_index` rows but shows zero impressions in performance queries
- `performance_baselines` has zero rows for SKUs that definitely have Google Ads traffic
- A join between a Google Ads result set and `variant_index` returns fewer rows than expected
- Any code that assembles offer IDs from two different sources without a normalization step

**Phase to address:** Phase: Entity relationship design and bulk data collection — add normalization utility before writing any bulk fetch code.

---

### Pitfall 5: Bulk Baseline Fetch for All 2,500 SKUs Triggers Google Ads Rate Limiting

**What goes wrong:**
`fetch_batch_product_performance()` chunks offer IDs into batches of 25 and runs up to 5 parallel threads. For 2,500 master SKUs × ~29 offer IDs per SKU (72K rows / 2,500 SKUs) = ~72,000 offer IDs total. At 25 per GAQL query with 5 threads, this is ~2,880 parallel API requests in rapid succession. Google Ads API enforces per-customer-ID rate limits. The current limit for the Reporting API is 15,000 requests per day per customer. A single bulk baseline fetch for all SKUs would consume ~2,880 requests — 19% of the daily quota in one shot — and if retried (due to errors), can exhaust the quota entirely.

Additionally, Google Ads API returns `QUOTA_ERROR` (not an HTTP 429) with an error code of `RESOURCE_EXHAUSTED`. The current retry logic in `google_ads_performance.py` may not handle this specific error type, causing the bulk operation to fail silently with incomplete data.

**Why it happens:**
The `fetch_batch_product_performance()` function was designed for on-demand single-SKU and small-batch operations (the current use case is ~274 baselines). Scaling it to 2,500 SKUs is a 9x increase in request volume that nobody has stress-tested.

**How to avoid:**
- Do NOT run the bulk baseline fetch as a single operation. Spread it across multiple days or run at a low-traffic time with throttling between chunks.
- Add an inter-batch delay (e.g., 200ms between chunks) when fetching baselines for more than 100 master SKUs.
- Implement `RESOURCE_EXHAUSTED` / `QUOTA_ERROR` detection in `fetch_batch_product_performance()` with exponential backoff (minimum 60s) and a max-retry limit.
- Track completion in the database (`baseline_fetch_jobs` table or use the existing backfill job tracking) so that a failed bulk fetch can resume from the last successful SKU rather than restarting from the beginning.
- Cap concurrent threads at 3 (not 5) for bulk operations to reduce burst pressure.

**Warning signs:**
- `googleads.errors.GoogleAdsException` with `error.code = RESOURCE_EXHAUSTED`
- Performance baselines filling in for the first few hundred SKUs then stopping
- Google Ads API response latency increasing steadily during the bulk fetch
- Daily quota consumed before noon (visible in Google Ads API Center)

**Phase to address:** Phase: Bulk data collection scale-out — implement throttling and quota monitoring before running the first bulk fetch.

---

### Pitfall 6: Cloud Scheduler Jobs Fail Silently With No Retry

**What goes wrong:**
The three Cloud Scheduler jobs (daily incremental backfill at 2:15 AM ET, daily snapshot capture at 2:45 AM ET, daily funnel snapshot at 6 AM UTC) all send HTTP POST requests to Cloud Run or Vercel endpoints. If the endpoint returns a non-2xx status (e.g., the `performance_snapshots` upsert throws 42P10 and the handler returns 500), Cloud Scheduler marks the job as failed and — depending on its retry configuration — either retries with exponential backoff or gives up silently.

The current snapshot collector (`collect_daily_performance_snapshots`) catches exceptions inside the loop and continues processing other dates. But the final HTTP response is 200 OK regardless — meaning Cloud Scheduler NEVER knows the job failed. The Slack alert is the only failure signal, and it only fires if the Slack webhook URL is configured and the exception surfaces to the top-level handler.

After the schema fix (adding the unique constraint), the upsert will succeed — but if `SLACK_WEBHOOK_URL` is not bound to the Cloud Run revision, Slack alerts are silently swallowed. The operator has no visibility into whether the daily job actually ran.

**Why it happens:**
The common pattern in Python APIs is to catch all exceptions inside a background worker and return 200 so the HTTP request layer doesn't retry (which would cause duplicate processing). But this means monitoring depends entirely on explicit alerting code paths working correctly. If the alert mechanism fails, failures are invisible.

**How to avoid:**
- After fixing the `performance_snapshots` constraint, explicitly verify the Slack webhook is bound to the Cloud Run service: `gcloud run services describe feedops-pipeline --project=bobbys-project-346400 --format='value(spec.template.spec.containers[0].env)'` and confirm `SLACK_WEBHOOK_URL` is present.
- Add an observability check to the health endpoint: `GET /health` should return the last successful run time and row count for each scheduled job. If the last run was >26 hours ago, `/health` should flag it.
- After the schema fix is deployed, manually trigger `POST /performance/capture-snapshot` and verify the Slack message arrives within 5 minutes.
- Consider whether Cloud Scheduler retry policy should be set to retry on 5xx (currently: if the endpoint returns 200 on exception, retries are never triggered — which is intentional to avoid duplicate processing, but means monitoring depends entirely on Slack).

**Warning signs:**
- `SLACK_WEBHOOK_URL` missing from `gcloud run services describe` output
- `performance_snapshots` row count unchanged after 48 hours despite the schema fix being deployed
- `performance_impact_scores` still has 0 rows 72 hours after the constraint fix
- Cloud Scheduler job history shows "success" but Slack received no notification

**Phase to address:** Phase: Schema migration for performance_snapshots — verify Slack webhook is bound before declaring the fix complete.

---

### Pitfall 7: Removing the Legacy `generate_candidates` Path Breaks the optimize.py CLI

**What goes wrong:**
`optimize.py` (the CLI pipeline) calls `generate_candidates()` from `generator.py`, which calls `build_split_prompt()`, which calls `build_prompt()`. This entire chain — approximately 450 lines in `generator.py` — looks dead because the modern API path uses `generate_per_platform()` → `executor.execute_generation_legacy_payload()`. Removing it to "clean up" dead code breaks the CLI pipeline, which may still be the mechanism for local development and bulk optimization runs outside the API.

From dead-code-research.md: "build_prompt() — Used by optimize.py (line 318)" and "generate_candidate()/generate_candidates() — Used by optimize.py (line 149)." These are explicitly marked as NOT safe to remove.

**Why it happens:**
The dead code audit correctly identifies these functions as "legacy" and developers interpret "legacy = remove." But legacy in this codebase means "superseded by the modern API path" — not "unused by any caller." The CLI may be the primary tool for the user's local development workflow.

**How to avoid:**
Before removing any function that `optimize.py` depends on:
1. Confirm with the team whether `optimize.py` is still actively used (check git log for recent changes to the file)
2. If `optimize.py` is still needed, keep the legacy path intact OR migrate `optimize.py` to call the API endpoints instead
3. Only remove the legacy path after `optimize.py` has been migrated or explicitly retired

The safe cleanup order from dead-code-research.md is: trivially dead items first (no dependencies), then test-blocked items (update tests first), then architectural decisions (evaluate optimize.py dependency before touching the legacy generation chain).

**Warning signs:**
- `git log src/feedops/pipeline/optimize.py` shows recent commits (file is still maintained)
- Any developer workflow documentation that mentions `python -m feedops.pipeline.optimize`
- Tests in `test_pipeline.py` that import `generate_candidates` — if the test exists, the function is likely still valued

**Phase to address:** Phase: Dead code removal — make the optimize.py dependency decision explicit in the phase plan before any cleanup begins.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Run dedup + constraint migration as two separate Supabase migrations | Separates concerns, easier to debug | If dedup succeeds but constraint migration fails, the table has no duplicates but also no constraint — state is inconsistent until migration is retried | Never — dedup DELETE and ALTER TABLE must be in the same migration file |
| Remove re-export from `main.py` without updating test imports | Cleaner `main.py` immediately | `ImportError` in CI; production deploy fails if tests gate the deploy | Never — update test imports first, in the same PR |
| Normalize offer IDs at query time with LOWER() in SQL instead of a Python utility | Works immediately without code changes | Every future query must remember to normalize; one forgotten LOWER() causes silent data loss | Only as a temporary emergency measure; add TODO to migrate to Python normalization |
| Increase bulk fetch thread count to 10 to finish faster | Faster bulk baseline population | Google Ads quota exhausted in one run; subsequent 24 hours have no API access | Never for bulk operations — keep at 3 concurrent threads |
| Add `ignore_duplicates=True` to all upserts to avoid conflict errors | No 42P10 errors | Silent data loss — if a duplicate row exists with different data, the new data is silently ignored | Only acceptable for idempotent re-runs of historical data; never for primary data collection |
| Skip the Slack webhook verification step after constraint fix | Faster deployment | Daily job can fail silently for weeks; no visibility into snapshot collection health | Never — Slack verification takes 2 minutes and prevents silent data loss |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Google Ads API | Assuming `QUOTA_ERROR` is returned as HTTP 429 | Google Ads returns quota errors as `GoogleAdsException` with `error.code = RESOURCE_EXHAUSTED` — must catch this specific exception type, not just HTTP status codes |
| Google Ads API | Mixing uppercase/lowercase offer IDs in a GAQL `WHERE product_item_id IN (...)` clause | Google Ads API is case-sensitive for `product_item_id` — always normalize to the format the API uses (uppercase `shopify_US_`), then normalize back to DB format (lowercase) on the way in |
| Supabase upsert | Using `on_conflict=` without a matching unique constraint | PostgreSQL raises error 42P10 silently caught by the Python client; verify constraint exists before relying on upsert semantics |
| Cloud Scheduler | Assuming a 200 HTTP response means the job succeeded | The snapshot collector returns 200 even on internal failures — monitor via Slack alert presence, not scheduler status |
| Cloud Run | Assuming a new env var binding takes effect immediately | After adding a secret binding or env var, Cloud Run creates a NEW revision — traffic may still route to the old revision. Always verify with `gcloud run revisions list` after changes |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching all 72K `variant_index` rows into memory for offer ID lookup | Works for search term sync (current use case) — `_preload_variant_cache()` loads all rows once per job | For bulk baseline fetch running in parallel threads, each thread loading 72K rows creates memory pressure on the 2GB Cloud Run container | At >3 parallel threads doing bulk data operations simultaneously |
| Daily snapshot query building offer_id sets from ALL of `variant_index` | Works currently at 179 snapshot rows (mostly failing) | Once snapshots start succeeding for all ~2,500 treated + 500 control SKUs, the daily snapshot API call processes ~87,500 offer IDs — 3× the current search term scale | At >500 actively tracked SKUs |
| Performance impact score computation in-memory diff-in-diff | Fine for 0 rows (current state) | Once snapshots exist for 2,500 SKUs × 90-day window × 3 refresh dates = ~675K rows, loading all snapshots into memory for diff-in-diff computation will OOM | At >50K snapshot rows loaded simultaneously |
| `pytest tests/ -v` running all tests without module isolation | Fine at current test count | After dead code cleanup modifies import paths in 5+ test files, tests that pass individually may fail together due to import order side effects | After any batch import path refactor |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing a Google Ads performance baseline dump to git (for debugging a bulk fetch issue) | Google Ads impression/click/cost data is commercially sensitive — competitor analysis if leaked | Never write raw API responses to files in the repo; use `/tmp/` only; confirm `.gitignore` covers `*.json` debug dumps |
| Logging full GAQL queries with inline offer ID lists (72K IDs) | Logs become unmanageable; Cloud Run log size limits cause log loss | Log the count and a sample (first 3 IDs), not the full list |
| Hardcoding the Google Ads customer ID (`6253381786`) in bulk fetch scripts | If the script is shared or the customer ID changes, all historical data becomes unattributable | Always read customer ID from env var `GOOGLE_ADS_CUSTOMER_ID`; never hardcode |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Dead code removed:** After each removal, run `pytest tests/ -v` — not just `python -c "import feedops.api.main"`. Import errors and test failures are separate failure modes.
- [ ] **`performance_snapshots` constraint added:** Verify with `SELECT constraint_name FROM information_schema.table_constraints WHERE table_name = 'performance_snapshots' AND constraint_type = 'UNIQUE'` — the constraint name `uq_snapshots_sku_platform_env_date` should appear.
- [ ] **Daily snapshot actually running:** After constraint fix + deployment, manually trigger `POST /performance/capture-snapshot` and check: (a) row count in `performance_snapshots` increases, (b) Slack notification arrives, (c) `performance_impact_scores` gains rows within 5 minutes.
- [ ] **Offer ID normalization applied everywhere:** Run `grep -r "shopify_US_\|shopify_us_" src/feedops/` and verify every occurrence either (a) normalizes immediately after use or (b) is the normalization utility itself.
- [ ] **Image wiring in executor.py:** After the 15-line wiring fix, run `/optimize-sku` for a SKU with a known product image URL and verify the generated Google title/description shows image-informed content (not just text-only generation).
- [ ] **Bulk baseline fetch tested with throttling:** Before running against all 2,500 SKUs, test against a 50-SKU sample with the throttling delay in place and confirm no `RESOURCE_EXHAUSTED` errors.
- [ ] **Backward-compat re-exports removed from main.py:** Verify by running `grep -c "noqa: F401" src/feedops/api/main.py` — should be 0 after cleanup (or only legitimate ones remain).

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Dead code removal breaks test imports | LOW | `git revert` the removal commit; update test imports to canonical locations first; re-remove in new PR |
| Migration fails with duplicate constraint violation | LOW | The migration fails before applying the constraint — no schema change occurred. Run the dedup query manually in Supabase SQL editor, then re-run the migration |
| Migration partially applied (dedup ran, ALTER failed) | MEDIUM | Run `SELECT constraint_name FROM information_schema.table_constraints WHERE table_name = 'performance_snapshots'` to confirm constraint is missing; then run only the ALTER TABLE statement manually |
| Bulk baseline fetch exhausts Google Ads quota | HIGH | Wait 24 hours for quota reset; run with 3-thread cap and 500ms inter-batch delay on retry; split across 2-3 days if needed; check quota consumption at [Google Ads API Center](https://ads.google.com/aw/apicenter) |
| Offer ID case mismatch corrupts baseline data | MEDIUM | Run `DELETE FROM performance_baselines WHERE impressions = 0 AND clicks = 0` to remove zero-data rows caused by failed lookups; add normalization utility; re-run baseline fetch |
| Snapshot collector runs successfully but impact scores stay at 0 | LOW | Run `SELECT COUNT(*) FROM performance_snapshots WHERE published_event_id IS NOT NULL` — if 0, no treated SKUs exist yet (publish_events table is empty for recent publishes); impact scoring requires at least one publish event with post-publish snapshot data |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Dead code removal breaks test imports | Dead code cleanup — update test imports before removing source | `pytest tests/ -v` green after each removal |
| Duplicate rows block constraint migration | Schema migration — run dedup query before writing migration file | Zero rows from `GROUP BY ... HAVING COUNT(*) > 1` |
| Upsert overwrites historical snapshots | Schema migration — choose `ignore_duplicates=True` semantics explicitly | Second upsert of same snapshot returns same row (no change) |
| Offer ID case mismatch in bulk fetch | Entity relationship design — add normalization utility as first step | `grep` of all offer ID assembly points shows normalization applied |
| Google Ads quota exhaustion during bulk fetch | Bulk data collection scale-out — add throttling before scale-out | 50-SKU test run completes with no `RESOURCE_EXHAUSTED` errors |
| Cloud Scheduler fails silently after fix | Schema migration deployment — verify Slack webhook binding | Manual trigger of snapshot capture produces Slack message within 5 minutes |
| Removing optimize.py's legacy generation dependency | Dead code cleanup — explicit decision on optimize.py status before cleanup | `python -m feedops.pipeline.optimize --help` still works after cleanup (or is intentionally retired) |
| Bulk in-memory data operations OOM at scale | Bulk data collection scale-out — implement pagination/streaming before full scale | Memory usage stays <1.5GB during 500-SKU test batch |

---

## Sources

- Codebase audit: `/tmp/dead-code-research.md` (2026-03-03) — direct source inspection of all dead code locations and test import dependencies (HIGH confidence)
- Codebase audit: `/tmp/google-ads-import-research.md` (2026-03-03) — live DB row counts, constraint analysis, scheduler job details, ON CONFLICT bug root cause (HIGH confidence)
- Source: `src/feedops/monitoring/performance_impact.py:461` — confirmed upsert with missing constraint
- Source: `src/feedops/integrations/google_ads_performance.py` — confirmed 25-per-chunk, 5-thread architecture
- Source: `tests/test_prompt_sanitization_contract.py:11-14` — confirmed test imports of generator.py dead code
- Source: `src/feedops/api/main.py:174-304` — confirmed re-export block scope and test file count (9 test files)
- Official: [Google Ads API rate limits and quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas) — 15,000 requests/day per customer limit (MEDIUM confidence — limit details may vary by API version)
- Official: [PostgreSQL ON CONFLICT documentation](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT) — confirms constraint requirement for `ON CONFLICT (columns)` syntax (HIGH confidence)
- Project history: `CLAUDE.md` — offer ID case mismatch pattern documented as critical known issue (HIGH confidence)
- Project history: `memory/MEMORY.md` — Phase 27 prompt sensitivity learnings preserved (HIGH confidence)

---
*Pitfalls research for: Dead code cleanup + data infrastructure hardening (v1.1)*
*Researched: 2026-03-03*
