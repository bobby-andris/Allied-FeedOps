# Phase 2: Comprehensive Data Discovery - Research

**Researched:** 2026-02-12
**Domain:** Google Ads API Data Sources (All Views, Metrics, Segments, Campaign Types)
**Confidence:** HIGH

## Summary

This research provides a complete inventory of Google Ads API data sources available for Shopping campaigns. The API exposes 230+ resources (views), 280+ performance metrics, and 100+ segmentation dimensions. Key findings confirm that `shopping_performance_view` is the primary resource for product-level metrics, with `segments.product_custom_attribute0-4` available for filtering. Performance Max campaigns are fully supported with dedicated resources. Auction Insights data is NOT available via API (UI-only), but core competitive metrics (impression share, search click share) ARE available through standard campaign/ad group reporting.

The google-ads Python client library (v24+) is the standard implementation tool, with full schema metadata accessible via GoogleAdsFieldService for discovering field capabilities programmatically.

## User Constraints

No user constraints from CONTEXT.md (file does not exist for this phase).

## Phase 1 Prior Decisions (Inherited Context)

These validated findings from Phase 1 inform this research:

1. **search_term_view Cannot Filter by Product** - Must use campaign-join pattern
2. **Google Ads API Uses Lowercase Offer IDs** - `shopify_us_` format (no transformation needed)
3. **LIMIT Values Up to 100K Work Without Issues** - 50K recommended batch size
4. **Data Retention Starts 2020-01-01 for This Account** - ~6 years available
5. **Custom Attribute Field Naming** - `product_custom_attribute0-4` (NO underscore before number)

## Complete Data Source Inventory

### Core Shopping Resources (DISC-01)

**Primary Shopping Views:**

1. **shopping_performance_view** - THE primary resource for product-level performance metrics
   - Status: Production-ready, actively used in codebase
   - Selectable: No direct fields (joins to segments and metrics)
   - Use case: Product performance queries by offer ID, date, campaign
   - Can segment by: All segments fields (date, product_item_id, product_custom_attribute0-4, etc.)
   - Can measure by: All metrics (impressions, clicks, conversions, cost, etc.)
   - **CRITICAL**: This is the ONLY view that supports `segments.product_item_id` filtering

2. **search_term_view** - Search query data (requires campaign-join for products)
   - Selectable: `ad_group`, `resource_name`, `search_term`, `status`
   - Filterable: All selectable fields
   - Sortable: `search_term`, `status`
   - **Limitation**: Cannot filter by `segments.product_item_id` (Phase 1 finding)
   - Use case: Search terms aggregated by ad group/campaign

3. **shopping_product** - Product catalog metadata (NOT performance)
   - Selectable: 34 fields including `item_id`, `title`, `brand`, `custom_attribute0-4`, `status`, `availability`
   - Filterable: All except `issues` array
   - Sortable: 25 fields
   - Use case: Product inventory status, issues, attributes
   - **Query requirement**: Must filter by campaign AND ad_group (strict scoping)

4. **product_group_view** - Product group partition data
   - Selectable: `resource_name` only
   - Use case: Shopping campaign product group structure

**Supporting Shopping Resources:**

5. **campaign_view** - Campaign-level data (includes Shopping settings)
6. **ad_group_view** - Ad group-level data
7. **product_category_constant** - Google product taxonomy (6k+ categories)
8. **hotel_performance_view** / **travel_activity_performance_view** - Hotel/Travel equivalents

### Performance Max Resources (DISC-05)

**Confirmed Available:**

1. **asset_group** - PMax asset group data
   - Selectable: `campaign`, `id`, `name`, `status`, `ad_strength`, `final_urls`, `path1`, `path2`
   - Use case: PMax asset group management

2. **asset_group_product_group_view** - PMax product targeting
   - Selectable: `asset_group`, `asset_group_listing_group_filter`, `resource_name`
   - Use case: Product partition structure in PMax

3. **asset_group_listing_group_filter** - PMax product filters
   - Selectable: Product dimension filters (brand, category, channel, condition, custom_attribute, item_id, type)
   - Use case: Product targeting configuration

