# Phase 2 Plan 3: Bidding, Attribution, and Competitive Metrics Discovery Summary

**One-liner:** Discovered and validated bidding strategies, attribution models, conversion lag distribution, impression share, and product-level competitive metrics via Google Ads API with live data.

---

## Plan Reference

- **Phase:** 02-comprehensive-data-discovery
- **Plan:** 03
- **Type:** execute
- **Completed:** 2026-02-12

---

## Metadata

```yaml
phase: 02-comprehensive-data-discovery
plan: 03
subsystem: data-discovery
tags: [bidding, attribution, competitive-metrics, google-ads-api, discovery]

dependency_graph:
  requires:
    - 02-01 (Product Performance and Search Term Discovery)
  provides:
    - Bidding strategy data validation
    - Attribution model and conversion lag data
    - Competitive metrics availability (impression share, position)
    - Product-level impression share availability
  affects:
    - Phase 3 segmentation analysis (can use impression share for filtering)
    - Future backfill planning (attribution lag informs data collection timing)

tech_stack:
  added:
    - bidding_strategy resource queries
    - conversion_action resource queries
    - impression_share metrics at campaign and product levels
  patterns:
    - Stream-based API query execution with error handling
    - Field availability testing (auction insights access check)

key_files:
  created:
    - scripts/discover_bidding_attribution_competitive.py
    - .planning/phases/02-comprehensive-data-discovery/disc-07-08-09-results.json
  modified: []

decisions:
  - summary: "Auction insights metrics not available for this account"
    rationale: "API returned access restriction error for auction_insight_* metrics"
    alternatives: "Use own-account impression share and position metrics instead"
    impact: "Cannot get competitor-specific data, but can track market share via impression share"

  - summary: "Product-level impression share is available"
    rationale: "Query succeeded with 10 products returning search_impression_share and search_click_share"
    alternatives: "N/A - this was a test query to confirm availability"
    impact: "Can track competitive metrics at product granularity, not just campaign level"

  - summary: "Data-driven attribution model is available for this account"
    rationale: "Conversion actions show GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN with data_driven_model_status: AVAILABLE"
    alternatives: "N/A - confirms advanced attribution capability"
    impact: "Attribution data is more sophisticated than basic last-click"

metrics:
  duration: 119 seconds
  tasks_completed: 2
  queries_executed: 10
  api_calls: 10 (all via search_stream)
  files_created: 2
  success_rate: "9/10 queries succeeded (90%)"
  completed_date: 2026-02-12
```

---

## What Was Built

### DISC-07: Bidding Data Discovery

**Queries Executed:**
1. **Bidding strategies** - Retrieved 10 portfolio bidding strategies
   - Types found: TARGET_SPEND
   - Status: Some REMOVED (historical data retained)
   - Field validation: All requested fields available

2. **Campaign-level bid settings** - Retrieved 20 Shopping/PMax campaigns
   - Channel types: SHOPPING, PERFORMANCE_MAX
   - Bidding types: TARGET_SPEND, maximize_conversion_value
   - Campaign bids: target_cpa, maximize_conversion_value.target_roas available

3. **Ad group bids** - Retrieved 20 ad groups (Standard Shopping only)
   - CPC bids: cpc_bid_micros available (e.g., 250000 = $0.25)
   - Target CPA: target_cpa_micros, effective_target_cpa_micros available
   - Note: PMax campaigns don't have ad groups (expected)

**Key Findings:**
- Account uses primarily automated bidding (TARGET_SPEND, maximize conversions)
- Campaign-level bidding strategy type queryable
- Ad group-level bids available for Standard Shopping campaigns
- All requested bidding fields are accessible via API

### DISC-08: Attribution Data Discovery

**Queries Executed:**
1. **Conversion action settings** - Retrieved 19 enabled conversion actions
   - Types: UNIVERSAL_ANALYTICS_TRANSACTION, others
   - Attribution model: GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN (data-driven attribution)
   - Model status: AVAILABLE (not in learning phase)
   - Lookback windows: 30-day click, 1-day view-through
   - Counting type: MANY_PER_CLICK (transaction-based)

2. **Conversion lag distribution** - Retrieved 176 lag bucket data points
   - Segments: conversion_lag_bucket (LESS_THAN_ONE_DAY, etc.)
   - Metrics: conversions, conversions_value per lag bucket
   - Coverage: 30-day window with conversion data
   - Granularity: Per-campaign, per-lag-bucket

3. **Cross-device and view-through attribution** - Retrieved 501 campaign-day combinations
   - Metrics available: conversions, cross_device_conversions, view_through_conversions, all_conversions
   - Data: Mix of zero and non-zero values (expected for 30-day window)
   - Use case: Track multi-device conversion paths

**Key Findings:**
- Account has data-driven attribution model enabled and available
- Conversion lag data queryable for understanding time-to-conversion
- Cross-device and view-through metrics accessible
- Attribution window: 30-day click, 1-day view-through (standard for e-commerce)

### DISC-09: Competitive Metrics Discovery

**Queries Executed:**
1. **Own-account impression share metrics** - Retrieved 20 campaigns (SUCCESS)
   - Metrics: search_impression_share, search_click_share, search_budget_lost_impression_share, search_rank_lost_impression_share
   - Additional: search_top_impression_share, search_absolute_top_impression_share
   - All metrics returned successfully for Shopping and PMax campaigns

2. **Position metrics** - Retrieved 10 campaigns (SUCCESS)
   - Metrics: top_impression_percentage, absolute_top_impression_percentage, impressions, clicks
   - Data quality: Mix of zero and non-zero values (depends on date range and campaign activity)

