# Roadmap: Allied FeedOps v1.0

## Milestones

- ✅ **Phase 0 Discovery** - API validation and research (shipped 2026-02-13)
- 🚧 **v1.0 Historical Data Backfill** - Phases 1-4 (in planning)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ Phase 0 Discovery - SHIPPED 2026-02-13</summary>

### Phase 0.1: API Capability Validation
**Goal**: Confirm Google Ads API can support product-level backfill strategy with validated query patterns and documented constraints
**Requirements**: API-01, API-02, API-03, API-04, API-05
**Plans**: 2 plans

Plans:
- [x] 00.1-01-PLAN.md — Validate core views (API-01: search_term_view limitation, API-02: shopping_performance_view product queries)
- [x] 00.1-02-PLAN.md — Test query boundaries and custom labels (API-03: LIMIT values, API-04: data retention, API-05: custom_label_0)

### Phase 0.2: Comprehensive Data Discovery
**Goal**: Complete inventory of all available Google Ads API data sources with documented fields, filtering capabilities, and use cases
**Requirements**: DISC-01 through DISC-12
**Plans**: 4 plans

Plans:
- [x] 00.2-01-PLAN.md — Enumerate all views, metrics, and Shopping report types
- [x] 00.2-02-PLAN.md — Test custom label filtering and PMax data patterns
- [x] 00.2-03-PLAN.md — Discover bidding, attribution, and competitive metrics
- [x] 00.2-04-PLAN.md — Discover audience segmentation, asset performance, and ML insights

### Phase 0.3: Sample Testing & Analysis
**Goal**: Validated backfill approach with real API responses from diverse product categories
**Requirements**: SAMP-01 through SAMP-06
**Plans**: 3 plans

Plans:
- [x] 00.3-01-PLAN.md — Select test SKUs across categories and fetch search terms
- [x] 00.3-02-PLAN.md — Generate Keyword Planner ideas and calculate opportunity gaps
- [x] 00.3-03-PLAN.md — Measure query performance and validate comprehensive metric retrieval

### Phase 0.4: Documentation & Decision
**Goal**: Comprehensive API reference document and clear Go/No-Go recommendation
**Requirements**: DOC-01 through DOC-06
**Plans**: 2 plans

Plans:
- [x] 00.4-01-PLAN.md — Comprehensive API reference with field tables and working GAQL queries
- [x] 00.4-02-PLAN.md — Data value assessment and Go/No-Go recommendation

</details>

## v1.0 Historical Data Backfill (In Planning)

**Milestone Goal:** Execute comprehensive Google Ads historical data backfill for all 2,784 SKUs with production-ready monitoring and validation.

### Phase 1: Job Infrastructure & Foundation
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

### Phase 2: Data Collection Pipeline
**Goal**: Implement all data collection endpoints using campaign-join pattern for search terms and direct queries for performance metrics

**Depends on**: Phase 1

**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-09, DATA-10

**Success Criteria** (what must be TRUE):
  1. System collects search terms for all 2,784 SKUs using 2-step campaign-join pattern
  2. System captures 180 days of performance metrics (impressions, clicks, CTR, conversions) per SKU
  3. System generates Keyword Planner ideas for all SKUs and stores with 30-day TTL
  4. System syncs custom_label_0 from Google Merchant Center to Supabase
  5. All collected data includes collection timestamps and uses explicit date ranges (YYYY-MM-DD format)

**Plans**: TBD

Plans:
- [ ] 02-01: TBD during phase planning

### Phase 3: Data Quality & Validation
**Goal**: Ensure data completeness, freshness, and accuracy through validation layers and contamination prevention

**Depends on**: Phase 2

**Requirements**: VALID-01, VALID-02, VALID-03, VALID-04, VALID-05, VALID-06, VALID-07, VALID-08, VALID-09, VALID-10

**Success Criteria** (what must be TRUE):
  1. System validates 100% requirement coverage (all 2,784 SKUs accounted for) after each batch job
  2. System detects and flags stale data (baselines >60 days, search terms >7 days) in dashboard
  3. System identifies multi-SKU families via product_id matching and marks aggregated data with badges
  4. System prevents baseline capture for SKUs published in last 30 days by checking publish_events
  5. System validates data ranges (CTR 0-1, clicks <= impressions) and sets job status to 'partial' if success rate <95%

**Plans**: TBD

Plans:
- [ ] 03-01: TBD during phase planning

### Phase 4: Monitoring & Automation
**Goal**: Enable production observability with dashboards, alerting, and automated incremental refresh for ongoing data sync

**Depends on**: Phase 3

**Requirements**: MON-01, MON-02, MON-03, MON-04, MON-05, MON-06, MON-07, MON-08, MON-09, MON-10

**Success Criteria** (what must be TRUE):
  1. Dashboard displays real-time job status, progress, and coverage metrics (X/2,784 SKUs with data)
  2. Dashboard shows data freshness heatmap and API health metrics (latency p95, error rates, rate limit hits)
  3. System sends email alerts on job failure and Slack notifications on completion
  4. System automatically triggers backfill for SKUs with missing or stale data via scheduled jobs
  5. System transitions from 180-day backfill to daily 1-day incremental refresh with Prometheus metrics exported

**Plans**: TBD

Plans:
- [ ] 04-01: TBD during phase planning

## Progress

**Execution Order:**
Phases execute in numeric order: 0.1 → 0.2 → 0.3 → 0.4 → 1 → 2 → 3 → 4

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 0.1 API Capability Validation | Phase 0 | 2/2 | Complete | 2026-02-12 |
| 0.2 Comprehensive Data Discovery | Phase 0 | 4/4 | Complete | 2026-02-12 |
| 0.3 Sample Testing & Analysis | Phase 0 | 3/3 | Complete | 2026-02-13 |
| 0.4 Documentation & Decision | Phase 0 | 2/2 | Complete | 2026-02-13 |
| 1. Job Infrastructure & Foundation | v1.0 | 4/4 | Complete | 2026-02-13 |
| 2. Data Collection Pipeline | v1.0 | 0/? | Not started | - |
| 3. Data Quality & Validation | v1.0 | 0/? | Not started | - |
| 4. Monitoring & Automation | v1.0 | 0/? | Not started | - |

---
*Phase 0 completed: 2026-02-13*
*v1.0 milestone initialized: 2026-02-13*
