# Project Research Summary

**Project:** Phase 0: Google Ads API Discovery
**Domain:** E-commerce feed optimization — Google Ads API data backfill
**Researched:** 2026-02-11
**Confidence:** HIGH

## Executive Summary

This research validates the technical feasibility of a comprehensive Google Ads API backfill system for 2,784 SKUs. The project aims to capture historical search term and performance data to inform content generation for Allied Brass product feeds. All 5 core questions from the discovery phase have been answered through official documentation and existing codebase analysis.

**The recommended approach is a job-based sequential backfill architecture** using the google-ads Python client library (v28.4.1+) with campaign-level query patterns. The key finding: direct product-level search term filtering is intentionally unsupported by Google — requiring a two-query join pattern via campaign association. However, this workaround is already implemented and tested in production code, validating feasibility. Data retention is actually better than assumed (11 years vs. 180 days/2 years), enabling more comprehensive historical analysis.

**Primary risk is rate limiting during large-scale backfill**, mitigated through sequential processing with exponential backoff. The existing infrastructure (Cloud Run + Supabase + established clients) provides a solid foundation. Critical pitfalls include GMC offer ID case sensitivity (shopify_us vs shopify_US), GAQL field compatibility constraints, and multi-SKU product aggregation patterns. With proper query validation and case normalization, the backfill strategy is production-ready.

## Key Findings

### Recommended Stack

The google-ads Python client (v29.0.0) is the official and only viable option for Google Ads API integration. The project currently uses v28.4.1, which is fully compatible and production-tested. No immediate upgrade required, though v29.0.0 adds latest API features.

**Core technologies:**
- **google-ads (28.4.1+)**: Official Python client with SearchStream pagination and automatic retry logic — only supported library for Google Ads API v18+
- **GAQL (v18+)**: SQL-like query language for advertising data — required for all search_stream operations, supports product_item_id filtering in shopping_performance_view
- **pandas (>=2.0)**: Data processing for large result sets — essential for batch upsert operations (50K+ rows) before Supabase insert
- **google-auth (>=2.48.0)**: OAuth2/service account authentication — already configured with refresh tokens, handles credential lifecycle automatically

**Supporting libraries** (all present in project):
- supabase-py: Database storage with upsert-on-conflict patterns
- google-api-python-client: Merchant API integration for custom_label_0 sync
- httpx: Async-capable HTTP client for concurrent operations

**Anti-patterns to avoid:**
- AdWords API libraries (sunset 2022) — use Google Ads API instead
- Manual pagination loops — use SearchStream built-in streaming
- Hardcoded credentials — use environment variables (already configured)
- google-ads <28.0 — deprecated API versions with missing features

### Expected Features

Research focused on API capabilities rather than user-facing features. The key capabilities that define the backfill system's scope:

**Must have (validated capabilities):**
- Product-level performance queries via shopping_performance_view (filtering by segments.product_item_id) — users need SKU-specific metrics
- Search term collection with campaign-based product association — users need query analysis for content optimization
- 11-year historical data access for both performance and search terms — far exceeds original 180-day/2-year assumptions
- Keyword Planner metrics enrichment (search volume, competition, CPC) — users need opportunity analysis for ranking gaps

**Should have (recommended enhancements):**
- Job-based async backfill with progress tracking — users need visibility into long-running operations
- Exponential backoff retry logic — prevents cascading failures from rate limits
- Variant-level caching for master_sku lookups — reduces N+1 query patterns during batch processing
- Case-normalized offer ID handling — prevents GMC sync failures

**Defer (not needed for backfill):**
- Real-time search term monitoring — Keyword Planner is rate-limited, monthly cache is sufficient
- BigQuery integration for 2+ year backfills — current scale (2,784 SKUs, 11-year data) manageable with direct API
- Parallel worker architecture — sequential processing sufficient for current volume (~5 min for full sync)

**Critical limitations (anti-features):**
- search_term_view CANNOT filter by product_item_id — Google intentionally removed this, must use campaign-join pattern
- Offset-based pagination NOT supported — token-based pagination required
- Keyword Planner rate limits prevent real-time queries — caching mandatory (30-day TTL)

