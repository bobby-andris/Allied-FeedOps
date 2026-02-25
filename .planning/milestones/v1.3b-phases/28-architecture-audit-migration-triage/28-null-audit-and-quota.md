# Phase 28: NULL Rate Audit & API Quota Analysis

**Audited:** 2026-02-25
**Data source:** Production Supabase (project `qezuszwufortkiutlhym`)
**Scope:** All foreign keys in the publish-performance join chain + Google Ads API quota sustainability

---

## Part 1: NULL Rate Audit

### 1.1 publish_events Column Completeness

**Total rows:** 73 | **Success events:** 69

| Column | Non-NULL | NULL | % Populated | Assessment |
|--------|----------|------|-------------|------------|
| `master_sku` | 73 | 0 | 100% | Fully populated (NOT NULL constraint) |
| `platform` | 73 | 0 | 100% | Fully populated (NOT NULL constraint) |
| `batch_id` | 23 | 50 | 31.5% | Expected -- not all publishes are batched |
| `content_version` | 22 | 51 | 30.1% | Needs enforcement going forward |
| `prompt_hash` | 2 | 71 | 2.7% | Backfillable from `generated_content.generation_prompt_hash` |
| `evidence_hash` | 2 | 71 | 2.7% | Backfillable if evidence data is available at publish time |
| `final_payload_hash` | 2 | 71 | 2.7% | Derivable from `final_payload_snapshot` |
| `segment_key` | 0 | 73 | 0% | Never populated -- enforce going forward |
| `published_title` | -- | -- | -- | Not audited (content snapshot, not a join key) |
| `published_description` | -- | -- | -- | Not audited (content snapshot, not a join key) |

**Key finding:** The migration 034 columns (`prompt_hash`, `evidence_hash`, `final_payload_hash`, `segment_key`) were added but the publishing code only started populating `prompt_hash` in the week of 2026-02-16 (2 events out of 11 that week = 18.2%).

### 1.2 performance_snapshots Column Completeness

**Total rows:** 179

| Column | Non-NULL | NULL | % Populated | Assessment |
|--------|----------|------|-------------|------------|
| `master_sku` | 179 | 0 | 100% | Fully populated (NOT NULL constraint) |
| `platform` | 179 | 0 | 100% | Fully populated (NOT NULL constraint) |
| `publish_event_id` | 178 | 1 | 99.4% | Excellent -- nearly all linked |
| `content_version` | 14 | 165 | 7.8% | Needs enforcement going forward |
| `days_since_publish` | 178 | 1 | 99.4% | Excellent -- calculated from publish_events |
| `cohort_type` | **COLUMN MISSING** | -- | -- | Not in production schema (documented in SCHEMA.md but never applied) |
| `product_category` | **COLUMN MISSING** | -- | -- | Not in production schema (documented in SCHEMA.md but never applied) |

**Schema drift finding:** `cohort_type` and `product_category` columns exist in SCHEMA.md documentation but are NOT present in the production `performance_snapshots` table. The production table has 18 columns; SCHEMA.md documents 20. These columns were likely part of migration 035 (performance_impact_scores) that was never fully applied.

### 1.3 performance_impact_scores

**Table does NOT exist in production.** The `performance_impact_scores` table is documented in SCHEMA.md and referenced in migration 035, but the table was never created in production.

**Impact:** Diff-in-diff scoring is not available. Phase 29 must either create this table or implement the feedback view without impact scores.

### 1.4 Join Chain Completeness (The Actual Feedback View Join)

```
generated_content.generation_prompt_hash (484/584 = 82.9% populated)
    -> publish_events.prompt_hash (2/73 = 2.7% populated)
    -> publish_events.content_version (22/73 = 30.1% populated)
    -> performance_snapshots.publish_event_id (178/179 = 99.4% populated)
    -> performance_snapshots.content_version (14/179 = 7.8% populated)
    -> performance_impact_scores.publish_event_id (TABLE DOES NOT EXIST)
```

**Direct join results (performance_snapshots LEFT JOIN publish_events):**

| Metric | Count | % of Snapshots |
|--------|-------|----------------|
| Total snapshots | 179 | 100% |
| Snapshots with `publish_event_id` | 178 | 99.4% |
| Matched to publish_events row | 178 | 99.4% |
| Matched with `prompt_hash` available | 0 | 0% |
| Matched with `content_version` available | 14 | 7.8% |

