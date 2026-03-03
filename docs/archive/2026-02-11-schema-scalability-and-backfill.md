# Schema Scalability, Historical Backfill & Performance Monitoring

**Date**: 2026-02-11
**Context**: Companion to `2026-02-11-signal-reality-and-sufficiency.md`
**Status**: Ready for GSD implementation

---

## GSD Prompt (paste into your GSD session)

Structure a new milestone with 5 phases for database scalability, Google Ads historical backfill, and long-term performance monitoring. Read `docs/plans/2026-02-11-schema-scalability-and-backfill.md` for full context and specifications. Here is the summary:

### Phase 1: Schema Fixes & Index Optimization (P0 — do first)

Fix critical schema issues that will cause problems at scale:

**1a. Fix performance_snapshots:**
- Convert `snapshot_date` from `text` to `date` type: `ALTER COLUMN snapshot_date TYPE date USING snapshot_date::date`
- Add unique constraint: `CREATE UNIQUE INDEX idx_perf_snapshots_unique ON performance_snapshots (master_sku, platform, snapshot_date)`
- Add FK to publish_events: `ADD CONSTRAINT fk_snapshots_publish_event FOREIGN KEY (publish_event_id) REFERENCES publish_events(id)`
- Add date-only index: `CREATE INDEX idx_snapshots_date ON performance_snapshots (snapshot_date DESC)`
- Add days_since_publish index: `CREATE INDEX idx_snapshots_days_since_publish ON performance_snapshots (days_since_publish)`

**1b. Fix search_queries index bloat (9 indexes on a bulk-insert table):**
- Audit index usage via `pg_stat_user_indexes` — candidates for removal: `idx_search_queries_ad_group_id`, `idx_search_queries_sync_job`, `idx_search_queries_finish`
- Add composite index: `CREATE INDEX idx_search_queries_sku_period_imp ON search_queries (master_sku, period_start, impressions DESC)`
- Add keyword_metrics TTL index: `CREATE INDEX idx_keyword_metrics_updated_at ON keyword_metrics (updated_at)`

**1c. Fix 197 NULL master_sku rows in search_queries** — investigate and fix or delete orphaned records.

**1d. Consider converting `search_queries_by_master_sku` from base table to materialized view** for automatic consistency with search_queries. Currently it's a regular table requiring manual sync — if sync code has bugs, data drifts silently.

Reference: The schema audit found current DB is 209 MB, Supabase Pro allows 8 GB. Current indexes are adequate for ~2K rows but 9 indexes on search_queries will cause write amplification at 1M+ rows.

### Phase 2: New Tables for Long-Term Monitoring

Create 3 new tables that enable pre-computed performance analytics:

**2a. `performance_rollups`** — Pre-computed weekly/monthly aggregate metrics per SKU with baseline deltas already calculated. Schema:
- `(master_sku, platform, rollup_period, period_start)` UNIQUE
- Avg impressions/clicks/CTR/conversions/ROAS
- Min/max for sparklines
- Pre-computed `baseline_ctr_delta`, `baseline_impressions_delta`, `baseline_roas_delta`
- `snapshot_count`, `publish_event_id`, `days_since_publish_start/end`

**2b. `search_query_rollups`** — Monthly search query aggregates per SKU. Schema:
- `(master_sku, platform, rollup_month)` UNIQUE
- Total unique queries, impressions, clicks, conversions
- `top_queries` JSONB array (top 20 by impressions)
- New/lost query counts, delta from previous month

**2c. `monitoring_alerts`** — Threshold-based alerts when metrics drop. Schema:
- `(master_sku, platform, alert_type, snapshot_date)` with severity levels
- `baseline_value`, `current_value`, `delta_percent`, `threshold_percent`
- Acknowledged/resolved state tracking

These tables eliminate app-side delta computation and enable fast dashboard queries. Storage estimate: ~237 MB Year 1, ~321 MB Year 3 (well within 8 GB limit).

### Phase 3: Google Ads Historical Backfill Script

Create `scripts/backfill_google_ads_data.py` — a standalone Python script (NOT a Cloud Run endpoint) that backfills historical data for all ~2,892 master SKUs.

**Key context**: Currently only 84 SKUs have search query data because only those have been through the generation pipeline. The Google Ads API has data for ALL products that have had Shopping ad impressions. The API retains search_term_view for 180 days and shopping_performance_view for ~2 years.

**Critical limitation to work around**: The current sync fetches the global top-1,000 search terms across ALL campaigns. This means high-impression products dominate and low-traffic SKUs never appear. The backfill must:
1. Increase LIMIT from 1,000 to 50,000
2. Process 6 x 30-day windows (covering the 180-day retention period)
3. Use `shopping_performance_view` for per-product performance data (it supports `segments.product_item_id` filtering, unlike search_term_view)
4. Track progress via `search_query_sync_jobs` with new columns: `backfill_type`, `date_window_start/end`, `batch_index`, `total_batches`, `last_processed_offset`, `parent_job_id`
5. Be resumable — if it fails at batch 40, resume from there