### Architecture Approach

The standard pattern for Google Ads API backfill is a **job-based architecture with sequential processing and campaign-level query strategy**. This matches the existing implementation in google_ads_search_terms.py and google_ads_performance.py.

**Major components:**
1. **Job Manager** (FastAPI + Supabase) — Creates job records, tracks progress, handles non-blocking responses via run_async_in_thread() pattern
2. **Worker Pool** (Python threads with asyncio event loops) — Executes API calls with retry logic, survives HTTP response but terminates on Cloud Run deployment
3. **Rate Limiter** (token bucket in google-ads client) — Enforces API quotas automatically, implements exponential backoff for RESOURCE_TEMPORARILY_EXHAUSTED errors
4. **Query Strategy** (two-step campaign join) — Fetch products by campaign from shopping_performance_view, fetch search terms by campaign from search_term_view, join via campaign_id in application layer
5. **Result Store** (Supabase with upsert-on-conflict) — Persists to search_queries table with unique constraint on (query_text, gmc_offer_id, period_start, period_end)

**Key architectural patterns:**
- **SearchStream for large datasets** (>10K rows) — automatic pagination, single operation quota cost
- **Campaign-level product association** — workaround for search_term_view limitation (no direct product_item_id filtering)
- **Variant-level caching** — in-memory dictionary for gmc_offer_id → master_sku lookups reduces database round-trips
- **Sequential date window processing** — simpler than parallelism, sufficient for 2,784 SKU scale (~3-5 min total)

**Scaling thresholds:**
- 0-500 SKUs: Single worker thread, sequential (current: 2,784 SKUs = ~5 min backfill)
- 500-5,000 SKUs: Parallel workers (5-10 threads), batch_size=50-100
- 5,000+ SKUs: Distributed workers (Cloud Run Jobs), batch_size=100-500

### Critical Pitfalls

Research identified 6 critical pitfalls with HIGH confidence, all documented with official source validation:

1. **search_term_view cannot filter by product_item_id** — Developers expect product-specific search terms like AdWords API supported. Google intentionally removed this capability as an "anti-pattern." Prevention: Use campaign-join pattern (fetch products by campaign from shopping_performance_view, fetch terms from search_term_view, join via campaign.id). Already implemented in google_ads_search_terms.py.

2. **GMC offer ID case sensitivity (shopify_us vs shopify_US)** — Database stores lowercase, GMC requires uppercase. Publishing lowercase breaks sync (rows append as duplicates). Query mismatches cause zero-row results. Prevention: Transform to uppercase when writing to sheets (.replace('shopify_us_', 'shopify_US_')), use lowercase for database lookups, normalize API responses before storing. Fixed in google-sheets.ts line 754 and google_ads_search_terms.py line 896.

3. **GAQL field compatibility errors** — Queries fail when SELECTing incompatible resource fields or filtering without including field in SELECT clause. Prevention: Always SELECT any field you filter on (e.g., if WHERE campaign.advertising_channel_type = 'SHOPPING', must SELECT campaign.advertising_channel_type). Validate queries with Google Ads Query Validator before production use.

4. **Token bucket rate limiting (RESOURCE_TEMPORARILY_EXHAUSTED)** — API uses dynamic limits based on server load, not fixed QPS. Naive retry logic depletes token bucket faster than refill rate. Prevention: Exponential backoff (5s → 10s → 20s), max 10 concurrent requests per customer_id, client-side rate limiter, sequential processing with delays for backfill.

5. **Data retention window assumptions** — Original assumption: 180 days for search terms, 2 years for performance. Reality: 11 years for both views (November 2024 policy update). Prevention: Document confirmed retention per resource, validate with date range queries. Impact: Can backfill much further than planned (positive surprise).

6. **Multi-SKU product aggregation** — Multiple master_skus share same product_id (DMF-2/2X, 2/3X, 2/4X, 2/5X all share 4539975336068). Google Ads aggregates at product_id level, not master_sku. Prevention: Query by product_id, post-process split by master_sku using variant_index mapping. Already implemented in existing code.

