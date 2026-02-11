# Requirements: Phase 0 - Google Ads API Discovery

**Defined:** 2026-02-11
**Core Value:** Answer critical questions about Google Ads API capabilities and comprehensively map available data to validate backfill assumptions before planning Phases 1-5.

## v1 Requirements

Requirements for Phase 0 investigation. Each maps to discovery activities.

### API Validation

- [ ] **API-01**: Confirm search_term_view cannot filter by product_item_id through test query
- [ ] **API-02**: Validate shopping_performance_view supports product-level queries with working GAQL example
- [ ] **API-03**: Test query result limits with 10K, 50K, and 100K LIMIT values to find ceiling
- [ ] **API-04**: Validate 11-year data retention by querying dates from 2015-2026
- [ ] **API-05**: Confirm custom_label_0 field exists in Merchant API product_view with test query

### Data Discovery

- [ ] **DISC-01**: Enumerate all available views/resources (search_term_view, shopping_performance_view, product_view, campaign_view, etc.)
- [ ] **DISC-02**: Document all performance metrics available (clicks, impressions, CTR, conversions, cost, CPC, conversion_value, ROAS, etc.)
- [ ] **DISC-03**: Explore custom label filtering capabilities - can we filter search terms by custom_label_0 through custom_label_4?
- [ ] **DISC-04**: Investigate if we can populate custom labels with product_item_id for easier filtering
- [ ] **DISC-05**: Identify Performance Max campaign data availability and query patterns
- [ ] **DISC-06**: Map all Shopping campaign report types and their use cases
- [ ] **DISC-07**: Document bidding data (bid amounts, bid strategies, auction insights)
- [ ] **DISC-08**: Explore attribution data (conversion paths, assisted conversions, attribution models)
- [ ] **DISC-09**: Investigate competitive metrics (auction insights, impression share, outranking share)
- [ ] **DISC-10**: Document asset-level performance (if available for Shopping ads)
- [ ] **DISC-11**: Explore audience segmentation data (demographics, location, device, time-of-day)
- [ ] **DISC-12**: Identify any machine learning insights or recommendations API provides

### Sample Testing

- [ ] **SAMP-01**: Select 5-10 test SKUs across product categories (towel bars, grab bars, mirrors, shelves, hardware)
- [ ] **SAMP-02**: Fetch current Google Ads search terms for sample SKUs via campaign-join pattern
- [ ] **SAMP-03**: Generate Keyword Planner ideas for sample SKUs using product titles as seed
- [ ] **SAMP-04**: Calculate opportunity gap (high-volume KP terms not in Google Ads data)
- [ ] **SAMP-05**: Measure query performance (p50, p95, p99 response times)
- [ ] **SAMP-06**: Test comprehensive data retrieval for sample SKUs (all metrics from DISC-02)

### Documentation

- [ ] **DOC-01**: Create docs/google-ads-api-capabilities.md with comprehensive API field reference
- [ ] **DOC-02**: Document working GAQL query examples for all valuable data types
- [ ] **DOC-03**: Include sample API responses (20-30 examples across different views)
- [ ] **DOC-04**: Create data value assessment - which metrics are most useful for content optimization?
- [ ] **DOC-05**: Document alternative strategies for any failed assumptions
- [ ] **DOC-06**: Provide Go/No-Go recommendation for Phases 1-5 with expanded data collection scope

## v2 Requirements

Deferred exploration - valuable but not blocking Phase 0 completion.

### Advanced Features

- **ADV-01**: BigQuery Data Transfer Service integration patterns (for 2+ year backfills at scale)
- **ADV-02**: Real-time bid adjustment API capabilities
- **ADV-03**: Smart Shopping campaign optimization signals
- **ADV-04**: Google Analytics 4 integration for conversion tracking
- **ADV-05**: Automated rules and scripts capabilities

## Out of Scope

Explicitly excluded from Phase 0 to maintain focus on discovery.

| Feature | Reason |
|---------|--------|
| Actual backfill implementation | Phase 0 is pure research - implementation happens in Phases 1-5 |
| Full 2,784 SKU data collection | Sample testing only (5-10 SKUs) - validates approach before scale |
| Schema migrations | No database changes until we know what data to collect |
| Dashboard UI | Visualization comes after we have data to display |
| Production deployment | Investigation phase - no production changes |
| Performance optimization | Premature - optimize after we validate what to build |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | Phase 1 | Pending |
| API-02 | Phase 1 | Pending |
| API-03 | Phase 1 | Pending |
| API-04 | Phase 1 | Pending |
| API-05 | Phase 1 | Pending |
| DISC-01 | Phase 2 | Pending |
| DISC-02 | Phase 2 | Pending |
| DISC-03 | Phase 2 | Pending |
| DISC-04 | Phase 2 | Pending |
| DISC-05 | Phase 2 | Pending |
| DISC-06 | Phase 2 | Pending |
| DISC-07 | Phase 2 | Pending |
| DISC-08 | Phase 2 | Pending |
| DISC-09 | Phase 2 | Pending |
| DISC-10 | Phase 2 | Pending |
| DISC-11 | Phase 2 | Pending |
| DISC-12 | Phase 2 | Pending |
| SAMP-01 | Phase 3 | Pending |
| SAMP-02 | Phase 3 | Pending |
| SAMP-03 | Phase 3 | Pending |
| SAMP-04 | Phase 3 | Pending |
| SAMP-05 | Phase 3 | Pending |
| SAMP-06 | Phase 3 | Pending |
| DOC-01 | Phase 4 | Pending |
| DOC-02 | Phase 4 | Pending |
| DOC-03 | Phase 4 | Pending |
| DOC-04 | Phase 4 | Pending |
| DOC-05 | Phase 4 | Pending |
| DOC-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29 (100% coverage)
- Unmapped: 0

---
*Requirements defined: 2026-02-11*
*Last updated: 2026-02-11 after roadmap creation*