**Run locally** with `source .venv/bin/activate && set -a && source .env.vercel && set +a && python scripts/backfill_google_ads_data.py`.

**Three sub-phases:**
- Search terms: 6 date windows x LIMIT 50K, ~20-30 minutes total
- Performance data: Batch 72K variants in groups of 500, ~30-60 minutes
- Keyword Planner enrichment: All unique search terms in batches of 100, ~10-50 minutes

Estimated storage: 200-700 MB total for all backfilled data.

### Phase 4: Automated Collection via pg_cron

Enable `pg_cron` extension on Supabase and schedule:

1. **Weekly performance snapshots** (Mondays 6 AM UTC): Call `/api/performance/capture-snapshot` for all published SKUs
2. **Daily snapshots for recently published SKUs** (first 30 days post-publish): More frequent capture during the settling period
3. **Weekly rollup computation** (Mondays 8 AM UTC): `compute_weekly_rollups()` function aggregates raw snapshots into `performance_rollups`
4. **Monthly search query snapshot** (1st of month): Sync latest search terms and store in `search_query_snapshots`
5. **Monthly rollup + cleanup** (2nd of month): `compute_monthly_rollups()` + `cleanup_old_snapshots()`

Retention policy:
- Raw daily snapshots: 90 days
- Raw weekly snapshots: 2 years
- Weekly/monthly rollups: forever
- Search query snapshots (raw): 6 months
- Search query rollups: forever

Helper functions needed: `compute_weekly_rollups()`, `compute_monthly_rollups()`, `cleanup_old_snapshots()` — all as PL/pgSQL functions in Supabase.

### Phase 5: Functional Sub-Type Clustering + Cold-Start KP Wiring

This is from the signal audit findings — wire it AFTER the backfill is done so we have data to validate against.

**5a. Build FST extractor** (`src/feedops/pipeline/functional_subtype.py`):
- Extract functional product type from `current_title` by stripping collection name, size dimensions, accent details (dotted/grooved/twist)
- Produces ~60-80 FST clusters (e.g., "Double Glass Shelf with Towel Bar", "Corner Glass Shelf", "Recessed Toilet Paper Holder")
- Critical: Allied Brass products are highly unique within categories — "Glass Shelves" alone has 10 distinct functional sub-types with different search intents. Category-level generalization would be HARMFUL.

**5b. Wire `GenerateKeywordIdeas` for cold-start fallback** in `src/feedops/pipeline/evidence.py`:
- After `fetch_search_queries_for_master_sku()` returns empty (line ~288), call `KeywordPlannerClient.generate_keyword_ideas()` with FST-derived seed keywords
- Cache results in existing `keyword_metrics` table (30-day TTL)
- Format using same `format_search_queries_for_evidence()` function

**5c. Extend regression tests** in `tests/test_signal_wiring.py`:
- Test FST extraction produces correct clusters
- Test cold-start fallback fires when search queries are empty
- Test KP results are formatted correctly as evidence rows

### Constraints

- Python remains single source of truth for generation
- All schema changes via Supabase migrations in `supabase/migrations/`
- Backfill script runs locally, not on Cloud Run
- No partitioning yet (defer until tables exceed 5M rows, est. Year 3)
- Existing 18 regression tests in `tests/test_signal_wiring.py` must continue passing
- Gold standard examples (10 in prompt_templates) are already working — don't touch
- Don't redesign the evidence pipeline architecture — add the smallest seams necessary

### Key files

**Schema**: `docs/database/SCHEMA.md`
**Google Ads integration**: `src/feedops/integrations/google_ads_search_terms.py`, `google_ads_performance.py`
**Search insights API**: `src/feedops/api/search_insights.py`
**Evidence builder**: `src/feedops/pipeline/evidence.py`
**Snapshot capture**: `dashboard/src/app/api/performance/capture-snapshot/`
**Signal wiring tests**: `tests/test_signal_wiring.py`
**Signal audit**: `docs/plans/2026-02-11-signal-reality-and-sufficiency.md`

### Success criteria

1. All schema fixes applied (unique constraints, type conversions, index optimization)
2. Backfill script runs to completion and populates search_queries for 500+ master SKUs (whatever has Google Ads data)
3. pg_cron schedules active and producing weekly snapshots
4. Rollup tables populated after first week of collection
5. FST clustering produces ~60-80 clusters, cold-start KP fallback fires for SKUs without search data
6. `pytest tests/ -v` passes with 0 failures