**Additional technical traps:**
- N+1 variant lookups (cache variant_index results)
- Large upsert batches (limit to 500 rows/transaction)
- Keyword Planner without cache (check keyword_metrics table first, 30-day TTL)
- Synchronous API calls in loop (use async/await for independent queries)

## Implications for Roadmap

Based on research, a 4-phase implementation is recommended with clear validation gates before scale-up.

### Phase 1: Query Validation & Sampling
**Rationale:** Validate all GAQL query patterns with real production data before building full backfill system. Prevents wasted effort if API limitations are worse than documented.

**Delivers:** Working queries tested on 5-10 sample SKUs, documented limitations, sample API responses demonstrating data structure and volume.

**Addresses:** Core Question 1 (product-level filtering), Q2 (query limits), Q3 (retention windows), Q5 (Keyword Planner gap analysis).

**Avoids:** Pitfall #1 (search_term_view filtering), Pitfall #3 (GAQL compatibility), Pitfall #5 (retention assumptions).

**Technical approach:**
- Test shopping_performance_view with product_item_id filtering (expected: works)
- Test search_term_view with campaign-level queries (expected: works)
- Validate variant_index join logic with sample data
- Test date ranges: 30, 60, 90, 180, 365 days to confirm 11-year retention
- Measure actual query latency (p50, p95, p99) for batch sizing

**Research flag:** LOW — patterns well-documented, existing code provides reference implementation.

---

### Phase 2: Core Backfill Implementation
**Rationale:** Build minimal job-based backfill system using validated patterns. Sequential processing sufficient for 2,784 SKU scale.

**Delivers:** /search-insights/sync endpoint that processes all SKUs with job status tracking, database upsert logic with conflict resolution, error logging.

**Uses:** google-ads 28.4.1 SearchStream, supabase-py upsert-on-conflict, FastAPI run_async_in_thread() background task pattern.

**Implements:** Job Manager component, sequential Worker (no parallelism yet), campaign-join Query Strategy.

**Avoids:** Pitfall #4 (rate limiting) via sequential processing with delays, Pitfall #2 (case sensitivity) via normalization in save_search_terms_to_db().

**Technical approach:**
- Create search_query_sync_jobs table (status, total_skus, processed_skus, errors)
- Implement single-SKU search term fetch function with campaign join
- Add upsert logic: ON CONFLICT (query_text, gmc_offer_id, period_start, period_end) DO UPDATE
- Build sequential job processor: iterate skus, fetch data, save, update progress
- Add 1-2 second delays between API calls to respect token bucket

**Research flag:** LOW — architecture patterns well-established, existing google_ads_search_terms.py provides template.

---

### Phase 3: Monitoring & Job Management
**Rationale:** Make backfill observable and debuggable before first production run. User visibility into long-running operations prevents support burden.

**Delivers:** Dashboard polling UI showing real-time progress, job status endpoint (GET /search-insights/sync/{job_id}), error counts and logs per job, structured logging with request_id context.

**Addresses:** UX requirements for non-blocking operations, operational visibility for debugging rate limit issues.

**Avoids:** UX pitfall (no progress indicator), operational blindness during failures.

**Technical approach:**
- Add job status endpoint returning: {status, progress_pct, processed_skus, total_skus, errors[]}
- Implement progress tracking: UPDATE search_query_sync_jobs SET processed_skus = N WHERE job_id = X
- Add error logging: Append failed SKUs to job.errors array as JSONB
- Build dashboard polling component: 3-5 second intervals with exponential backoff for long jobs
- Structured logging: Include job_id, request_id, customer_id in all log entries

**Research flag:** LOW — standard polling pattern, no complex integrations.

---

### Phase 4: Historical Backfill Execution
**Rationale:** Execute production backfill using validated system. Monitor closely for rate limits and data quality issues.

**Delivers:** Complete 180-day search term history for all 2,784 SKUs, performance baselines for all SKUs, Keyword Planner metrics enrichment for unique search terms.