**Why 0% prompt_hash through the join:** The 2 publish_events that have `prompt_hash` (IDs 73, 74 -- SKUs CL-28-24 and CL-29, published 2026-02-21) do not yet have corresponding performance snapshots. Snapshot capture has not run for these SKUs since they were published with prompt tracking.

### 1.5 Temporal Analysis: When Did prompt_hash Start Being Populated?

| Week | Events | With prompt_hash | % |
|------|--------|------------------|---|
| 2026-02-02 | 25 | 0 | 0% |
| 2026-02-09 | 33 | 0 | 0% |
| 2026-02-16 | 11 | 2 | 18.2% |

`prompt_hash` population began the week of 2026-02-16 when the `expand-variants.ts` code was updated to copy `generation_prompt_hash` from `generated_content` to `publish_events.prompt_hash` during publishing.

### 1.6 Data Overlap Summary

| Metric | Count |
|--------|-------|
| Distinct SKUs with performance snapshots | 39 |
| Distinct SKUs with successful publish events | 42 |
| SKUs with BOTH snapshots and publish events | 39 |
| `generated_content` rows with `generation_prompt_hash` | 484/584 (82.9%) |

---

## Part 2: Go/No-Go Decision for Feedback View (Phase 29 FEED-01)

### Decision: **GO** -- with backfill strategy

**Rationale:**

1. **The join chain is structurally sound.** 99.4% of snapshots link to publish_events via `publish_event_id`. The infrastructure works.

2. **The data gap is temporal, not structural.** `prompt_hash` population started 2026-02-16. Prior events lack it because the code path didn't exist yet. All future publishes will populate it.

3. **Backfill is possible for `prompt_hash`.** 82.9% of `generated_content` rows have `generation_prompt_hash`. A backfill script can match `publish_events` to `generated_content` on `(master_sku, platform)` and copy the hash. This would retroactively link ~67 of the 69 success events.

4. **Even without backfill, the view is useful.** Per user decision: "Any linked data is useful -- even 10 records justifies building the view." The 178 snapshot-to-publish_event links provide content-performance correlation even without prompt_hash (via `master_sku + platform`).

5. **content_version is a secondary concern.** Only 30.1% of publish_events have it, but the feedback view can still function using `master_sku + platform` as the primary join key. Content version adds precision but isn't required for the minimum viable view.

### Minimum Viable Feedback View Join

```sql
-- This join works TODAY with 178/179 rows matching
SELECT
  ps.master_sku,
  ps.platform,
  ps.snapshot_date,
  ps.impressions,
  ps.clicks,
  ps.ctr,
  ps.days_since_publish,
  pe.published_at,
  pe.published_title,
  pe.prompt_hash,       -- NULL for pre-Feb-16 events
  pe.content_version,   -- NULL for ~70% of events
  gc.candidate_content,
  gc.quality_score,
  gc.generation_prompt_hash
FROM performance_snapshots ps
JOIN publish_events pe ON ps.publish_event_id = pe.id
LEFT JOIN generated_content gc
  ON pe.master_sku = gc.master_sku
  AND pe.platform = gc.platform
  AND gc.content_type = 'title'
WHERE pe.status = 'success';
```

---

## Part 3: Phase 29 Recommendations

### 3.1 Columns to Enforce NOT NULL Going Forward

| Column | Table | Action | Reasoning |
|--------|-------|--------|-----------|
| `prompt_hash` | publish_events | Enforce NOT NULL on new inserts | Required for content-performance feedback loop |
| `content_version` | publish_events | Enforce NOT NULL on new inserts | Needed for A/B tracking of prompt versions |
| `content_version` | performance_snapshots | Enforce NOT NULL on new inserts | Should mirror the version from the linked publish_event |
| `segment_key` | publish_events | Enforce NOT NULL on new inserts | Required for segment-level analysis |

**Note:** Do NOT add ALTER TABLE constraints retroactively (would fail on existing NULLs). Instead, enforce at the application layer in the publishing code paths.

### 3.2 Backfill Opportunities