4. **performance_max_placement_view** - PMax placement data
   - Selectable: `display_name`, `placement`, `placement_type`, `target_url`
   - Use case: Where PMax ads appeared

5. **asset_group_asset** - PMax asset details
   - Selectable: Asset assignments, field types, status, policy
   - Use case: Asset performance tracking

6. **asset_group_top_combination_view** - Top performing asset combinations
   - Selectable: `asset_group_top_combinations`
   - Use case: Asset combination insights

**Performance Max Query Pattern:**
```sql
SELECT
  campaign.id,
  asset_group.id,
  segments.product_item_id,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM shopping_performance_view
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND segments.date BETWEEN '2025-01-01' AND '2025-12-31'
```

**Key Finding:** Performance Max campaigns populate `shopping_performance_view` with product-level data just like standard Shopping campaigns. Use `campaign.advertising_channel_type` filter to distinguish.

### Complete Metrics Inventory (DISC-02)

**Shopping-Specific Metrics (280+ total available):**

**Core Performance (Always Available):**
- `metrics.impressions` - Ad impressions
- `metrics.clicks` - Ad clicks
- `metrics.ctr` - Click-through rate (clicks/impressions)
- `metrics.cost_micros` - Cost in micros (divide by 1M for dollars)
- `metrics.average_cpc` - Average cost per click
- `metrics.average_cpm` - Average cost per thousand impressions

**Conversion Metrics:**
- `metrics.conversions` - Conversion count
- `metrics.conversions_value` - Total conversion value
- `metrics.conversions_from_interactions_rate` - Conversion rate
- `metrics.conversions_value_per_cost` - ROAS
- `metrics.cost_per_conversion` - CPA
- `metrics.all_conversions` - All conversions (includes view-through)
- `metrics.all_conversions_value` - All conversion value
- `metrics.view_through_conversions` - View-through conversions

**Shopping Cart Data Metrics (v22+):**
- `metrics.orders` - Number of orders
- `metrics.average_cart_size` - Average items per cart
- `metrics.average_order_value_micros` - Average order value
- `metrics.revenue_micros` - Total revenue
- `metrics.units_sold` - Total units sold
- `metrics.cost_of_goods_sold_micros` - COGS
- `metrics.gross_profit_micros` - Gross profit
- `metrics.gross_profit_margin` - Margin percentage

**Cross-Sell/Lead Metrics:**
- `metrics.cross_sell_cost_of_goods_sold_micros`
- `metrics.cross_sell_gross_profit_micros`
- `metrics.cross_sell_revenue_micros`
- `metrics.cross_sell_units_sold`
- `metrics.lead_cost_of_goods_sold_micros`
- `metrics.lead_gross_profit_micros`
- `metrics.lead_revenue_micros`
- `metrics.lead_units_sold`

**Impression Share & Auction Metrics (DISC-09):**
- `metrics.search_impression_share` - Search IS %
- `metrics.search_click_share` - Search click share %
- `metrics.search_budget_lost_impression_share` - Budget-limited IS loss
- `metrics.search_rank_lost_impression_share` - Rank-limited IS loss
- `metrics.search_top_impression_share` - Top of page IS %
- `metrics.search_absolute_top_impression_share` - Absolute top IS %
- `metrics.top_impression_percentage` - Top position %
- `metrics.absolute_top_impression_percentage` - Absolute top %

**Auction Insights Metrics (DISC-09 - Available with auction_insight_domain segment):**
- `metrics.auction_insight_search_impression_share`
- `metrics.auction_insight_search_overlap_rate`
- `metrics.auction_insight_search_outranking_share`
- `metrics.auction_insight_search_position_above_rate`
- `metrics.auction_insight_search_top_impression_percentage`
- `metrics.auction_insight_search_absolute_top_impression_percentage`

**NOTE**: Full Auction Insights Report (competitor-level data) is UI-only and NOT available via API. These metrics only work when `segments.auction_insight_domain` is included and require special account access.