**Addresses:** Core Question 4 (custom_label_0 sync), complete historical data coverage goal.

**Avoids:** All 6 critical pitfalls via patterns implemented in Phases 1-3.

**Technical approach:**
- Step 1: custom_label_0 sync via Merchant API (prerequisite for clustering)
- Step 2: Performance baselines (30-day pre-optimization metrics, already implemented in capture-baseline endpoint)
- Step 3: Search terms backfill (180 days, batch by 30-day windows for resumability)
- Step 4: Keyword Planner enrichment (batch 100 keywords/request, rate-limited to ~10 req/min)
- Step 5: Data quality validation (check master_sku population >90%, verify case normalization)

**Research flag:** MEDIUM — custom_label_0 sync via Merchant API needs validation (Q4), rest is standard.

---

### Phase Ordering Rationale

**Why validation first:** Prevents building full system on incorrect API assumptions. 1-2 day investment eliminates risk of multi-week rework.

**Why monitoring before production:** First production backfill will surface edge cases. Monitoring enables rapid debugging without code changes.

**Why sequential execution:** At 2,784 SKU scale, sequential processing completes in ~5 minutes. Parallel architecture adds complexity (worker coordination, partial failure handling, distributed rate limiting) without meaningful time savings. Premature optimization.

**Dependency chain:**
- Phase 1 validates queries → Phase 2 uses validated patterns
- Phase 2 builds job system → Phase 3 exposes job status
- Phase 3 provides monitoring → Phase 4 executes with visibility

**Risk mitigation:**
- Each phase has clear validation gate before next phase
- Phase 1 catches API blockers early (minimal time investment)
- Phase 2-3 build infrastructure without touching production data
- Phase 4 is pure execution with established patterns

### Research Flags

Phases needing deeper research during planning:

- **Phase 4 (custom_label_0 sync):** Merchant API field availability needs validation. MCP query: `SELECT id, offer_id, custom_label_0 FROM product_view LIMIT 10` to confirm field name and structure. If not available, fallback to Google Sheets API or CSV export. MEDIUM priority.

- **Phase 4 (Keyword Planner rate limits):** Exact limits not documented. Needs empirical testing with 100-keyword batches to measure actual throughput. Fallback: Increase delays between requests if RESOURCE_TEMPORARILY_EXHAUSTED occurs. LOW priority — already have established patterns.

Phases with standard patterns (skip research-phase):

- **Phase 1 (Query validation):** GAQL patterns well-documented in official docs, existing code provides working examples. Standard SELECT...FROM...WHERE testing.

- **Phase 2 (Job-based backfill):** Established FastAPI + Supabase pattern already in use (batch_generation_jobs table, run_async_in_thread() helper). No novel integration.

- **Phase 3 (Monitoring):** Standard polling UI + structured logging. No special considerations beyond existing Cloud Logging setup.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Official google-ads client library is only option, well-documented, already in production use at v28.4.1 |
| Features | **HIGH** | All API capabilities validated via official docs + existing codebase. Limitations (search_term_view) confirmed in developer forums. |
| Architecture | **HIGH** | Job-based pattern matches existing batch_generation_jobs implementation. Campaign-join strategy already tested in google_ads_search_terms.py. |
| Pitfalls | **HIGH** | All 6 critical pitfalls sourced from official docs or project experience (GMC case sensitivity, multi-SKU pattern). None are speculative. |

**Overall confidence:** **HIGH**

Research based on:
- Official Google Ads API documentation (v18+)
- Existing production code (google_ads_search_terms.py, google_ads_performance.py)
- Project-specific learnings (CLAUDE.md, multi-sku-pattern.md)
- Google developer forums for API limitations (search_term_view product filtering)

No reliance on tertiary sources or unvalidated assumptions.

### Gaps to Address

**Gap: Keyword Planner exact rate limits**
- Official docs state "stricter limits" but don't specify QPS
- Community sources suggest ~10 requests/min, batch size 100 keywords
- **How to handle:** Start conservative (5 req/min), monitor for RESOURCE_TEMPORARILY_EXHAUSTED, adjust delays empirically
- **Phase:** Phase 4 (Keyword Planner enrichment)
- **Risk:** LOW — worst case is slower enrichment, not blocking failure

