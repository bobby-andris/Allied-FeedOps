# Roadmap: Allied FeedOps

## Milestones

- ✅ **Phase 0 Discovery** - API validation and research (shipped 2026-02-13)
- ✅ **v1.0 Historical Data Backfill** - Phases 05-08 (shipped 2026-02-13)
- **v1.1 Dashboard UX & Quality** - Phases 9-12 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, ...): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ Phase 0 Discovery - SHIPPED 2026-02-13</summary>

### Phase 01: API Capability Validation
**Goal**: Confirm Google Ads API can support product-level backfill strategy with validated query patterns and documented constraints
**Requirements**: API-01, API-02, API-03, API-04, API-05
**Plans**: 2 plans

Plans:
- [x] 00.1-01-PLAN.md — Validate core views (API-01: search_term_view limitation, API-02: shopping_performance_view product queries)
- [x] 00.1-02-PLAN.md — Test query boundaries and custom labels (API-03: LIMIT values, API-04: data retention, API-05: custom_label_0)

### Phase 02: Comprehensive Data Discovery
**Goal**: Complete inventory of all available Google Ads API data sources with documented fields, filtering capabilities, and use cases
**Requirements**: DISC-01 through DISC-12
**Plans**: 4 plans

Plans:
- [x] 00.2-01-PLAN.md — Enumerate all views, metrics, and Shopping report types
- [x] 00.2-02-PLAN.md — Test custom label filtering and PMax data patterns
- [x] 00.2-03-PLAN.md — Discover bidding, attribution, and competitive metrics
- [x] 00.2-04-PLAN.md — Discover audience segmentation, asset performance, and ML insights

### Phase 03: Sample Testing & Analysis
**Goal**: Validated backfill approach with real API responses from diverse product categories
**Requirements**: SAMP-01 through SAMP-06
**Plans**: 3 plans

Plans:
- [x] 00.3-01-PLAN.md — Select test SKUs across categories and fetch search terms
- [x] 00.3-02-PLAN.md — Generate Keyword Planner ideas and calculate opportunity gaps
- [x] 00.3-03-PLAN.md — Measure query performance and validate comprehensive metric retrieval

### Phase 04: Documentation & Decision
**Goal**: Comprehensive API reference document and clear Go/No-Go recommendation
**Requirements**: DOC-01 through DOC-06
**Plans**: 2 plans

Plans:
- [x] 00.4-01-PLAN.md — Comprehensive API reference with field tables and working GAQL queries
- [x] 00.4-02-PLAN.md — Data value assessment and Go/No-Go recommendation

</details>

<details>
<summary>✅ v1.0 Historical Data Backfill — COMPLETE 2026-02-13</summary>

**Milestone Goal:** Execute comprehensive Google Ads historical data backfill for all 2,784 SKUs with production-ready monitoring and validation.

### Phase 05: Job Infrastructure & Foundation
**Goal**: Establish robust job-based async processing infrastructure with rate limiting, error handling, and resumability

**Depends on**: Phase 0 (complete)

**Requirements**: JOB-01, JOB-02, JOB-03, JOB-04, JOB-05, JOB-06, JOB-07, JOB-08, JOB-09, JOB-10, DATA-06, DATA-07, DATA-08

**Success Criteria** (what must be TRUE):
  1. System can create batch jobs and track their status through complete lifecycle (creating, running, complete, failed, partial)
  2. System can process 100 SKUs with progress updates, error logging, and ETA calculation
  3. System recovers from interruptions by resuming jobs from last checkpoint without data duplication
  4. System respects API rate limits using token bucket limiting (10 QPS max) and exponential backoff
  5. Database connections remain stable with no exhaustion when running 3 concurrent jobs

**Plans**: 4 plans

Plans:
- [x] 05-01-PLAN.md — Database schema (backfill_jobs, backfill_job_errors) + Python models and job manager
- [x] 05-02-PLAN.md — Token bucket rate limiter + generic batch processor with checkpointing
- [x] 05-03-PLAN.md — FastAPI backfill endpoints (start, status, resume, list) with concurrent job limiting
- [x] 05-04-PLAN.md — Test suite for rate limiter, job manager, and batch processor

### Phase 06: Data Collection Pipeline
**Goal**: Implement all data collection endpoints using campaign-join pattern for search terms and direct queries for performance metrics