**Attribution & Customer Lifecycle:**
- `metrics.cross_device_conversions` - Cross-device attribution
- `metrics.current_model_attributed_conversions` - Current attribution model
- `metrics.platform_comparable_conversions` - Platform-standardized conversions
- `metrics.new_customer_lifetime_value` - New customer LTV
- `metrics.all_new_customer_lifetime_value` - All new customer LTV

**Data Types:**
- Integer: impressions, clicks, conversions
- Float: ctr, conversion_rate, roas
- Micros (int64): cost_micros, cpc_micros, conversion_value (divide by 1,000,000)

**Availability:** All metrics are selectable when querying `shopping_performance_view`. Not all metrics will have data (e.g., cart data requires Merchant Center cart data feed).

### Custom Label Filtering (DISC-03)

**CONFIRMED Available:**

**Segment Fields (All Filterable):**
- `segments.product_custom_attribute0`
- `segments.product_custom_attribute1`
- `segments.product_custom_attribute2`
- `segments.product_custom_attribute3`
- `segments.product_custom_attribute4`

**Shopping Product Fields (Filterable):**
- `shopping_product.custom_attribute0`
- `shopping_product.custom_attribute1`
- `shopping_product.custom_attribute2`
- `shopping_product.custom_attribute3`
- `shopping_product.custom_attribute4`

**Data Type:** STRING (exact match only)

**Example Query:**
```sql
SELECT
  segments.product_item_id,
  segments.product_custom_attribute0,
  metrics.impressions,
  metrics.clicks
FROM shopping_performance_view
WHERE segments.product_custom_attribute0 = 'Towel Bars'
  AND segments.date DURING LAST_30_DAYS
```

**Current Usage:**
- Google Sheets feed populates custom_label_0, 1, 2, 4
- custom_label_3 is unused
- **Opportunity**: Could populate custom_label_4 with product_item_id for easier filtering (DISC-04)

**Filtering Capabilities:**
- Exact match: `= 'value'`
- IN clause: `IN ('value1', 'value2')`
- NOT: `!= 'value'` or `NOT IN ('value1', 'value2')`
- **NO support for**: LIKE, CONTAINS, regex

**Best Practice:** Use for high-cardinality dimensions (category, tier, product line) to segment large product catalogs without building long IN clauses of offer IDs.

### Segmentation Dimensions (DISC-11)

**100+ Segment Fields Available:**

**Product Dimensions:**
- `segments.product_item_id` - GMC offer ID
- `segments.product_brand` - Brand name
- `segments.product_category_level1-5` - Google taxonomy
- `segments.product_type_l1-5` - Custom product type
- `segments.product_custom_attribute0-4` - Custom labels
- `segments.product_channel` - online/local
- `segments.product_channel_exclusivity` - single/multi-channel
- `segments.product_condition` - new/used/refurbished
- `segments.product_title` - Product title
- `segments.product_feed_label` - Feed label
- `segments.product_merchant_id` - Merchant center ID
- `segments.product_store_id` - Local inventory store ID
- `segments.product_aggregator_id` - Comparison shopping service ID
- `segments.product_country` - Target country
- `segments.product_language` - Target language

**Time Dimensions:**
- `segments.date` - Date (YYYY-MM-DD)
- `segments.week` - Week start date
- `segments.month` - Month start date
- `segments.quarter` - Quarter start date
- `segments.year` - Year
- `segments.day_of_week` - MONDAY, TUESDAY, etc.
- `segments.month_of_year` - JANUARY, FEBRUARY, etc.
- `segments.hour` - Hour of day (0-23)

**Campaign/Ad Structure:**
- `segments.campaign` - Campaign resource name
- `segments.ad_group` - Ad group resource name
- `segments.asset_group` - Asset group (PMax)
- `segments.ad_network_type` - SEARCH, SHOPPING, DISPLAY
- `segments.device` - MOBILE, TABLET, DESKTOP
- `segments.click_type` - URL_CLICKS, CALLS, etc.

