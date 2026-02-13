# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-11)

**Core value:** Validate Google Ads API capabilities and comprehensively map available data to inform backfill strategy before planning Phases 1-5
**Current focus:** Phase 2 - Comprehensive Data Discovery

## Current Position

Phase: 3 of 4 (Sample Testing & Analysis)
Plan: 2 of 2 in current phase
Status: Phase complete
Last activity: 2026-02-13 — Completed plan 03-02 (Keyword Planner Ideas and Opportunity Gap Analysis)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 3.1 minutes
- Total execution time: 0.42 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. API Capability Validation | 2 | 9 min | 4.5 min |
| 2. Comprehensive Data Discovery | 4 | 11 min | 2.75 min |
| 3. Sample Testing & Analysis | 2 | 10 min | 5.0 min |

**Recent Trend:**
- Latest: 03-02 (4 minutes)
- Previous: 03-01 (6 minutes)
- Trend: Consistent performance for API integration tasks

*Updated after each plan completion*
| Phase 03 P01 | 6 | 1 task | 3 files |
| Phase 03 P02 | 4 | 1 task | 3 files |

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

12. **LAST_N_DAYS Syntax Not Supported** (03-01, 2026-02-13)
   - Google Ads API rejects date literals like `LAST_90_DAYS` with "Invalid value" error
   - Must use explicit date ranges: `BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'`
   - Calculate dates in code before building query string
   - Impact: All date range queries require Python datetime calculations

13. **Filtered Fields Must Be in SELECT Clause** (03-01, 2026-02-13)
   - API enforces strict rule: fields used in WHERE must appear in SELECT
   - Example: `WHERE campaign.advertising_channel_type = 'SHOPPING'` requires `SELECT campaign.advertising_channel_type`
   - Same applies to segments.product_item_id and other filtered fields
   - Impact: SELECT clauses must include all WHERE filter fields, not just desired output fields

14. **Category-Based SKU Selection Requires Fallback Strategy** (03-01, 2026-02-13)
   - Many products in catalog lack recent Google Ads activity (<30 days)
   - Category-only selection insufficient for representative sampling
   - Solution: Use known-active offer IDs from validation phase as fallback
   - Impact: Sample selection scripts need two-tier strategy (category first, fallback second)

Key context from PROJECT.md:
- Phase 0 is discovery only — no schema migrations, no production deployment
- 5 core questions must be answered before planning main backfill
- Research validates that campaign-join pattern already exists in codebase
- GMC offer ID case sensitivity (shopify_us vs shopify_US) is known pitfall
- [Phase 02-04]: Asset Performance Labels Not Available - asset_group_asset.performance_label field unrecognized by API v22
- [Phase 02-04]: Search Term Insights Require Campaign-Level Query - cannot query all campaigns at once for campaign_search_term_insight
- [Phase 02-04]: Demographics and Quality Scores Not Available for Shopping - confirmed these metrics only exist for Search/Display campaigns
- [Phase 03-01]: Sample set established - 6 SKUs, 5 categories, 60K+ search terms, 560K impressions

15. **Keyword Planner Requires Generic Category Terms for Idea Generation** (03-02, 2026-02-13)
   - Full product titles (brand + model) return only exact match with 0 search volume
   - Generic category terms (e.g., "grab bar" vs "Pipeline Collection 16 Inch Grab Bar") generate 100+ related ideas
   - Impact: Seed keyword selection is critical for quality Keyword Planner results

16. **Keyword Planner Competition Field Returns Integer (Not Enum)** (03-02, 2026-02-13)
   - API returns competition as int (0-3) instead of enum object with .name attribute
   - Must handle both int and enum types in parsing code
   - Mapping: 0=UNSPECIFIED, 1=LOW, 2=MEDIUM, 3=HIGH
   - Impact: Type checking required to avoid runtime errors

### Pending Todos

None yet.

### Blockers/Concerns

None yet. Research summary indicates HIGH confidence in feasibility.

## Session Continuity

Last session: 2026-02-13 — Plan 03-02 execution
Stopped at: Completed 03-02-PLAN.md (Keyword Planner Ideas and Opportunity Gap Analysis)
Resume file: None

---
*Next step:* Phase 3 complete. Ready for Phase 4 (Gap Analysis & Recommendations)
