# Roadmap: Phase 0 - Google Ads API Discovery

## Overview

This is a pure research project to validate Google Ads API capabilities before executing a comprehensive backfill plan. We'll answer 5 core questions about API constraints, map all available data sources, test with sample SKUs, and document findings to inform the full backfill strategy (Phases 1-5). Success means we have enough information to confidently plan the main backfill OR pivot to a different approach if critical assumptions are wrong.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: API Capability Validation** - Test core API assumptions and establish working query patterns
- [x] **Phase 2: Comprehensive Data Discovery** - Map all available views, metrics, and filtering capabilities
- [x] **Phase 3: Sample Testing & Analysis** - Validate approach with 5-10 real SKUs across categories
- [x] **Phase 4: Documentation & Decision** - Create comprehensive API reference and provide Go/No-Go recommendation

## Phase Details

### Phase 1: API Capability Validation
**Goal**: Confirm Google Ads API can support product-level backfill strategy with validated query patterns and documented constraints
**Depends on**: Nothing (first phase)
**Requirements**: API-01, API-02, API-03, API-04, API-05
**Success Criteria** (what must be TRUE):
  1. We know whether search_term_view supports product_item_id filtering (expected: no)
  2. We have working GAQL query for shopping_performance_view with product-level filtering
  3. We know the maximum LIMIT value that works reliably (tested 10K, 50K, 100K)
  4. We know actual data retention windows for both search terms and performance views
  5. We have confirmed custom_label_0 field availability in Merchant API product_view
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Validate core views (API-01: search_term_view limitation, API-02: shopping_performance_view product queries)
- [x] 01-02-PLAN.md — Test query boundaries and custom labels (API-03: LIMIT values, API-04: data retention, API-05: custom_label_0)

### Phase 2: Comprehensive Data Discovery
**Goal**: Complete inventory of all available Google Ads API data sources with documented fields, filtering capabilities, and use cases
**Depends on**: Phase 1
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04, DISC-05, DISC-06, DISC-07, DISC-08, DISC-09, DISC-10, DISC-11, DISC-12
**Success Criteria** (what must be TRUE):
  1. All available views and resources are enumerated with field listings (search_term_view, shopping_performance_view, product_view, campaign_view, etc.)
  2. All performance metrics are documented with data types and availability (clicks, impressions, conversions, ROAS, etc.)
  3. Custom label filtering capabilities are tested and documented (can we filter by custom_label_0-4?)
  4. Performance Max campaign data patterns are documented
  5. Competitive metrics availability is confirmed (auction insights, impression share, etc.)
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — Enumerate all views, metrics, and Shopping report types (DISC-01, DISC-02, DISC-06)
- [x] 02-02-PLAN.md — Test custom label filtering and PMax data patterns (DISC-03, DISC-04, DISC-05)
- [x] 02-03-PLAN.md — Discover bidding, attribution, and competitive metrics (DISC-07, DISC-08, DISC-09)
- [x] 02-04-PLAN.md — Discover audience segmentation, asset performance, and ML insights (DISC-10, DISC-11, DISC-12)

### Phase 3: Sample Testing & Analysis
**Goal**: Validated backfill approach with real API responses from diverse product categories showing performance, opportunity gaps, and query execution characteristics
**Depends on**: Phase 2
**Requirements**: SAMP-01, SAMP-02, SAMP-03, SAMP-04, SAMP-05, SAMP-06
**Success Criteria** (what must be TRUE):
  1. 5-10 test SKUs are selected across product categories (towel bars, grab bars, mirrors, shelves, hardware)
  2. Current Google Ads search terms are fetched for all sample SKUs using validated query patterns
  3. Keyword Planner ideas are generated for sample SKUs with documented opportunity gaps
  4. Query performance is measured (p50, p95, p99 response times) for batch sizing decisions
  5. Comprehensive data retrieval works for sample SKUs (all metrics identified in Phase 2)
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Select test SKUs across categories and fetch search terms (SAMP-01, SAMP-02)
- [x] 03-02-PLAN.md — Generate Keyword Planner ideas and calculate opportunity gaps (SAMP-03, SAMP-04)
- [x] 03-03-PLAN.md — Measure query performance and validate comprehensive metric retrieval (SAMP-05, SAMP-06)

### Phase 4: Documentation & Decision
**Goal**: Comprehensive API reference document and clear Go/No-Go recommendation for Phases 1-5 backfill execution
**Depends on**: Phase 3
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06
**Success Criteria** (what must be TRUE):
  1. `docs/google-ads-api-capabilities.md` exists with complete field reference for all views
  2. Document includes 20-30 sample API responses showing real data structures
  3. Working GAQL query examples are provided for all valuable data types
  4. Data value assessment identifies which metrics are most useful for content optimization
  5. Alternative strategies are documented for any failed assumptions
  6. Clear Go/No-Go recommendation exists for proceeding with Phases 1-5
**Plans**: 2 plans

Plans:
- [x] 04-01-PLAN.md — Comprehensive API reference with field tables, working GAQL queries, and 20-30 sample responses (DOC-01, DOC-02, DOC-03)
- [x] 04-02-PLAN.md — Data value assessment, alternative strategies, and Go/No-Go recommendation (DOC-04, DOC-05, DOC-06)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. API Capability Validation | 2/2 | ✓ Complete | 2026-02-12 |
| 2. Comprehensive Data Discovery | 4/4 | ✓ Complete | 2026-02-12 |
| 3. Sample Testing & Analysis | 3/3 | ✓ Complete | 2026-02-13 |
| 4. Documentation & Decision | 2/2 | ✓ Complete | 2026-02-13 |

---
*Roadmap created: 2026-02-11*
*Last updated: 2026-02-13 (Phase 4 complete - milestone complete)*