**Depends on**: Phase 1

**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-09, DATA-10

**Success Criteria** (what must be TRUE):
  1. System collects search terms for all 2,784 SKUs using 2-step campaign-join pattern
  2. System captures 180 days of performance metrics (impressions, clicks, CTR, conversions) per SKU
  3. System generates Keyword Planner ideas for all SKUs and stores with 30-day TTL
  4. System syncs custom_label_0 from Google Merchant Center to Supabase
  5. All collected data includes collection timestamps and uses explicit date ranges (YYYY-MM-DD format)

**Plans**: 3 plans

Plans:
- [x] 06-01-PLAN.md -- Collection worker functions (search terms, performance, keyword planner, custom labels)
- [x] 06-02-PLAN.md -- Wire workers into backfill API endpoints (replace _noop_process with job-type routing)
- [x] 06-03-PLAN.md -- Unit tests for all 4 collection workers

### Phase 07: Data Quality & Validation
**Goal**: Ensure data completeness, freshness, and accuracy through validation layers and contamination prevention

**Depends on**: Phase 2

**Requirements**: VALID-01, VALID-02, VALID-03, VALID-04, VALID-05, VALID-06, VALID-07, VALID-08, VALID-09, VALID-10

**Success Criteria** (what must be TRUE):
  1. System validates 100% requirement coverage (all 2,784 SKUs accounted for) after each batch job
  2. System detects and flags stale data (baselines >60 days, search terms >7 days) in dashboard
  3. System identifies multi-SKU families via product_id matching and marks aggregated data with badges
  4. System prevents baseline capture for SKUs published in last 30 days by checking publish_events
  5. System validates data ranges (CTR 0-1, clicks <= impressions) and sets job status to 'partial' if success rate <95%

**Plans**: 4 plans

Plans:
- [x] 07-01-PLAN.md -- Pydantic validation models + worker integration (VALID-05, VALID-06)
- [x] 07-02-PLAN.md -- Multi-SKU family detection + publish contamination prevention + metadata column (VALID-03, VALID-04, VALID-08, VALID-09)
- [x] 07-03-PLAN.md -- Quality report module: completeness, freshness, outlier detection (VALID-01, VALID-02, VALID-07, VALID-10)
- [x] 07-04-PLAN.md -- API endpoint + job status correction wiring (VALID-07 enforcement)

### Phase 08: Monitoring & Automation
**Goal**: Enable production observability with dashboards, alerting, and automated incremental refresh for ongoing data sync

**Depends on**: Phase 3

**Requirements**: MON-01, MON-02, MON-03, MON-04, MON-05, MON-06, MON-07, MON-08, MON-09, MON-10

**Success Criteria** (what must be TRUE):
  1. Dashboard displays real-time job status, progress, and coverage metrics (X/2,784 SKUs with data)
  2. Dashboard shows data freshness heatmap and API health metrics (latency p95, error rates, rate limit hits)
  3. System sends email alerts on job failure and Slack notifications on completion
  4. System automatically triggers backfill for SKUs with missing or stale data via scheduled jobs
  5. System transitions from 180-day backfill to daily 1-day incremental refresh with Prometheus metrics exported

**Plans**: 5 plans

Plans:
- [x] 08-01-PLAN.md — Python monitoring API endpoints (freshness, coverage, api-health) + Prometheus /metrics mount
- [x] 08-02-PLAN.md — Stale SKU detection, incremental refresh logic, and Slack/email alert helpers
- [x] 08-03-PLAN.md — Dashboard backfill monitoring page with Tremor (job status, coverage KPIs, freshness heatmap, API health)
- [x] 08-04-PLAN.md — Cloud Scheduler setup for daily incremental refresh + notification channel configuration
- [x] 08-05-PLAN.md — Gap closure: Fix monitoring endpoints 500 errors (replace execute_sql RPC with direct table queries)

</details>

## v1.1 Dashboard UX & Quality — IN PROGRESS

**Milestone Goal:** Revamp the dashboard to make the core review, image, and performance workflows fast, clear, and actually useful — with a full audit pass to fix broken pages and eliminate dead-end experiences.

**Visual verification note:** VER-01 applies to all phases in this milestone. Every UI change must be inspected using agent-browser before being marked complete.