**Geography Dimensions:**
- `segments.geo_target_country` - Country
- `segments.geo_target_region` - State/province/region
- `segments.geo_target_metro` - Metro area
- `segments.geo_target_city` - City
- `segments.geo_target_postal_code` - Postal code
- `segments.geo_target_county` - County
- `segments.geo_target_most_specific_location` - Most specific available

**Audience Dimensions:**
- `segments.adjusted_age_range` - 18-24, 25-34, 35-44, etc.
- `segments.adjusted_gender` - MALE, FEMALE, UNKNOWN
- `segments.new_versus_returning_customers` - NEW, RETURNING, UNKNOWN

**Conversion Dimensions:**
- `segments.conversion_action` - Conversion action resource name
- `segments.conversion_action_name` - Conversion action name
- `segments.conversion_action_category` - PURCHASE, LEAD, etc.
- `segments.external_conversion_source` - Source of imported conversions

**Search Dimensions:**
- `segments.search_term` - Search query text
- `segments.search_term_match_type` - EXACT, PHRASE, BROAD
- `segments.match_type` - Keyword match type
- `segments.search_engine_results_page_type` - RESULTS_PAGE, ADVERTISER_PAGE, etc.

**Asset/Creative Dimensions (DISC-10):**
- `segments.asset_interaction_target` - Which asset was interacted with
- `segments.ad_format_type` - Shopping ad format
- `segments.ad_using_product_data` - Whether ad uses product data
- `segments.ad_using_video` - Whether ad uses video

**Competitive Dimensions:**
- `segments.auction_insight_domain` - Competitor domain (requires special access)

**SKAdNetwork (Mobile App):**
- `segments.sk_ad_network_*` - Various mobile attribution fields

### Bidding Data (DISC-07)

**Bidding Resources:**

1. **bidding_strategy** - Shared bidding strategies
   - Selectable: 29 fields including strategy type, target CPA/ROAS, CPC ceilings/floors
   - Types: TARGET_CPA, TARGET_ROAS, MAXIMIZE_CONVERSIONS, MAXIMIZE_CONVERSION_VALUE, TARGET_SPEND, TARGET_IMPRESSION_SHARE

2. **Campaign-level bid settings:**
   - `campaign.target_cpa.target_cpa_micros`
   - `campaign.target_roas.target_roas`
   - `campaign.maximize_conversions.target_cpa_micros`
   - `campaign.maximize_conversion_value.target_roas`
   - `campaign.manual_cpc.enhanced_cpc_enabled`

3. **Ad Group-level bids:**
   - `ad_group.cpc_bid_micros` - Max CPC bid
   - `ad_group.target_cpa_micros` - Target CPA
   - `ad_group.target_roas` - Target ROAS
   - `ad_group.effective_target_cpa_micros` - Effective CPA (inherited or set)
   - `ad_group.effective_target_roas` - Effective ROAS

4. **Product Group bids:**
   - `ad_group_criterion.cpc_bid_micros` - Product partition max CPC
   - `ad_group_criterion.effective_cpc_bid_micros` - Effective CPC bid
   - Via `listing_group` dimension

**Auction Insights (DISC-09):**

**Via API (Available):**
- Impression share metrics (own account only)
- Search click share
- Budget/rank lost impression share
- Top/absolute top impression percentages

**Via UI Only (NOT available via API):**
- Full Auction Insights Report with competitor domains
- Overlap rate, outranking share, position above rate BY competitor

**Note:** The `auction_insight_*` metrics exist in the API but require `segments.auction_insight_domain`, which is only populated for accounts with special access (typically large advertisers). For most accounts, these will return no data.

### Attribution Data (DISC-08)

**Conversion Attribution Resources:**

1. **conversion_action** - Conversion tracking configuration
   - `attribution_model_settings.attribution_model` - LAST_CLICK, FIRST_CLICK, LINEAR, TIME_DECAY, POSITION_BASED, DATA_DRIVEN
   - `attribution_model_settings.data_driven_model_status` - ELIGIBLE, NOT_ELIGIBLE, LEARNING
   - `click_through_lookback_window_days` - 1-90 days
   - `view_through_lookback_window_days` - 1-30 days
   - `counting_type` - ONE_PER_CLICK, MANY_PER_CLICK