3. **Auction insights** - Access restricted (EXPECTED FAILURE)
   - Error: "The developer doesn't have access to metrics: 'auction_insight_search_impression_share', 'auction_insight_search_overlap_rate', 'auction_insight_search_outranking_share'"
   - Interpretation: These metrics require special API access or are not available via API
   - Alternative: Auction Insights available in UI, but not programmatically

4. **Product-level impression share** - Retrieved 10 products (SUCCESS - CRITICAL FINDING)
   - Metrics: search_impression_share, search_click_share available at product granularity
   - Sample data: 51% impression share, 34% click share for top product
   - Impact: Can track competitive position for individual SKUs, not just campaigns
   - Use case: Identify products losing impression share to competitors

**Key Findings:**
- Impression share and position metrics available at campaign level
- **Product-level impression share IS AVAILABLE** (not campaign-only)
- Auction insights (competitor-specific data) NOT accessible via API
- Budget loss and rank loss metrics available for optimization analysis

---

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

### Architectural Decisions

None required.

---

## Technical Implementation

### Discovery Script Pattern

The script follows the `discover_fields.py` pattern:
- Client loading: `load_client()` tries env first, then storage
- Stream-based queries: Uses `search_stream()` for efficient data retrieval
- Error handling: Catches `GoogleAdsException` and returns structured error details
- Result structure: `{success, row_count, sample_data, query}` or `{success, error, error_code, query}`

### JSON Output Structure

```json
{
  "customer_id": "6253381786",
  "bidding": {
    "bidding_strategies": { ... },
    "campaign_bid_settings": { ... },
    "ad_group_bids": { ... }
  },
  "attribution": {
    "conversion_action_settings": { ... },
    "conversion_lag_distribution": { ... },
    "cross_device_attribution": { ... }
  },
  "competitive_metrics": {
    "impression_share_metrics": { ... },
    "position_metrics": { ... },
    "auction_insights": { ... },
    "product_level_impression_share": { ... }
  }
}
```

Each query result includes:
- `success`: Boolean
- `row_count`: Number of rows returned
- `sample_data`: First 5 rows (for successful queries)
- `query`: The GAQL query executed
- `error`/`error_code`: If query failed

---

## Verification Results

- [x] `scripts/discover_bidding_attribution_competitive.py` runs without errors
- [x] `disc-07-08-09-results.json` contains bidding, attribution, and competitive sections
- [x] Bidding strategies and bid data documented for Shopping campaigns
- [x] Attribution models and conversion lag documented
- [x] Competitive metrics tested at campaign and product levels
- [x] DISC-07, DISC-08, DISC-09 requirements addressed

**Additional verifications:**
- [x] Bidding queries: 3/3 succeeded (100%)
- [x] Attribution queries: 3/3 succeeded (100%)
- [x] Competitive queries: 3/4 succeeded (75% - auction insights restricted)
- [x] Product-level impression share confirmed available with sample data
- [x] Data-driven attribution model confirmed available

---

## Key Insights

### Bidding Intelligence

1. **Portfolio bidding strategies** - 10 strategies found (mostly TARGET_SPEND)
2. **Campaign bidding types** - Mix of automated bidding (TARGET_SPEND, maximize conversions)
3. **Ad group bids** - CPC bids available for Standard Shopping (not PMax)

### Attribution Intelligence

1. **Data-driven attribution enabled** - Most sophisticated attribution model available
2. **Conversion lag data available** - Can analyze time-to-conversion patterns
3. **Multi-device tracking** - Cross-device conversions tracked separately
4. **Attribution windows** - 30-day click / 1-day view-through (industry standard)

### Competitive Intelligence

1. **Impression share at campaign level** - Budget loss and rank loss identifiable
2. **Impression share at product level** - Can track competitive position per SKU (critical discovery)
3. **Position metrics available** - Top-of-page and absolute-top tracking
4. **Auction insights restricted** - Competitor-specific data not accessible via API

### Implications for Phase 3+

1. **Segmentation can use impression share** - Filter products by competitive position
2. **Attribution lag informs backfill timing** - Need to account for conversion delay when measuring impact
3. **Product-level competitive analysis possible** - Can identify which SKUs are losing market share
4. **Bidding data context available** - Can correlate content changes with bid strategy changes

---

## What's Next

**Phase 2 Plan 4:** Segmentation and field availability analysis
- Time-based segmentation testing (daily, weekly, monthly rollups)
- Device, location, and custom attribute segmentation
- Complete field availability matrix for all discovered views

**Phase 3:** Historical data backfill strategy planning
- Use attribution lag data to determine lookback period
- Use impression share data to prioritize high-opportunity products
- Plan batch sizes and rate limiting based on Phase 1 findings

---

## Self-Check: PASSED

**Created files verified:**
```bash
✓ FOUND: scripts/discover_bidding_attribution_competitive.py (executable Python script)
✓ FOUND: .planning/phases/02-comprehensive-data-discovery/disc-07-08-09-results.json (313KB JSON data)
```

**Commits verified:**
```bash
✓ FOUND: 1d59ba65 - feat(02-03): discover bidding and attribution data (DISC-07, DISC-08)
```

**JSON structure verified:**
```bash
✓ Sections: customer_id, bidding, attribution, competitive_metrics
✓ Bidding queries: 3 (bidding_strategies, campaign_bid_settings, ad_group_bids)
✓ Attribution queries: 3 (conversion_action_settings, conversion_lag_distribution, cross_device_attribution)
✓ Competitive queries: 4 (impression_share_metrics, position_metrics, auction_insights, product_level_impression_share)
```

**Query success rates:**
```bash
✓ Bidding: 3/3 succeeded (100%)
✓ Attribution: 3/3 succeeded (100%)
✓ Competitive: 3/4 succeeded (75% - auction insights restricted as expected)
✓ Overall: 9/10 queries succeeded (90%)
```

All plan objectives met. Ready for state updates.