### Phase 9: SKU Review Revamp
**Goal**: Users can review SKU approval status across platforms in a compact list with filtering, eliminating per-SKU vertical scrolling

**Depends on**: Phase 08 (v1.0 complete)

**Requirements**: SKUR-01, SKUR-02, SKUR-03, SKUR-04, SKUR-05, VER-01

**Success Criteria** (what must be TRUE):
  1. User sees a stats summary bar at the top of the SKU review page showing counts by status (approved, pending, not started) broken out per platform (Google / Bing)
  2. User can scan all SKUs at a glance in a compact list — per-platform status badges visible per row without vertical scrolling per SKU
  3. User can filter the list by status (needs review, approved, all) and by platform, and the list updates immediately
  4. User can click a SKU row to expand full detail inline while retaining list context (no full-page navigation away)
  5. All three SkuReviewClient variants (main, magazine, original) render correctly and all UI changes verified via agent-browser in the live dashboard

**Plans**: 3 plans

Plans:
- [ ] 09-01-PLAN.md — Compact list rows with per-platform status badges + ReviewListClient component
- [ ] 09-02-PLAN.md — Stats summary bar + filter controls wired to URL state
- [ ] 09-03-PLAN.md — Inline expand/collapse row preview + browser verification

### Phase 10: Image Workflow Improvements
**Goal**: Users control which variant is used for lifestyle image generation, and can see which variants are missing images

**Depends on**: Phase 9

**Requirements**: IMG-01, IMG-02, IMG-03, IMG-04, VER-01

**Success Criteria** (what must be TRUE):
  1. User can manually select a specific finish/variant before triggering lifestyle image generation for a SKU
  2. When no variant is manually selected, the system auto-selects the Google Ads variant with the highest impression count (not a hardcoded heuristic)
  3. User can see a per-variant coverage view for a SKU — which Google Ads variants have a lifestyle image and which do not
  4. Image generation uses the user's selected variant and does not override it with auto-selection logic after the user has chosen
  5. Image generation UI changes verified via agent-browser — manual selection, auto-selection fallback, and coverage view all work end-to-end in the live dashboard

**Plans**: 3 plans

Plans:
- [ ] 10-01-PLAN.md — GET /api/images/variant-data endpoint: per-finish impression totals + lifestyle image coverage
- [ ] 10-02-PLAN.md — Variant selector modal + auto-select label + generate integration (selected_finish_code to Cloud Run)
- [ ] 10-03-PLAN.md — Coverage tab in LifestyleImageReview + browser verification of complete workflow

### Phase 11: Performance Page Enhancements
**Goal**: Users can clearly see how published SKUs are performing relative to their pre-publish baseline, with trend direction at a glance

**Depends on**: Phase 10

**Requirements**: PERF-01, PERF-02, PERF-03, VER-01

**Success Criteria** (what must be TRUE):
  1. Performance page shows a side-by-side or delta comparison of baseline vs. latest snapshot metrics (CTR, impressions, clicks, CVR) for each published SKU
  2. Each published SKU row shows days-since-publish alongside the metric deltas so the user can contextualize improvement timelines
  3. Page visually distinguishes SKUs trending up vs. down since publish (e.g., color coding, icons) without requiring manual calculation
  4. Performance changes verified via agent-browser against the 44 real snapshots for 36 published SKUs — comparisons reflect actual data

**Plans**: 3 plans

Plans:
- [ ] 11-01-PLAN.md — Enhanced API (dual time windows, daysSincePublish, snapshot-only data source) + rewritten page (delta table, dual selectors, filter toggle, sortable columns, trend indicators)
- [ ] 11-02-PLAN.md — Inline SKU detail expansion (variant breakdown + search terms) + browser verification of all phase success criteria
- [ ] 11-03-PLAN.md — Gap closure: fix baseline divisor, snapshot window filter, SKU detail query via offer ID join, search term sync case fix, baseline re-capture

### Phase 12: Dashboard Audit & Cleanup
**Goal**: Every dashboard page either shows useful current data or provides a clear next action — no dead ends, no stale broken states

**Depends on**: Phase 11

**Requirements**: DASH-01, DASH-02, DASH-03, VER-01