| Column | Backfill Source | Feasibility | Priority |
|--------|----------------|-------------|----------|
| `publish_events.prompt_hash` | `generated_content.generation_prompt_hash` via `(master_sku, platform)` join | HIGH -- 82.9% of source data has the hash | P1 -- enables full feedback chain |
| `publish_events.content_version` | `generated_content.version` via `(master_sku, platform)` join | HIGH -- version data exists in generated_content | P1 -- enables version tracking |
| `publish_events.final_payload_hash` | Derive from `final_payload_snapshot` using SHA-256 | MEDIUM -- requires hashing existing JSONB | P2 -- nice to have for payload diffing |
| `publish_events.segment_key` | Derive from `product_catalog.category` or `custom_label_0` | MEDIUM -- requires business rule definition | P3 -- needed for segment analysis |
| `performance_snapshots.content_version` | Copy from linked `publish_events.content_version` after that backfill | HIGH -- direct FK join | P1 -- chain dependency |

### 3.3 Schema Drift Issues to Address

1. **`performance_snapshots`** is missing `cohort_type` and `product_category` columns documented in SCHEMA.md. Decision needed: add them via ALTER TABLE, or update SCHEMA.md to match production.

2. **`performance_impact_scores`** table does not exist. If Phase 29 needs diff-in-diff scoring, this table must be created first.

3. **SCHEMA.md** should be updated to reflect actual production state. The documentation currently overstates what exists.

### 3.4 Minimum Viable Join for Feedback View

The feedback view should use:
- **Primary join:** `performance_snapshots.publish_event_id -> publish_events.id` (99.4% match rate)
- **Content join:** `publish_events.(master_sku, platform) -> generated_content.(master_sku, platform)` (works for all events)
- **Optional enrichment:** `publish_events.prompt_hash` (2.7% now, 100% after backfill)

The view does NOT need `performance_impact_scores` for its initial version. Simple before/after comparison using `performance_baselines` vs `performance_snapshots` is sufficient.

---

## Part 4: API Quota Analysis

### 4.1 Google Ads Standard Access Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Requests per day | 15,000 | Per developer token |
| Operations per request | 1,000 | Mutate operations (not relevant for read-only GAQL) |
| GAQL query limit | None specific | Limited by request count, not query complexity |
| Rate limiting | Token bucket | Soft limit; brief bursts allowed |

Standard Access is the current access tier for developer token `GOOGLE_ADS_DEVELOPER_TOKEN`. No rate limit issues have been observed in production.

### 4.2 Complete Google Ads API Call Site Catalog

#### 4.2.1 TypeScript Layer: `dashboard/src/lib/google-ads.ts`

| # | GAQL View | Purpose | Trigger | Persists To |
|---|-----------|---------|---------|-------------|
| 1 | `shopping_performance_view` | Fetch product performance by Shopify product IDs | Dashboard baseline capture (`/api/performance/capture-baseline`), SKU selection page | `performance_baselines` table |

**1 GAQL query per invocation.** Fetches ALL shopify products for date range, filters in-memory. Triggered sporadically by user actions (baseline capture, SKU selection).

#### 4.2.2 TypeScript Layer: `dashboard/src/lib/shopping-funnel/service.ts`

| # | GAQL View/Resource | Purpose | Trigger |
|---|-------------------|---------|---------|
| 1 | `campaign` | List enabled Shopping campaigns | `buildAdsContext()` |
| 2 | `ad_group` | List enabled Shopping ad groups | `buildAdsContext()` |
| 3 | `shared_set` | List negative keyword shared sets | `buildAdsContext()` |
| 4 | `campaign_criterion` | Campaign-level negative keywords | `buildAdsContext()` |
| 5 | `ad_group_criterion` | Ad group-level negative keywords | `buildAdsContext()` |
| 6 | `search_term_view` | Shopping search terms with metrics | `buildAdsContext()` |
| 7 | `shared_criterion` | Shared set criteria (conditional) | `buildAdsContext()` |

**7 GAQL queries per context build.** All fired in parallel via `Promise.all()`. Context is cached in memory for 2 minutes (`CACHE_TTL_MS = 2 * 60 * 1000`).

**Persists to:** NOTHING. All data is held in a 2-minute in-memory cache. When the cache expires or the serverless function cold-starts, all 7 queries re-fire. No database writes.

**Trigger:** Any visit to the Shopping Funnel dashboard page, or any API call to `/api/search-terms/*` endpoints. Each uncached page load = 7 API requests.

#### 4.2.3 Python Layer: `src/feedops/integrations/google_ads_performance.py`