2. **Attribution Metrics:**
   - `metrics.conversions` - Default attribution model
   - `metrics.current_model_attributed_conversions` - Current model
   - `metrics.cross_device_conversions` - Cross-device attribution
   - `metrics.view_through_conversions` - View-through conversions

3. **Conversion Segments:**
   - `segments.conversion_action` - Which conversion action
   - `segments.conversion_attribution_event_type` - CLICK, VIEW
   - `segments.conversion_lag_bucket` - Time to conversion (LESS_THAN_ONE_DAY, ONE_TO_TWO_DAYS, etc.)
   - `segments.external_conversion_source` - GA4, Salesforce, etc.

**Assisted Conversion Data:**

NOT directly available in Shopping views. The `conversion_action` resource has limited path data. For full path analysis, must use Google Analytics 4 integration.

**Available:**
- Conversion lag buckets
- Device cross-over (via `cross_device_conversions`)
- Attribution model comparison (via `current_model_attributed_conversions`)

**NOT Available via API:**
- Full conversion path (multi-touch)
- Assisted conversion counts
- Top conversion paths

### Asset-Level Performance (DISC-10)

**For Shopping Ads:** Limited asset-level data

**Available for Performance Max:**

1. **asset_group_asset** - Individual assets
   - `asset` - Asset resource name
   - `field_type` - HEADLINE, DESCRIPTION, IMAGE, etc.
   - `performance_label` - BEST, GOOD, LOW, LEARNING, UNRATED
   - `enabled` - Active status

2. **Metrics by asset performance:**
   - `metrics.asset_best_performance_cost_percentage`
   - `metrics.asset_best_performance_impression_percentage`
   - `metrics.asset_good_performance_cost_percentage`
   - `metrics.asset_good_performance_impression_percentage`
   - `metrics.asset_low_performance_cost_percentage`
   - `metrics.asset_low_performance_impression_percentage`
   - `metrics.asset_learning_performance_cost_percentage`
   - `metrics.asset_learning_performance_impression_percentage`

3. **Asset pinning metrics:**
   - `metrics.asset_pinned_as_headline_position_one_count`
   - `metrics.asset_pinned_as_headline_position_two_count`
   - `metrics.asset_pinned_as_headline_position_three_count`
   - `metrics.asset_pinned_as_description_position_one_count`
   - `metrics.asset_pinned_as_description_position_two_count`
   - `metrics.asset_pinned_total_count`

**For Standard Shopping:** No direct asset-level metrics. Shopping ads use product data from GMC, not ad assets.

**Segment-level insight:**
- `segments.ad_format_type` - Shopping ad format
- `segments.asset_interaction_target.asset` - Which asset was clicked (PMax)
- `segments.asset_interaction_target.interaction_on_this_asset` - Boolean

### Competitive Metrics (DISC-09)

**Available via Standard Metrics:**

**Own Account Metrics (Always Available):**
1. **Search Impression Share:**
   - `metrics.search_impression_share` - % of eligible impressions
   - `metrics.search_budget_lost_impression_share` - Lost due to budget
   - `metrics.search_rank_lost_impression_share` - Lost due to rank
   - `metrics.search_exact_match_impression_share` - Exact match only
   - `metrics.search_top_impression_share` - Top of page
   - `metrics.search_absolute_top_impression_share` - Absolute top

2. **Search Click Share:**
   - `metrics.search_click_share` - % of available clicks captured

3. **Position Metrics:**
   - `metrics.top_impression_percentage` - % of impressions at top
   - `metrics.absolute_top_impression_percentage` - % at absolute top

**Auction Insights Metrics (Requires Special Access):**

When `segments.auction_insight_domain` is available (large advertisers only):
- `metrics.auction_insight_search_impression_share`
- `metrics.auction_insight_search_overlap_rate`
- `metrics.auction_insight_search_outranking_share`
- `metrics.auction_insight_search_position_above_rate`
- `metrics.auction_insight_search_top_impression_percentage`
- `metrics.auction_insight_search_absolute_top_impression_percentage`