**Success Criteria** (what must be TRUE):
  1. Each dashboard page has been reviewed: pages showing useful current data are confirmed working, pages with stale or broken data are identified with a fix applied or a deferral noted
  2. Pages or features that do not serve the current workflow are simplified, removed, or replaced with a clear redirect to something useful
  3. No page in the dashboard results in an empty state with no path forward — every dead-end state has an action or informative message
  4. Audit findings and changes verified via agent-browser walkthrough of all dashboard pages in the live environment

**Plans**: 3 plans

Plans:
- [ ] 12-01-PLAN.md — Audit pass: code inspection + local dev walkthrough of all 11 pages, produce 12-AUDIT.md
- [ ] 12-02-PLAN.md — Fix all FIX-status pages from audit (alert() removal, stale data, broken APIs)
- [ ] 12-03-PLAN.md — Empty state actions for DEAD-END pages + agent-browser verification on live Vercel URL

## Progress

**Execution Order:**
Phases execute in numeric order: 9 → 10 → 11 → 12 → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01. API Capability Validation | Phase 0 | 2/2 | Complete | 2026-02-12 |
| 02. Comprehensive Data Discovery | Phase 0 | 4/4 | Complete | 2026-02-12 |
| 03. Sample Testing & Analysis | Phase 0 | 3/3 | Complete | 2026-02-13 |
| 04. Documentation & Decision | Phase 0 | 2/2 | Complete | 2026-02-13 |
| 05. Job Infrastructure & Foundation | v1.0 | 4/4 | Complete | 2026-02-13 |
| 06. Data Collection Pipeline | v1.0 | 3/3 | Complete | 2026-02-13 |
| 07. Data Quality & Validation | v1.0 | 4/4 | Complete | 2026-02-13 |
| 08. Monitoring & Automation | v1.0 | 5/5 | Complete | 2026-02-13 |
| 9. SKU Review Revamp | 3/3 | Complete    | 2026-02-18 | - |
| 10. Image Workflow Improvements | 3/3 | Complete    | 2026-02-19 | - |
| 11. Performance Page Enhancements | 3/3 | Complete   | 2026-02-19 | - |
| 12. Dashboard Audit & Cleanup | 3/3 | Complete    | 2026-02-19 | - |
| 13. Fix Google Ads Data Sourcing | 3/3 | Complete    | 2026-02-19 | - |
| 14. Complete 180-day Backfill & Monitoring Fixes | 3/3 | Complete    | 2026-02-19 | - |
| 15. Google Ads Data Backfill & Monitoring Verification | 0/3 | Partial — bugs found |  | - |
| 16. Fix Google Ads Backfill Pipeline | 1/3 | In Progress|  | - |

### Phase 13: Fix Google Ads data sourcing: variant metrics from shopping_performance_view and per-campaign search terms sync

**Goal:** Fix how Google Ads data is fetched and stored — correct variant-level search term attribution (per-item instead of per-campaign-top-item) and confirm performance metrics use the right offer ID format for shopping_performance_view. Re-sync all 2,784 SKUs with corrected data.
**Depends on:** Phase 12
**Plans:** 3/3 plans executed

Plans:
- [x] 13-01-PLAN.md — Diagnosis: code trace of both bugs + empirical data comparison + 13-DIAGNOSIS.md
- [x] 13-02-PLAN.md — Fix: fetch_search_terms() variant expansion, delete-before-insert worker, synced_at migration, offer ID case fix
- [x] 13-03-PLAN.md — Deploy + re-sync all 2,784 SKUs + human verification of corrected data

### Phase 14: Complete 180-day data backfill and fix monitoring page accuracy

**Goal:** Complete the full 180-day Google Ads data sync for all 2,784 SKUs using the corrected pipeline from Phase 13, and fix the monitoring dashboard to show accurate coverage numbers and active job status.

**Depends on:** Phase 13

**Requirements:** SYNC-01, SYNC-02, MON-FIX-01, MON-FIX-02

**Success Criteria** (what must be TRUE):
  1. 026_backfill_jobs.sql migration applied to production — `backfill_jobs` and `backfill_job_errors` tables exist
  2. LAST_N_DAYS syntax bug fixed in google_ads_search_terms.py — all occurrences replaced with explicit BETWEEN date strings; 180-day sync completes without INVALID_ARGUMENT errors
  3. Performance metrics backfill runs for all 2,784 SKUs via /backfill/start and completes successfully
  4. Monitoring page shows correct coverage (COUNT queries, not PostgREST 1000-row limit) and Active Jobs reads from search_query_sync_jobs and backfill_jobs