| # | GAQL View | Purpose | Trigger | Persists To |
|---|-----------|---------|---------|-------------|
| 1 | `shopping_performance_view` | Single product performance | `fetch_product_performance()` | `performance_snapshots` |
| 2 | `shopping_performance_view` | Batch product performance (chunked, 25 IDs/chunk) | `fetch_batch_product_performance()` | `performance_snapshots` |

**1-N GAQL queries per invocation** (N = ceil(offer_ids / 25) for batch mode, capped at 5 parallel). Triggered by Cloud Run `/performance/capture-baseline` and `/optimize-sku` endpoints.

#### 4.2.4 Python Layer: `src/feedops/integrations/google_ads_search_terms.py`

| # | GAQL View | Purpose | Trigger | Persists To |
|---|-----------|---------|---------|-------------|
| 1 | `campaign` | List Shopping campaigns | `SearchTermsClient._fetch_shopping_campaigns()` | (intermediate) |
| 2 | `shopping_performance_view` | Products by campaign | `SearchTermsClient._fetch_campaign_products()` | (intermediate) |
| 3 | `search_term_view` | Search terms with campaign context | `SearchTermsClient.fetch_search_terms()` | `search_queries`, `search_queries_by_master_sku` |
| 4 | `search_term_view` | Deprecated per-SKU terms | `get_terms_for_master_sku()` (dead code -- returns early) | N/A |
| 5 | `search_term_view` | Per-variant search terms | `get_search_terms_for_variant()` | (caller decides) |

**3-5 GAQL queries per sync invocation.** Triggered by Cloud Run `/search-insights/sync` endpoint. Query 4 is dead code (returns before executing).

#### 4.2.5 Python Layer: `src/feedops/integrations/google_ads_search_terms.py` (Keyword Planner)

| # | API | Purpose | Trigger | Persists To |
|---|-----|---------|---------|-------------|
| 1 | `KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics` | Search volume, competition data | `KeywordPlannerClient.get_historical_metrics()` | `keyword_metrics` table (30-day cache) |

**1 API call per batch of 100 keywords.** Uses DB-level caching with 30-day TTL. Triggered by `ensureSkuData()` during SKU selection/regeneration.

### 4.3 Daily API Usage Estimate

#### Current Usage (Dashboard-Triggered, Sporadic)

| Source | Queries/Invocation | Estimated Daily Invocations | Daily Total |
|--------|--------------------|-----------------------------|-------------|
| `google-ads.ts` (baseline capture) | 1 | 0-5 (manual, sporadic) | 0-5 |
| `service.ts` (funnel context) | 7 | 0-20 (page visits, 2-min cache) | 0-140 |
| Python performance (snapshot capture) | 1-5 | 0-3 (manual) | 0-15 |
| Python search terms (sync) | 3-5 | 0-2 (manual) | 0-10 |
| Keyword Planner | 1 per 100 keywords | 0-5 | 0-5 |
| **Current daily total** | | | **0-175** |

#### Proposed Additions (Phase 29-30)

| New Job | Queries/Run | Frequency | Daily Total |
|---------|-------------|-----------|-------------|
| Daily performance snapshot (Cloud Scheduler) | 3-5 (batch, ~100 product_ids in ~4 chunks) | 1x/day | 3-5 |
| Daily funnel snapshot (Phase 30 HIST-01) | 7 (mirrors service.ts pattern) | 1x/day | 7 |
| **Proposed daily addition** | | | **10-12** |

#### Total Projected Daily Usage

| Component | Daily Requests |
|-----------|----------------|
| Current sporadic usage (worst case) | 175 |
| Proposed daily jobs | 12 |
| **Total projected** | **~187** |
| **Standard Access limit** | **15,000** |
| **Utilization** | **~1.2%** |
| **Remaining headroom** | **~14,813 requests** |

### 4.4 Redundant API Call Analysis

#### Redundancy 1: `shopping_performance_view` (TS + Python)

| Layer | File | When Called | Data Window |
|-------|------|------------|-------------|
| TypeScript | `google-ads.ts` | Baseline capture (user-triggered) | 7d/30d/90d |
| Python | `google_ads_performance.py` | Snapshot capture (Cloud Run) | 30d typically |

