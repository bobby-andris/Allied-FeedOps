# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-11)

**Core value:** Validate Google Ads API capabilities and comprehensively map available data to inform backfill strategy before planning Phases 1-5
**Current focus:** Phase 2 - Comprehensive Data Discovery

## Current Position

Phase: 2 of 4 (Comprehensive Data Discovery)
Plan: 4 of 4 in current phase
Status: Phase complete
Last activity: 2026-02-12 — Completed plan 02-04 (Audience, Asset, and ML Insights Discovery)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 2.83 minutes
- Total execution time: 0.28 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. API Capability Validation | 2 | 9 min | 4.5 min |
| 2. Comprehensive Data Discovery | 4 | 11 min | 2.75 min |

**Recent Trend:**
- Latest: 02-04 (3 minutes)
- Previous: 02-03 (2 minutes)
- Trend: Consistent velocity (~2.75 min/plan in Phase 2)

*Updated after each plan completion*
| Phase 02 P04 | 3 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

1. **search_term_view Cannot Filter by Product** (01-01, 2026-02-11)
   - API explicitly rejects `segments.product_item_id` in search_term_view queries
   - Must use campaign-join pattern (already implemented in codebase)
   - Impact: Two-step query required for product→search term association

2. **Google Ads API Uses Lowercase Offer IDs** (01-01, 2026-02-11)
   - API returns and expects `shopify_us_` format (lowercase), not `shopify_US_`
   - Database format already matches API (no transformation needed for queries)
   - Impact: Confirms existing database schema is correct; GMC publishing must still transform to uppercase

3. **LIMIT Values Up to 100K Work Without Issues** (01-02, 2026-02-12)
   - Tested 10K, 50K, and 100K LIMIT values - all succeeded with 2-4s response times
   - Recommend 50K as default batch size (balances throughput with retry granularity)
   - Impact: Can use larger batches than initially assumed, reducing total API calls needed

4. **Data Retention Starts 2020-01-01 for This Account** (01-02, 2026-02-12)
   - No data exists before 2020 despite API documentation claiming 11 years retention
   - Likely reflects account activation date, not API limitation
   - Impact: Historical backfill window is 2020-01-01 to present (~6 years)

5. **Custom Attribute Field Naming Has No Underscore** (01-02, 2026-02-12)
   - Correct: `product_custom_attribute0` through `product_custom_attribute4`
   - Incorrect: `product_custom_attribute_0` (with underscore before number)
   - Impact: Must use correct field names in all queries; research document needs correction

6. **Custom Labels 0-3 Populated, Custom Label 4 Available** (02-02, 2026-02-12)
   - 4 custom labels currently populated with category/tier data
   - custom_label_4 is available for future use (could populate with product_item_id or category data)
   - Custom labels are READ-ONLY via Google Ads API (SET via Google Sheets supplemental feed)
   - Impact: Can use custom labels for efficient product segmentation without long IN clauses

7. **Performance Max Populates shopping_performance_view** (02-02, 2026-02-12)
   - PMax campaigns populate shopping_performance_view with product-level metrics
   - Filter by `campaign.advertising_channel_type = 'PERFORMANCE_MAX'` to isolate PMax data
   - Asset groups queryable with ad_strength data
   - Impact: Same query patterns work for both Standard Shopping and Performance Max

8. **performance_max_placement_view Metric Compatibility** (02-02, 2026-02-12)
   - performance_max_placement_view supports impressions metric only
   - clicks, conversions, and other metrics incompatible with this view
   - This is an API constraint, not a data availability issue
   - Impact: Limited metrics available for placement analysis

9. **Auction Insights Metrics Not Available via API** (02-03, 2026-02-12)
   - API returned access restriction error for auction_insight_* metrics (impression share, overlap rate, outranking share)
   - These metrics may be UI-only or require special API access
   - Use own-account impression share and position metrics instead
   - Impact: Cannot get competitor-specific data programmatically, but can track market share via impression_share metrics

10. **Product-Level Impression Share Available** (02-03, 2026-02-12)
   - Query succeeded with search_impression_share and search_click_share at product granularity
   - Sample data: 51% impression share, 34% click share for top product
   - Available in shopping_performance_view with segments.product_item_id
   - Impact: Can track competitive position for individual SKUs, not just campaigns

11. **Data-Driven Attribution Model Available** (02-03, 2026-02-12)
   - Conversion actions show GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN with data_driven_model_status: AVAILABLE
   - 19 enabled conversion actions with 30-day click / 1-day view-through lookback
   - Conversion lag distribution queryable (176 lag buckets found in 30-day window)
   - Impact: Attribution data is more sophisticated than basic last-click; conversion lag data informs backfill timing

Key context from PROJECT.md:
- Phase 0 is discovery only — no schema migrations, no production deployment
- 5 core questions must be answered before planning main backfill
- Research validates that campaign-join pattern already exists in codebase
- GMC offer ID case sensitivity (shopify_us vs shopify_US) is known pitfall
- [Phase 02-04]: Asset Performance Labels Not Available - asset_group_asset.performance_label field unrecognized by API v22
- [Phase 02-04]: Search Term Insights Require Campaign-Level Query - cannot query all campaigns at once for campaign_search_term_insight
- [Phase 02-04]: Demographics and Quality Scores Not Available for Shopping - confirmed these metrics only exist for Search/Display campaigns

### Pending Todos

None yet.

### Blockers/Concerns

None yet. Research summary indicates HIGH confidence in feasibility.

## Session Continuity

Last session: 2026-02-12 — Plan 02-04 execution
Stopped at: Completed 02-04-PLAN.md (Audience, Asset, and ML Insights Discovery)
Resume file: None

---
*Next step:* Phase 2 complete. Ready for Phase 3 (Sample Testing) or Phase 4 (Gap Analysis & Recommendations)