**Plans:** 3/3 plans executed

Plans:
- [x] 14-01-PLAN.md — Apply 026_backfill_jobs.sql migration + fix LAST_N_DAYS → BETWEEN in google_ads_search_terms.py + re-trigger 180-day search terms sync
- [x] 14-02-PLAN.md — (rolled into Phase 15) Performance metrics backfill skipped — moved to Phase 15
- [x] 14-03-PLAN.md — Fix monitoring page: coverage COUNT queries + two Active Jobs sections (search_query_sync_jobs + backfill_jobs) + freshness heatmap accuracy

### Phase 15: Google Ads Data Backfill and Monitoring Verification

**Goal:** Complete the 180-day search terms backfill using safe 30-day chunked windows, run the performance metrics backfill for all 2,784 SKUs, and verify monitoring page accuracy after both syncs complete.

**Depends on:** Phase 14

**Success Criteria** (what must be TRUE):
  1. 180-day search terms backfill complete using 6 sequential 30-day windows — row count grows after each chunk; final count significantly above 7,891
  2. Performance metrics backfill runs for all 2,784 SKUs via /backfill/start with job_type=performance_metrics and completes successfully
  3. Monitoring page coverage numbers are accurate after both syncs — agent-browser confirms correct SKU counts in all coverage cards

**Plans:** 3/3 plans

Plans:
- [ ] 15-01-PLAN.md — Search terms backfill: smoke test (days=30) + full 180-day sync (days=180) with row count verification
- [ ] 15-02-PLAN.md — Performance metrics backfill for all 2,784 SKUs via /backfill/start (job_type=performance_metrics)
- [ ] 15-03-PLAN.md — Monitoring page verification via agent-browser after both syncs complete

### Phase 16: Fix Google Ads Backfill Pipeline — Search Terms + Performance Metrics

**Goal:** Fix two root-cause bugs blocking full 2,784-SKU data backfill, then run both syncs to completion and verify with monitoring page.

**Depends on:** Phase 15

**Research approach:** Use `mcp__plugin_context7_context7__query-docs` to look up correct Google Ads API GAQL patterns and query limits, and/or reference the google-ads-developer-assistant repo for working examples before writing any fixes.

**Bug 1 — Performance metrics: oversized GAQL IN() clause**
`fetch_batch_product_performance` in `google_ads_performance.py` sends all offer IDs for a batch (~250+) in a single GAQL `IN (...)` clause for a 180-day window. Google Ads API hangs indefinitely.
Fix: chunk offer IDs into groups of ≤25 per GAQL query, run sequentially per chunk, merge results.

**Bug 2 — Search terms: date-range jobs return 0 queries**
Jobs using new `start_date`/`end_date` params (enabled in Phase 15-01) hang or return empty results. The `days=30` default approach worked (10,000 queries, 424 SKUs). Root cause unknown — likely the campaign-product join in `_fetch_campaign_products` returns nothing for historical date windows.
Fix: Add diagnostic logging, test locally, identify empty-result cause, fix and verify.

**Success Criteria** (what must be TRUE):
  1. `fetch_batch_product_performance` correctly chunks offer IDs — a batch of 10 SKUs with 250 offer IDs runs in <60 seconds
  2. Search terms sync with explicit `start_date`/`end_date` returns results matching `days=N` equivalent — root cause identified and fixed
  3. Performance metrics backfill for all 2,784 SKUs completes (job reaches terminal status, success rate ≥80%)
  4. Search terms 180-day backfill using 6 × 30-day windows completes — search_queries rows >> 7,891, oldest period ~180 days ago
  5. Monitoring page coverage cards reflect post-backfill numbers (>>424 SKUs search terms, >>96 SKUs performance)

**Plans:** 1/3 plans executed

Plans:
- [ ] 16-01-PLAN.md — Fix fetch_batch_product_performance chunking + run performance backfill for 2,784 SKUs
- [ ] 16-02-PLAN.md — Debug and fix search terms date-range empty results + run 180-day chunked backfill
- [ ] 16-03-PLAN.md — Monitoring page verification via agent-browser after both backfills complete

---
*Phase 0 completed: 2026-02-13*
*v1.0 milestone completed: 2026-02-13*
*v1.1 milestone started: 2026-02-18*