**Overlap:** Both query the same view for the same products. The TS layer fetches for baseline calculation, the Python layer for ongoing snapshots.

**Recommendation:** Not a problem today (different purposes, both persist results). If daily snapshots are added via Cloud Scheduler (Python), the TS baseline capture becomes redundant for most use cases. Consider deprecating `google-ads.ts` baseline capture and using Python pipeline results stored in `performance_baselines` instead.

#### Redundancy 2: `search_term_view` (service.ts + Python)

| Layer | File | When Called | Persists? |
|-------|------|------------|-----------|
| TypeScript | `service.ts` | Every Shopping Funnel page visit (7 queries, 2-min cache) | NO |
| Python | `google_ads_search_terms.py` | Manual sync trigger | YES (`search_queries` table) |

**Overlap:** Both query `search_term_view` for the same Shopping campaigns. The Python layer persists results; the TS layer discards after 2 minutes.

**This is the most wasteful redundancy.** On an active dashboard session, service.ts can fire 7 queries every 2 minutes. Over 30 minutes of active use, that is 105 API requests -- all discarded.

**Recommendation:** Implement write-behind caching for service.ts:
1. On first call, query Google Ads API and persist results to a `funnel_context_cache` table
2. On subsequent calls within the same day, serve from DB cache
3. Add a "refresh" button for manual cache invalidation
4. Phase 30 (HIST-01) should create `funnel_snapshots_daily` table for this purpose

#### Redundancy 3: `campaign` resource (service.ts + Python search_terms)

| Layer | File | Purpose |
|-------|------|---------|
| TypeScript | `service.ts` | List Shopping campaigns for context |
| Python | `google_ads_search_terms.py` | List Shopping campaigns for search term association |

**Overlap:** Same query, different runtimes.

**Recommendation:** Low priority. Campaign list is a lightweight query and only fires 1x per context build. Not worth optimizing.

### 4.5 Caching Strategy Recommendations

#### Strategy 1: Write-Behind for service.ts (Priority: HIGH)

**Problem:** service.ts issues 7 GAQL queries per context build with only 2-minute in-memory caching. Active dashboard use generates significant API traffic with zero persistence.

**Solution:**
1. Create `funnel_snapshots_daily` table (Phase 30 HIST-01 already plans this)
2. First context build of the day: query Google Ads API, persist to DB
3. Subsequent builds: serve from DB, skip API calls
4. Add daily Cloud Scheduler job to pre-warm the cache before business hours
5. Keep manual "refresh" capability for ad-hoc needs

**Impact:** Reduces service.ts API calls from ~140/day (worst case) to 7/day (one context build + daily scheduler).

#### Strategy 2: Time-Based Cache for Daily Snapshots (Priority: MEDIUM)

**Problem:** Performance snapshot capture queries Google Ads for the same date range data that doesn't change intra-day (Google Ads data updates once per day).

**Solution:**
1. Cloud Scheduler triggers snapshot capture once daily (early morning, after Google Ads data refreshes)
2. If called again same day, skip API call and return cached DB results
3. Use `fetched_at` timestamp to determine staleness

**Impact:** Prevents accidental duplicate snapshot runs. Ensures data freshness without wasted calls.

#### Strategy 3: Consolidate TS/Python Performance Queries (Priority: LOW)

**Problem:** Both `google-ads.ts` and `google_ads_performance.py` query `shopping_performance_view`.

**Solution:**
1. Make Python pipeline the single authoritative source for performance data
2. Have TS baseline capture read from `performance_baselines` table instead of calling Google Ads directly
3. Python pipeline runs daily via Cloud Scheduler, populating both baselines and snapshots

**Impact:** Eliminates one API integration point entirely. Simplifies the codebase. Low priority because current overlap is minimal.

### 4.6 Verdict

**Daily snapshot capture is SUSTAINABLE within Google Ads Standard Access limits.**

- Projected usage: ~187 requests/day (1.2% of 15,000 limit)
- Even with 10x growth in dashboard usage: ~1,870 requests/day (12.5% of limit)
- Even with aggressive automated jobs (hourly instead of daily): ~1,000 requests/day (6.7% of limit)
- Standard Access is effectively unlimited for Allied FeedOps' scale (2,784 SKUs, single account)

**No quota concerns whatsoever.** The only reason to implement caching is to reduce latency and avoid wasted API calls, not to stay within quota limits.
