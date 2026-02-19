# Phase 13 Diagnosis: Google Ads Data Sourcing Bugs

**Date:** 2026-02-19
**Author:** Claude

## Executive Summary

Two data sourcing bugs exist in the Google Ads integration. Bug 1 is confirmed and critical: `fetch_search_terms()` attributes ALL search terms in a campaign to the single highest-impression variant of that campaign (`item_ids[0]`), rather than distributing them across the variants that actually triggered each term. This means every row in `search_queries` for a multi-variant SKU has the same `gmc_offer_id`, making variant-level attribution meaningless. Bug 2 requires empirical confirmation: `collect_performance_batch()` passes lowercase `shopify_us_*` offer IDs to the Google Ads API shopping_performance_view; Phase 0 documented that lowercase is the correct format for API queries, but this must be verified against actual data to confirm whether performance_baselines are populated correctly.

---

## Bug 1: Search Terms — Campaign-Level Attribution Instead of Variant-Level

### Code Trace

**Step 1:** `collect_search_terms_batch()` in `src/feedops/jobs/workers.py` (line 104) calls `client.fetch_search_terms(days=180, limit=10000)`.

**Step 2:** `fetch_search_terms()` in `src/feedops/integrations/google_ads_search_terms.py` (line 525) executes a two-step query:

- Step 2a (lines 549-550): Calls `self._fetch_campaign_products(days)` to get all products grouped by campaign.
- `_fetch_campaign_products()` (lines 462-523) queries `shopping_performance_view` for products with impressions, ordered by `metrics.impressions DESC` (line 489). Results are deduplicated and stored in a `campaign_products` dict: `campaign_id → list[item_id]`. **The list is in impressions-DESC order because that's how the GAQL ORDER BY clause sorts them.**

**Step 3:** (lines 553-570): Queries `search_term_view` for all search terms, joining on `campaign.id`.

**Step 4 — THE BUG (lines 593-603):**
```python
# Step 3: Find products in this campaign
item_ids = campaign_products.get(campaign_id, [])

# If we have products, look up variant info for the first one
gmc_offer_id = None
variant_info = {}

if item_ids:
    # item_id format is already the GMC offer ID
    gmc_offer_id = item_ids[0]          # <-- BUG: always the highest-impression variant
    variant_info = self.get_variant_info(gmc_offer_id)
```

**The bug:** For every search term in a campaign, `item_ids[0]` is used. This is the variant with the most impressions in that campaign over the last N days. A campaign typically contains 10-28 variants of a single product (all finishes). All search terms for that campaign are attributed to the single highest-impression finish, regardless of which variant actually triggered the search term.

**Step 5:** The result dict (lines 605-620) stores `gmc_offer_id`, `master_sku`, `finish`, `finish_code` derived from `item_ids[0]`. The `item_ids` field (line 614) includes up to 10 item_ids for context, but the attribution fields all reference `item_ids[0]`.

**Step 6:** `save_search_terms_to_db()` (lines 870-959) deduplicates on `(query_text, gmc_offer_id)` and upserts. Since ALL terms share the same `gmc_offer_id` (the highest-impression variant), there are at most as many rows in `search_queries` as there are unique `query_text` values per campaign — all attributed to one variant.

### What the Code Does

For each search term row from `search_term_view`, the code looks up which campaign produced that search term, then assigns the variant with the highest total impressions in that campaign to be the "owner" of that search term. This is a campaign-level join, not a variant-level join. The result: a product like a towel bar with 28 finishes will have all search queries attributed to, say, the Polished Chrome (PC) finish if PC has the most impressions — even queries containing "antique brass" that could only have triggered the AB variant.

### What It Should Do

The correct behavior from Phase 0 research (DATA-01): the campaign-join pattern was designed to **list all products in each campaign** and then match search terms to the specific product(s) that triggered them. The correct implementation should either:

1. **Option A (per-variant row):** Create one row per `(search_term, variant)` combination for each variant in the campaign — preserving that a search term could have been triggered by any of the campaign's products.
2. **Option B (campaign-level row):** Store the search term once per campaign with `item_ids` as the full list, and treat variant attribution as "all variants in this campaign" — accepting that true per-variant attribution is impossible without segment.product_item_id in search_term_view.

The fix specification (Plan 2) will choose between these based on what data structure supports the dashboard's needs. Based on the Plan 2 plan file, the approach appears to be inserting one row per variant per search term (Option A), or more likely one row per campaign with the full `item_ids` list stored.

### Impact

- `search_queries` table: every row for a multi-variant SKU has the same `gmc_offer_id` — the highest-impression finish of the campaign.
- `master_sku` field is populated correctly (derived from `item_ids[0]` which is in the same SKU family).
- Variant breakdown in the dashboard (e.g., the finish selector showing which variant has the most search impressions) is wrong — it will always show one finish as having 100% of search queries.
- `finish_code` and `finish` fields are wrong for all terms that did not trigger via the highest-impression variant.

---

## Bug 2: Performance Metrics — Offer ID Case Analysis

### Code Trace