**NOT Available via API:**
- Competitor domains list (UI only)
- Overlap rate by competitor (UI only)
- Outranking share by competitor (UI only)
- Position above rate by competitor (UI only)

**Recommendation:** Use standard impression share and click share metrics for competitive analysis. These are sufficient to identify budget vs quality issues without requiring UI access.

### Machine Learning Insights (DISC-12)

**Recommendations API:**

1. **recommendation** Resource - 40+ recommendation types
   - `type` - Recommendation type enum (KEYWORD, CALL_ASSET, CAMPAIGN_BUDGET, etc.)
   - `impact` - Projected impact metrics
   - `dismissed` - Whether recommendation is dismissed

**Shopping-Specific Recommendation Types:**
- SHOPPING_ADD_AGE_GROUP_RECOMMENDATION
- SHOPPING_ADD_COLOR_RECOMMENDATION
- SHOPPING_ADD_GENDER_RECOMMENDATION
- SHOPPING_ADD_GTIN_RECOMMENDATION
- SHOPPING_ADD_MORE_IDENTIFIERS_RECOMMENDATION
- SHOPPING_ADD_PRODUCTS_TO_CAMPAIGN_RECOMMENDATION
- SHOPPING_ADD_SIZE_RECOMMENDATION
- SHOPPING_FIX_DISAPPROVED_PRODUCTS_RECOMMENDATION
- SHOPPING_FIX_SUSPENDED_MERCHANT_CENTER_ACCOUNT_RECOMMENDATION
- SHOPPING_TARGET_ALL_OFFERS_RECOMMENDATION
- SHOPPING_MIGRATE_REGULAR_SHOPPING_CAMPAIGN_OFFERS_TO_PERFORMANCE_MAX_RECOMMENDATION

**Optimization Insights:**
- `campaign.optimization_score` - 0-100 score
- `metrics.optimization_score_uplift` - Projected improvement
- `metrics.optimization_score_url` - Link to recommendations

**Smart Bidding Insights:**
- `bidding_strategy.maximize_conversion_value.target_roas_tolerance_percent_millis` - Flexibility setting
- `campaign.bidding_strategy_system_status` - LEARNING, ELIGIBLE, LIMITED, etc.

**Search Term Insights:**
- `customer_search_term_insight` - Aggregated search term clusters
- `campaign_search_term_insight` - Campaign-level insights
- `category_label` - ML-categorized search intent

**Ad Strength:**
- `asset_group.ad_strength` - EXCELLENT, GOOD, AVERAGE, POOR, PENDING
- `ad_group_ad.ad_strength` - For responsive search ads

**Change Event Tracking:**
- `change_event` - Resource change history (last 30 days)
- Tracks changes to campaigns, ad groups, keywords, bids

**Reach & Frequency (Video):**
- `recommendation.forecasting_campaign_budget_recommendation` - Budget forecasts
- `recommendation.forecasting_set_target_cpa_recommendation` - CPA forecasts
- `recommendation.forecasting_set_target_roas_recommendation` - ROAS forecasts

**Quality Score (Search/Shopping):**
- `ad_group_criterion.quality_info.quality_score` - 1-10 (keyword-level)
- `ad_group_criterion.quality_info.creative_quality_score` - ABOVE_AVERAGE, AVERAGE, BELOW_AVERAGE
- `ad_group_criterion.quality_info.landing_page_quality_score`
- `ad_group_criterion.quality_info.search_predicted_ctr`

### All Shopping Campaign Report Types (DISC-06)

**Primary Reports (Use These):**

1. **shopping_performance_view** - Product-level performance
   - Use case: Product performance over time
   - Segments: All product, time, geo, device dimensions
   - Metrics: All standard metrics

2. **campaign** - Campaign-level aggregates
   - Use case: Campaign performance, budget tracking
   - Segments: Time, geo, device, network
   - Metrics: All standard metrics + campaign settings

