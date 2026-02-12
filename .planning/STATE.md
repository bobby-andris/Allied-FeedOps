# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-11)

**Core value:** Validate Google Ads API capabilities and comprehensively map available data to inform backfill strategy before planning Phases 1-5
**Current focus:** Phase 2 - Comprehensive Data Discovery

## Current Position

Phase: 2 of 4 (Comprehensive Data Discovery)
Plan: 2 of 4 in current phase
Status: In progress
Last activity: 2026-02-12 — Completed plan 02-02 (Custom Label Filtering and PMax Discovery)

Progress: [█████░░░░░] 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 3.75 minutes
- Total execution time: 0.25 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. API Capability Validation | 2 | 9 min | 4.5 min |
| 2. Comprehensive Data Discovery | 2 | 6 min | 3 min |

**Recent Trend:**
- Latest: 02-02 (3 minutes)
- Previous: 02-01 (3 minutes)
- Trend: Accelerating velocity (~3 min/plan in Phase 2)

*Updated after each plan completion*

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

Key context from PROJECT.md:
- Phase 0 is discovery only — no schema migrations, no production deployment
- 5 core questions must be answered before planning main backfill
- Research validates that campaign-join pattern already exists in codebase
- GMC offer ID case sensitivity (shopify_us vs shopify_US) is known pitfall

### Pending Todos

None yet.

### Blockers/Concerns

None yet. Research summary indicates HIGH confidence in feasibility.

## Session Continuity

Last session: 2026-02-12 — Plan 02-02 execution
Stopped at: Completed 02-02-PLAN.md (Custom Label Filtering and PMax Discovery)
Resume file: None

---
*Next step:* Continue Phase 2 with Plan 02-03 (Segmentation Analysis)