**Step 1:** `collect_performance_batch()` in `src/feedops/jobs/workers.py` (lines 255-265) queries `variant_index` for all `gmc_offer_id` values for each SKU:
```python
result = supabase.table("variant_index").select("gmc_offer_id").eq("master_sku", sku).execute()
offer_ids = [row["gmc_offer_id"] for row in result.data if row.get("gmc_offer_id")]
```
`variant_index` stores offer IDs as **lowercase** `shopify_us_*` (confirmed by SCHEMA.md and the backfill.py `normalize_offer_id()` comment: "Database stores offer IDs as shopify_us_*").

**Step 2:** (lines 281-285) These lowercase offer IDs are passed directly to `fetch_batch_product_performance()`:
```python
performance_data = fetch_batch_product_performance(
    offer_ids=all_offer_ids,   # lowercase shopify_us_*
    start_date=start_date,
    end_date=end_date,
)
```

**Step 3:** `fetch_batch_product_performance()` in `src/feedops/integrations/google_ads_performance.py` (lines 326-328) builds the GAQL IN clause directly from these IDs:
```python
safe_ids = [oid.replace("'", "\\'") for oid in offer_ids]
ids_clause = ", ".join(f"'{oid}'" for oid in safe_ids)
```
The GAQL query (lines 330-346) uses:
```sql
WHERE segments.product_item_id IN (ids_clause)
```

**Step 4:** The API returns rows grouped by `segments.product_item_id`. The code then looks up results using the original `offer_id` as the key (line 365):
```python
product_rows = grouped.get(offer_id, [])
```
If Google Ads returns uppercase `shopify_US_*` but we're looking up with lowercase `shopify_us_*`, the `grouped.get()` will miss all data → empty result → `_empty_performance_result()` → all zeros.

### What the Code Does

The code sends lowercase `shopify_us_*` offer IDs to the `shopping_performance_view` GAQL query. Phase 0 Decision #4 explicitly documented: "API expects shopify_us_ format (lowercase 'us')". The `backfill.py` comment for `normalize_offer_id()` also says lowercase is correct for API queries. However, the `fetch_product_performance()` docstring (line 106) shows an example with UPPERCASE: `'shopify_US_7721863643362_42804912849122'`.

**This is a contradictory signal in the codebase.** The Phase 0 documentation says lowercase works; the `fetch_product_performance()` docstring uses uppercase; the actual `shopping_performance_view` API behavior in production is unknown until we query the database.

### What the Actual Behavior Is (Hypothesis)

If Google Ads' `shopping_performance_view` is **case-insensitive** in the WHERE clause, lowercase IDs work fine and performance_baselines are correctly populated. If it is **case-sensitive** and requires uppercase, all baselines would be zero/empty.

### Impact (Pending Empirical Confirmation)

- If performance_baselines are non-zero for published SKUs → case mismatch is NOT a bug (API is case-insensitive or accepts lowercase).
- If performance_baselines are all zero → case mismatch is confirmed as Bug 2.

The empirical evidence section below will resolve this.

---

## Process Retrospective

### Timeline: Phase 0 Research → Phase 6 Implementation → Current Bug

**Phase 0 (Discovery — DATA-01):** The research team established the "campaign-join pattern" because `search_term_view` cannot be directly filtered by `segments.product_item_id`. The documented solution was: query `shopping_performance_view` to get `{campaign_id → [product_item_ids]}`, then join search terms via campaign_id. The Phase 0 STATE.md records: "Search Terms Filtering Approach: Worker filters results after fetch (client is batch-native with campaign-join pattern). Client handles campaign-join, worker handles batch filtering."

**Phase 6 (Implementation):** The `SearchTermsClient.fetch_search_terms()` method was implemented with the campaign-join structure correctly: it fetches campaign→product mappings, then fetches search terms with campaign.id. The code at line 594-603 correctly retrieves `item_ids = campaign_products.get(campaign_id, [])`.

**Where it diverged:** The comment at line 596 reads "If we have products, look up variant info for the first one" — this is where the implementation chose `item_ids[0]` instead of iterating over all `item_ids`. The Phase 0 research described getting the list of products per campaign for *matching purposes*, but the implementation interpreted "join via campaign to associate search terms with products" as "pick the first product in the campaign."

**Why Phase 0/6/7 didn't catch it:**

1. **Phase 0** validated that the campaign-join pattern works in principle (you CAN get search terms associated with campaigns that contain your products) — but did not specify what to do when a campaign has multiple products. The research treated "product per campaign" as roughly 1:1, when in reality each campaign typically contains all 10-28 variants of a product.

2. **Phase 6** implemented `item_ids[0]` as a reasonable first approximation. The code even includes `"item_ids": item_ids[:10]` in the result (line 614) — suggesting awareness that there are multiple products per campaign — but the attribution logic still uses only index 0.

3. **Phase 7** (Data Quality & Validation) validated data structure and ranges (validation errors, contamination checks) but did not validate semantic correctness — it didn't check whether the `gmc_offer_id` in search_queries actually matched one of the correct variants for the attributed master_sku. A row with gmc_offer_id for finish "PC" and query_text "antique brass towel bar" would pass all structural validation.