3. **ad_group** - Ad group-level aggregates
   - Use case: Product group performance
   - Segments: Time, device
   - Metrics: All standard metrics

4. **search_term_view** - Search query performance
   - Use case: Query analysis (with campaign-join)
   - Segments: Time, device, match type
   - Metrics: All standard metrics

5. **product_group_view** - Product partition performance
   - Use case: Product group tree analysis
   - Segments: Product dimensions
   - Metrics: All standard metrics

**Specialized Reports:**

6. **geographic_view** - Performance by location
7. **user_location_view** - Performance by user physical location
8. **shopping_product** - Product status and issues (NOT performance)
9. **asset_group_product_group_view** - PMax product targeting
10. **performance_max_placement_view** - PMax placement data

**Legacy/Deprecated:**
- `shopping_smart_ad` - Smart Shopping (sunset 2022)

**Comparison Matrix:**

| Report Type | Granularity | Primary Use Case | Product Filter | Campaign Filter |
|-------------|-------------|------------------|----------------|-----------------|
| shopping_performance_view | Product + Date | Product performance | ✅ product_item_id | ✅ campaign.id |
| campaign | Campaign + Date | Budget tracking | ❌ | ✅ campaign.id |
| ad_group | Ad Group + Date | Product group performance | ❌ | ✅ via ad_group |
| search_term_view | Query + Ad Group | Search analysis | ❌ (join required) | ✅ via ad_group |
| product_group_view | Product Partition | Tree structure | ❌ | ✅ |
| shopping_product | Variant | Product issues | ✅ item_id | ✅ campaign + ad_group |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-ads | 24.1.0+ | Official Google Ads API Python client | Google-maintained, complete API coverage, handles auth/pagination/streaming |
| google-api-core | Latest | gRPC transport | Required dependency, handles retry logic |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| protobuf | 3.20+ | Proto message serialization | Required for google-ads client |
| google-auth-oauthlib | Latest | OAuth2 authentication | Initial credential setup (already configured) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| google-ads Python client | Direct REST API calls | Client handles pagination, streaming, retries, error mapping - REST is lower-level and brittle |
| google-ads Python client | Google Ads MCP | MCP useful for ad-hoc queries in Cursor, but Python client better for production pipelines |

**Installation:**
```bash
pip install google-ads google-api-core
```

**Configuration:**
Already configured in `src/feedops/integrations/google_ads_performance.py` with environment variable and file-based config support.

## Architecture Patterns

### Pattern 1: Schema Discovery (New)

**What:** Use GoogleAdsFieldService to programmatically discover field metadata (selectable, filterable, sortable, data type).

**When to use:** Building dynamic queries, validating field compatibility, generating documentation.

**Example:**
```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage()
field_service = client.get_service("GoogleAdsFieldService")

# Search for fields
request = client.get_type("SearchGoogleAdsFieldsRequest")
request.query = """
  SELECT
    name,
    category,
    selectable,
    filterable,
    sortable,
    data_type,
    is_repeated
  WHERE name LIKE 'segments.product%'
"""

response = field_service.search_google_ads_fields(request=request)

for field in response:
    print(f"{field.name}: {field.data_type.name} "
          f"(S:{field.selectable}, F:{field.filterable}, So:{field.sortable})")
```

**Output:**
```
segments.product_item_id: STRING (S:True, F:True, So:True)
segments.product_custom_attribute0: STRING (S:True, F:True, So:True)
segments.product_brand: STRING (S:True, F:True, So:True)
...
```

### Pattern 2: Custom Label Segmentation

**What:** Filter and segment by custom labels for category/tier analysis.

**When to use:** Analyzing specific product categories without building long IN clauses.

**Example:**
```python
query = f"""
SELECT
  segments.product_custom_attribute0,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  metrics.conversions_value
FROM shopping_performance_view
WHERE
  segments.product_custom_attribute0 IN ('Towel Bars', 'Towel Rings', 'Robe Hooks')
  AND segments.date BETWEEN '2025-01-01' AND '2025-12-31'
ORDER BY segments.product_custom_attribute0, segments.