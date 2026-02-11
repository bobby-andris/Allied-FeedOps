# Roadmap: Phase 0 - Google Ads API Discovery

## Overview

This is a pure research project to validate Google Ads API capabilities before executing a comprehensive backfill plan. We'll answer 5 core questions about API constraints, map all available data sources, test with sample SKUs, and document findings to inform the full backfill strategy (Phases 1-5). Success means we have enough information to confidently plan the main backfill OR pivot to a different approach if critical assumptions are wrong.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: API Capability Validation** - Test core API assumptions and establish working query patterns
- [ ] **Phase 2: Comprehensive Data Discovery** - Map all available views, metrics, and filtering capabilities
- [ ] **Phase 3: Sample Testing & Analysis** - Validate approach with 5-10 real SKUs across categories
- [ ] **Phase 4: Documentation & Decision** - Create comprehensive API reference and provide Go/No-Go recommendation

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
**Plans**: TBD

Plans:
- Plans will be created during `/gsd:plan-phase 1`

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
**Plans**: TBD

Plans:
- Plans will be created during `/gsd:plan-phase 2`

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
**Plans**: TBD

Plans:
- Plans will be created during `/gsd:plan-phase 3`

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
**Plans**: TBD

Plans:
- Plans will be created during `/gsd:plan-phase 4`

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. API Capability Validation | 0/TBD | Not started | - |
| 2. Comprehensive Data Discovery | 0/TBD | Not started | - |
| 3. Sample Testing & Analysis | 0/TBD | Not started | - |
| 4. Documentation & Decision | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-11*
*Last updated: 2026-02-11*