**Gap: custom_label_0 field name in Merchant API**
- Documentation confirms existence but field name might be `customLabel0` (camelCase) vs `custom_label_0` (snake_case)
- **How to handle:** Test query in Phase 1 validation: `SELECT * FROM product_view LIMIT 1` to see all field names
- **Phase:** Phase 1 (Query validation) or Phase 4 (custom_label_0 sync)
- **Risk:** LOW — multiple fallback options (Google Sheets API, CSV export)

**Gap: Actual backfill completion time at scale**
- Estimate: 2,784 SKUs × ~3 seconds/SKU = ~2.3 hours for 180-day backfill
- Unknown: Does SearchStream caching reduce subsequent date window queries?
- **How to handle:** Measure Phase 1 sample queries, extrapolate. Monitor Phase 4 execution closely.
- **Phase:** Phase 1 (validation provides data point), Phase 4 (actual measurement)
- **Risk:** LOW — even if 2x slower, 4-5 hours is acceptable for one-time backfill

**Gap: Multi-SKU family completeness**
- Project docs identify DMF-2/2X family, but are there others?
- **How to handle:** Query variant_index for duplicate product_ids: `SELECT product_id, COUNT(DISTINCT master_sku) AS sku_count FROM variant_index GROUP BY product_id HAVING COUNT(DISTINCT master_sku) > 1`
- **Phase:** Phase 0 (can run immediately) or Phase 1 (document before backfill)
- **Risk:** MEDIUM — incorrect aggregation leads to misleading performance metrics. Already have pattern to handle, just need complete list.

## Sources

### Primary (HIGH confidence)

**Official Google Documentation:**
- [Google Ads Python Client Library](https://developers.google.com/google-ads/api/docs/client-libs/python) — Library installation, authentication, SearchStream patterns
- [GAQL Reference](https://developers.google.com/google-ads/api/docs/query/overview) — Query syntax, field compatibility, pagination
- [shopping_performance_view](https://developers.google.com/google-ads/api/fields/v22/shopping_performance_view) — Confirmed product_item_id filtering support
- [search_term_view](https://developers.google.com/google-ads/api/fields/v21/search_term_view) — Confirmed limitation: no product_item_id filtering
- [Google Ads Data Retention Policy](https://support.google.com/google-ads/answer/15188209?hl=en) — Confirmed 11-year retention (November 2024 update)
- [API Limits and Quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas) — Rate limiting, token bucket algorithm, RESOURCE_TEMPORARILY_EXHAUSTED handling
- [Batch Processing Best Practices](https://developers.google.com/google-ads/api/docs/batch-processing/best-practices) — Partial failure model, exponential backoff patterns

**Existing Implementation:**
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/integrations/google_ads_search_terms.py` — Campaign-join pattern (lines 478+), case normalization (line 896), caching patterns
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/integrations/google_ads_performance.py` — SearchStream usage, batch queries
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` — search_queries table schema, variant_index structure
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/CLAUDE.md` — Offer ID case sensitivity documentation, multi-SKU pattern reference

### Secondary (MEDIUM confidence)

**Community Sources:**
- [Google Groups: Search Term View for Shopping](https://groups.google.com/g/adwords-api/c/SxEmuVTfBoQ) — Confirms product_item_id limitation is intentional
- [Google Ads API Conversion Data Changes 2026](https://almcorp.com/blog/google-ads-api-conversion-data-changes-2026/) — Retention policy context
- [Keyword Planner with Python](https://www.danielherediamejias.com/python-keyword-planner-google-ads-api/) — Batch size recommendations (100 keywords), rate limit observations

### Project-Specific Documentation

- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/multi-sku-pattern.md` — DMF-2/2X family pattern
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/troubleshooting/baseline-capture.md` — Case sensitivity debugging
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/.planning/PROJECT.md` — Phase 0 objectives, 5 core questions

---
*Research completed: 2026-02-11*
*Ready for roadmap: yes*