4. **Testing gap:** The system was never tested with a dashboard showing "which finish has the most search queries" before real data revealed the problem. The bug is invisible until you notice that all search queries for a SKU show the same finish.

**Root cause in one sentence:** Phase 0 documented the data structure (campaign → list of products) without specifying the correct many-to-many resolution strategy, and Phase 6 implemented a single-item shortcut (`item_ids[0]`) that is structurally valid but semantically incorrect for multi-variant campaigns.

---

## Fix Specification

### Files to Modify

| File | Change |
|------|--------|
| `src/feedops/integrations/google_ads_search_terms.py` | Fix `fetch_search_terms()` to emit one result per variant per search term (or store all item_ids and set gmc_offer_id = None for campaign-level rows) |
| `src/feedops/jobs/workers.py` | Add per-SKU delete before re-insert in `collect_search_terms_batch()` + add `synced_at` timestamp |
| `supabase/migrations/NNN_add_synced_at_to_search_queries.sql` | Add `synced_at` column to `search_queries` table |
| `docs/database/SCHEMA.md` | Update search_queries schema to document `synced_at` column |

### What Does NOT Change

- `fetch_batch_product_performance()` queries `shopping_performance_view` — this is the correct API view and is confirmed by Phase 0 research and the existing implementation.
- The upsert conflict key `(query_text, gmc_offer_id, period_start, period_end)` in `save_search_terms_to_db()` — this remains the right deduplication key.
- The batch infrastructure (`BatchProcessor`, `backfill.py`, `workers.py` structure) — no architectural changes needed.
- `performance_baselines` table and `collect_performance_batch()` — pending empirical confirmation; likely no change needed if Phase 0's lowercase-is-correct was accurate.

### The Fix for Bug 1 (Confirmed)

**Option chosen per Plan 2:** Replace `gmc_offer_id = item_ids[0]` with iteration over all `item_ids` in the campaign, emitting one result dict per variant. This means each search term produces N rows (one per variant in the campaign), each with the correct `gmc_offer_id`, `master_sku`, `finish`, `finish_code`.

This is a "fan-out" approach: one search_term_view row → N search_queries rows (one per campaign product). This is semantically correct for the dashboard's use case: all variants that were active in the campaign could have triggered the search term, and the dashboard aggregates by master_sku anyway.

**Per-SKU delete before re-insert:** Per context decision, before re-inserting a SKU's search terms, delete existing rows: `DELETE FROM search_queries WHERE master_sku = $sku`. This ensures clean slate without full table wipe, and is safe for resume.

**synced_at column:** Add to `search_queries` to distinguish corrected data from old data.

### The Fix for Bug 2 (Conditional on Empirical Evidence)

- If performance_baselines show **non-zero** impressions/clicks for published SKUs: Bug 2 is NOT present — lowercase offer IDs work correctly with the API. No change needed.
- If performance_baselines show **all zeros**: Add uppercase transformation before `fetch_batch_product_performance()` call, similar to `save_search_terms_to_db()` which already normalizes to uppercase before saving to DB.

### Data Cleanup Plan

- `search_queries`: Per-SKU delete + re-insert via backfill job (`search_terms` job type across all 2,784 SKUs)
- `performance_baselines`: Re-capture only if Bug 2 is confirmed (all-zeros in empirical evidence)
- `performance_snapshots`: No change — snapshots are post-publish data, not affected by this bug

### Success Verification

**SQL queries to run post-fix:**

```sql
-- 1. Confirm multiple distinct gmc_offer_ids per master_sku (Bug 1 fixed)
SELECT master_sku, COUNT(DISTINCT gmc_offer_id) as offer_ids, COUNT(DISTINCT query_text) as queries
FROM search_queries
WHERE master_sku IN (SELECT DISTINCT master_sku FROM publish_events WHERE platform = 'google' LIMIT 5)
GROUP BY master_sku
ORDER BY offer_ids DESC;
-- Expected: offer_ids > 1 for multi-variant SKUs (was = 1 before fix)

-- 2. Confirm synced_at timestamp exists on new rows
SELECT master_sku, COUNT(*) as rows, MAX(synced_at) as last_synced
FROM search_queries
WHERE synced_at IS NOT NULL
GROUP BY master_sku
LIMIT 10;
-- Expected: non-null synced_at, recent timestamps

-- 3. Confirm performance_baselines are non-zero
SELECT master_sku, avg_impressions, avg_clicks, avg_ctr
FROM performance_baselines
WHERE platform = 'google'
ORDER BY avg_impressions DESC
LIMIT 10;
-- Expected: non-zero values (if Bug 2 not present)
```

**Dashboard visual check:**
- `/search-insights/[sku]`: Variant breakdown should show multiple finishes with different impression counts
- `/performance`: Baselines table should show non-zero impressions for published SKUs

---

## Empirical Evidence

*This section will be populated by Task 2 (Supabase MCP queries).*
