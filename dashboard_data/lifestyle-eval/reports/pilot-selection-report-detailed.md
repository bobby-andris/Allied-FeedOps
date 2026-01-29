# Pilot SKU Selection Detailed Rationale (Ads 30d + GA4 30/90d)

## Scope

- Goal: select 40 MasterSKUs for a low-risk, learnable optimization pilot.
- Optimization unit: MasterSKU aggregated from variant item_ids.
- Selected list: `data/pilot_sku_selection/selected_master_skus.txt` (40 MasterSKUs).
- Control group: `data/pilot_sku_selection/control_master_skus.txt` (16 MasterSKUs).

## Data sources and mappings

- Google Ads (MCP) 30d Shopping performance by `segments.product_item_id`:
  - `data/pilot_sku_selection/ads_30d_top_impressions.jsonl`
  - `data/pilot_sku_selection/ads_30d_top_clicks.jsonl`
  - `data/pilot_sku_selection/ads_30d_top_conv_value.jsonl`
- GA4 (MCP) item performance from Shopify property:
  - `data/pilot_sku_selection/ga4_30d.jsonl`
  - `data/pilot_sku_selection/ga4_90d.jsonl`
  - Source/medium filter removed due to GA4 compatibility; values reflect all traffic.
- Catalog mapping for aggregation and metadata:
  - `data/pilot_sku_selection/candidate_items.csv` (item_id -> MasterSKU + category/collection)
- Tier labels and baseline summary:
  - `dashboard_data/lifestyle-eval-candidate/reports/pilot-selection-report.md`

## Applied selection logic (as executed)

- Traffic filter relaxed to impressions >= 0 and clicks >= 0 due to account size.
- Excluded top-5 by GA4 90d revenue to limit revenue risk:
  - CL-55, FR-23, TD-23, CL-28-30, CL-54
- Tiering strategy used for balance:
  - Tier1: high conversion efficiency, low count (risk-managed winners).
  - Tier2: mid-pack performance, primary test bed.
  - Tier3: high traffic with low efficiency (largest upside).
  - Fill: used to reach 40 SKUs while maintaining category coverage.
- Diversity summary (selected set):
  - 24 categories represented (largest: Glass Shelves = 7, Towel Bars = 4).
  - Additional notable categories: Assorted Free Standing Accessories (3), Freestanding Toilet Tissue Stands (3).

## Calculation notes

- Cost = `metrics.cost_micros / 1,000,000`
- CTR = clicks / impressions
- CVR = conversions / clicks
- ROAS = conversion_value / cost
- CPC = cost / clicks
- CPA = cost / conversions
- Percentile ranks computed within the selected 40-SKU set for: impressions, clicks, CVR, ROAS, conversion value.

## SKU-level rationale

### SKU: 920D-6

- Tier: Tier1
- Category: Multi Hooks
- Collection: Mercury
- Variant item_ids used (1): shopify_us_4538762494084_32096757710980

Ads 30d (Google Shopping):

- Impressions: 2
- Clicks: 1
- CTR: 50.00%
- Cost: $0.40
- CPC: $0.40
- Conversions: 2.00
- CVR: 200.00%
- Conversion value: $1,270.00
- Conversion value per click: $1,270.00
- Conversion value per impression: $635.00
- ROAS: 3175.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 5.0%
- Clicks percentile: 12.5%
- CVR percentile: 100.0%
- ROAS percentile: 100.0%
- Conversion value percentile: 92.5%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 5.0% / 12.5%).
- Efficiency band is high (CVR/ROAS percentiles: 100.0% / 100.0%).
- Tier1 selection prioritizes high efficiency with limited risk exposure; this SKU fits the high-efficiency profile without being in the top GA4 revenue exclusions.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection coverage in the final 40-SKU mix.

### SKU: CL-41-30

- Tier: Tier1
- Category: Towel Bars
- Collection: Carolina
- Variant item_ids used (1): shopify_us_4542499979396_32116325384324

Ads 30d (Google Shopping):

- Impressions: 74
- Clicks: 1
- CTR: 1.35%
- Cost: $4.14
- CPC: $4.14
- Conversions: 1.00
- CVR: 100.00%
- Conversion value: $357.00
- Conversion value per click: $357.00
- Conversion value per impression: $4.82
- ROAS: 86.23

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 12.5%
- Clicks percentile: 12.5%
- CVR percentile: 97.5%
- ROAS percentile: 92.5%
- Conversion value percentile: 40.0%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 12.5% / 12.5%).
- Efficiency band is high (CVR/ROAS percentiles: 97.5% / 92.5%).
- Tier1 selection prioritizes high efficiency with limited risk exposure; this SKU fits the high-efficiency profile without being in the top GA4 revenue exclusions.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: P-550-WPT

- Tier: Tier1
- Category: Paper Towel Holders
- Collection: Pipeline
- Variant item_ids used (1): shopify_us_4545081081988_43093829714146

Ads 30d (Google Shopping):

- Impressions: 48
- Clicks: 1
- CTR: 2.08%
- Cost: $3.83
- CPC: $3.83
- Conversions: 1.00
- CVR: 100.00%
- Conversion value: $404.25
- Conversion value per click: $404.25
- Conversion value per impression: $8.42
- ROAS: 105.55

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 12
- 90d item revenue: $970.20

Relative position among selected SKUs (percentile):

- Impressions percentile: 10.0%
- Clicks percentile: 12.5%
- CVR percentile: 97.5%
- ROAS percentile: 95.0%
- Conversion value percentile: 47.5%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 10.0% / 12.5%).
- Efficiency band is high (CVR/ROAS percentiles: 97.5% / 95.0%).
- Tier1 selection prioritizes high efficiency with limited risk exposure; this SKU fits the high-efficiency profile without being in the top GA4 revenue exclusions.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: QN-31/30

- Tier: Tier1
- Category: Towel Bars
- Collection: Que New
- Variant item_ids used (1): shopify_us_4542622630020_32116946337924

Ads 30d (Google Shopping):

- Impressions: 9
- Clicks: 1
- CTR: 11.11%
- Cost: $9.59
- CPC: $9.59
- Conversions: 1.00
- CVR: 100.00%
- Conversion value: $423.50
- Conversion value per click: $423.50
- Conversion value per impression: $47.06
- ROAS: 44.16

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 7.5%
- Clicks percentile: 12.5%
- CVR percentile: 97.5%
- ROAS percentile: 87.5%
- Conversion value percentile: 52.5%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 7.5% / 12.5%).
- Efficiency band is high (CVR/ROAS percentiles: 97.5% / 87.5%).
- Tier1 selection prioritizes high efficiency with limited risk exposure; this SKU fits the high-efficiency profile without being in the top GA4 revenue exclusions.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection coverage in the final 40-SKU mix.

### SKU: SH-84

- Tier: Tier1
- Category: Assorted Free Standing Accessories
- Collection: Soho
- Variant item_ids used (1): shopify_us_4544976748676_32128185139332

Ads 30d (Google Shopping):

- Impressions: 2
- Clicks: 1
- CTR: 50.00%
- Cost: $1.34
- CPC: $1.34
- Conversions: 1.00
- CVR: 100.00%
- Conversion value: $785.40
- Conversion value per click: $785.40
- Conversion value per impression: $392.70
- ROAS: 586.12

GA4 (Shopify):

- 30d items purchased: 2
- 30d item revenue: $785.40
- 90d items purchased: 2
- 90d item revenue: $785.40

Relative position among selected SKUs (percentile):

- Impressions percentile: 5.0%
- Clicks percentile: 12.5%
- CVR percentile: 97.5%
- ROAS percentile: 97.5%
- Conversion value percentile: 77.5%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 5.0% / 12.5%).
- Efficiency band is high (CVR/ROAS percentiles: 97.5% / 97.5%).
- Tier1 selection prioritizes high efficiency with limited risk exposure; this SKU fits the high-efficiency profile without being in the top GA4 revenue exclusions.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category representation and collection coverage in the final 40-SKU mix.

### SKU: CV-407-8SM

- Tier: Tier1
- Category: Shower Door Hardware
- Collection: Clearview
- Variant item_ids used (1): shopify_us_4544675741828_37929912991912

Ads 30d (Google Shopping):

- Impressions: 125
- Clicks: 2
- CTR: 1.60%
- Cost: $15.49
- CPC: $7.75
- Conversions: 1.33
- CVR: 66.67%
- Conversion value: $786.68
- Conversion value per click: $393.34
- Conversion value per impression: $6.29
- ROAS: 50.79

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 15.0%
- Clicks percentile: 15.0%
- CVR percentile: 87.5%
- ROAS percentile: 90.0%
- Conversion value percentile: 80.0%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 15.0% / 15.0%).
- Efficiency band is high (CVR/ROAS percentiles: 87.5% / 90.0%).
- Tier1 selection prioritizes high efficiency with limited risk exposure; this SKU fits the high-efficiency profile without being in the top GA4 revenue exclusions.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection coverage in the final 40-SKU mix.

### SKU: CL-29

- Tier: Tier2
- Category: Freestanding Toilet Tissue Stands
- Collection: Carolina
- Variant item_ids used (1): shopify_us_4543014273156_32119561453700

Ads 30d (Google Shopping):

- Impressions: 427
- Clicks: 10
- CTR: 2.34%
- Cost: $13.62
- CPC: $1.36
- Conversions: 1.50
- CVR: 15.00%
- Conversion value: $481.25
- Conversion value per click: $48.12
- Conversion value per impression: $1.13
- ROAS: 35.33

GA4 (Shopify):

- 30d items purchased: 3
- 30d item revenue: $577.50
- 90d items purchased: 7
- 90d item revenue: $1,347.50

Relative position among selected SKUs (percentile):

- Impressions percentile: 17.5%
- Clicks percentile: 25.0%
- CVR percentile: 72.5%
- ROAS percentile: 85.0%
- Conversion value percentile: 62.5%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 17.5% / 25.0%).
- Efficiency band is high (CVR/ROAS percentiles: 72.5% / 85.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: FT-16

- Tier: Tier2
- Category: Towel Rings
- Collection: Foxtrot
- Variant item_ids used (2): shopify_us_4545450475652_32130384560260, shopify_us_4545450475652_43093698412770

Ads 30d (Google Shopping):

- Impressions: 3987
- Clicks: 49
- CTR: 1.23%
- Cost: $41.35
- CPC: $0.84
- Conversions: 8.00
- CVR: 16.33%
- Conversion value: $1,278.61
- Conversion value per click: $26.09
- Conversion value per impression: $0.32
- ROAS: 30.92

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 1
- 90d item revenue: $40.04

Relative position among selected SKUs (percentile):

- Impressions percentile: 82.5%
- Clicks percentile: 87.5%
- CVR percentile: 75.0%
- ROAS percentile: 82.5%
- Conversion value percentile: 95.0%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 82.5% / 87.5%).
- Efficiency band is high (CVR/ROAS percentiles: 75.0% / 82.5%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection coverage in the final 40-SKU mix.

### SKU: MB-20

- Tier: Tier2
- Category: Robe Hooks
- Collection: Malibu
- Variant item_ids used (2): shopify_us_7924786331874_43539420774626, shopify_us_7924786331874_43539420840162

Ads 30d (Google Shopping):

- Impressions: 2736
- Clicks: 30
- CTR: 1.10%
- Cost: $39.40
- CPC: $1.31
- Conversions: 5.00
- CVR: 16.67%
- Conversion value: $1,094.89
- Conversion value per click: $36.50
- Conversion value per impression: $0.40
- ROAS: 27.79

GA4 (Shopify):

- 30d items purchased: 2
- 30d item revenue: $54.00
- 90d items purchased: 8
- 90d item revenue: $216.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 70.0%
- Clicks percentile: 67.5%
- CVR percentile: 80.0%
- ROAS percentile: 80.0%
- Conversion value percentile: 87.5%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 70.0% / 67.5%).
- Efficiency band is high (CVR/ROAS percentiles: 80.0% / 80.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection coverage in the final 40-SKU mix.

### SKU: CL-11

- Tier: Tier2
- Category: Guest Towel Holders
- Collection: Carolina
- Variant item_ids used (2): shopify_us_4543084265604_32120233361540, shopify_us_4543084265604_32120233492612

Ads 30d (Google Shopping):

- Impressions: 3049
- Clicks: 21
- CTR: 0.69%
- Cost: $40.72
- CPC: $1.94
- Conversions: 4.00
- CVR: 19.03%
- Conversion value: $1,071.63
- Conversion value per click: $51.03
- Conversion value per impression: $0.35
- ROAS: 26.32

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 4
- 90d item revenue: $772.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 75.0%
- Clicks percentile: 42.5%
- CVR percentile: 82.5%
- ROAS percentile: 77.5%
- Conversion value percentile: 85.0%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 75.0% / 42.5%).
- Efficiency band is high (CVR/ROAS percentiles: 82.5% / 77.5%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: 1051

- Tier: Tier2
- Category: Paper Towel Holders
- Collection: Unassigned
- Variant item_ids used (1): shopify_us_4545063682180_32128479821956

Ads 30d (Google Shopping):

- Impressions: 504
- Clicks: 12
- CTR: 2.38%
- Cost: $17.32
- CPC: $1.44
- Conversions: 2.00
- CVR: 16.67%
- Conversion value: $438.90
- Conversion value per click: $36.57
- Conversion value per impression: $0.87
- ROAS: 25.34

GA4 (Shopify):

- 30d items purchased: 1
- 30d item revenue: $146.30
- 90d items purchased: 1
- 90d item revenue: $146.30

Relative position among selected SKUs (percentile):

- Impressions percentile: 22.5%
- Clicks percentile: 30.0%
- CVR percentile: 80.0%
- ROAS percentile: 75.0%
- Conversion value percentile: 55.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 22.5% / 30.0%).
- Efficiency band is high (CVR/ROAS percentiles: 80.0% / 75.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: WP-GLT-24

- Tier: Tier2
- Category: Toilet Paper Holders
- Collection: Waverly Place
- Variant item_ids used (1): shopify_us_4545335558276_32130019328132

Ads 30d (Google Shopping):

- Impressions: 640
- Clicks: 7
- CTR: 1.09%
- Cost: $17.73
- CPC: $2.53
- Conversions: 1.00
- CVR: 14.29%
- Conversion value: $419.65
- Conversion value per click: $59.95
- Conversion value per impression: $0.66
- ROAS: 23.67

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 30.0%
- Clicks percentile: 17.5%
- CVR percentile: 70.0%
- ROAS percentile: 72.5%
- Conversion value percentile: 50.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 30.0% / 17.5%).
- Efficiency band is mid (CVR/ROAS percentiles: 70.0% / 72.5%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: CL-41-18

- Tier: Tier2
- Category: Towel Bars
- Collection: Carolina
- Variant item_ids used (1): shopify_us_4542499979396_32116324270212

Ads 30d (Google Shopping):

- Impressions: 604
- Clicks: 8
- CTR: 1.32%
- Cost: $18.78
- CPC: $2.35
- Conversions: 1.00
- CVR: 12.50%
- Conversion value: $392.70
- Conversion value per click: $49.09
- Conversion value per impression: $0.65
- ROAS: 20.91

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 1
- 90d item revenue: $168.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 25.0%
- Clicks percentile: 20.0%
- CVR percentile: 67.5%
- ROAS percentile: 70.0%
- Conversion value percentile: 45.0%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 25.0% / 20.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 67.5% / 70.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: HTL-3

- Tier: Tier2
- Category: Towel Shelves
- Collection: Unassigned
- Variant item_ids used (2): shopify_us_4545516241028_32130727641220, shopify_us_4545516241028_32130727673988

Ads 30d (Google Shopping):

- Impressions: 4422
- Clicks: 38
- CTR: 0.86%
- Cost: $69.72
- CPC: $1.83
- Conversions: 2.50
- CVR: 6.58%
- Conversion value: $1,291.30
- Conversion value per click: $33.98
- Conversion value per impression: $0.29
- ROAS: 18.52

GA4 (Shopify):

- 30d items purchased: 3
- 30d item revenue: $831.60
- 90d items purchased: 4
- 90d item revenue: $1,108.80

Relative position among selected SKUs (percentile):

- Impressions percentile: 87.5%
- Clicks percentile: 77.5%
- CVR percentile: 52.5%
- ROAS percentile: 65.0%
- Conversion value percentile: 97.5%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 87.5% / 77.5%).
- Efficiency band is mid (CVR/ROAS percentiles: 52.5% / 65.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: TS-4L

- Tier: Tier2
- Category: Assorted Free Standing Accessories
- Collection: Unassigned
- Variant item_ids used (2): shopify_us_4544991723652_32128217841796, shopify_us_4544991723652_32128218103940

Ads 30d (Google Shopping):

- Impressions: 801
- Clicks: 16
- CTR: 2.00%
- Cost: $40.66
- CPC: $2.54
- Conversions: 2.00
- CVR: 12.50%
- Conversion value: $719.95
- Conversion value per click: $45.00
- Conversion value per impression: $0.90
- ROAS: 17.71

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 32.5%
- Clicks percentile: 32.5%
- CVR percentile: 67.5%
- ROAS percentile: 62.5%
- Conversion value percentile: 72.5%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 32.5% / 32.5%).
- Efficiency band is mid (CVR/ROAS percentiles: 67.5% / 62.5%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: MA-26

- Tier: Tier2
- Category: Tumbler Toothbrush Holders
- Collection: Mambo
- Variant item_ids used (1): shopify_us_4545561526404_32131127607428

Ads 30d (Google Shopping):

- Impressions: 1192
- Clicks: 18
- CTR: 1.51%
- Cost: $11.03
- CPC: $0.61
- Conversions: 2.00
- CVR: 11.11%
- Conversion value: $167.86
- Conversion value per click: $9.33
- Conversion value per impression: $0.14
- ROAS: 15.22

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 37.5%
- Clicks percentile: 40.0%
- CVR percentile: 62.5%
- ROAS percentile: 60.0%
- Conversion value percentile: 27.5%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 37.5% / 40.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 62.5% / 60.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection coverage in the final 40-SKU mix.

### SKU: WP-61

- Tier: Tier2
- Category: Soap Dispensers
- Collection: Waverly Place
- Variant item_ids used (1): shopify_us_4545142784132_32128934969476

Ads 30d (Google Shopping):

- Impressions: 436
- Clicks: 10
- CTR: 2.29%
- Cost: $51.60
- CPC: $5.16
- Conversions: 2.00
- CVR: 20.00%
- Conversion value: $746.90
- Conversion value per click: $74.69
- Conversion value per impression: $1.71
- ROAS: 14.47

GA4 (Shopify):

- 30d items purchased: 2
- 30d item revenue: $277.20
- 90d items purchased: 2
- 90d item revenue: $277.20

Relative position among selected SKUs (percentile):

- Impressions percentile: 20.0%
- Clicks percentile: 25.0%
- CVR percentile: 85.0%
- ROAS percentile: 57.5%
- Conversion value percentile: 75.0%

Selection rationale:

- Traffic band is low (impressions/clicks percentiles: 20.0% / 25.0%).
- Efficiency band is high (CVR/ROAS percentiles: 85.0% / 57.5%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: CS-1

- Tier: Tier2
- Category: Assorted Free Standing Accessories
- Collection: Unassigned
- Variant item_ids used (2): shopify_us_4544951648388_32128137658500, shopify_us_4544951648388_43093852291298

Ads 30d (Google Shopping):

- Impressions: 1895
- Clicks: 12
- CTR: 0.63%
- Cost: $41.64
- CPC: $3.47
- Conversions: 1.00
- CVR: 8.33%
- Conversion value: $481.25
- Conversion value per click: $40.10
- Conversion value per impression: $0.25
- ROAS: 11.56

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 52.5%
- Clicks percentile: 30.0%
- CVR percentile: 57.5%
- ROAS percentile: 52.5%
- Conversion value percentile: 62.5%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 52.5% / 30.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 57.5% / 52.5%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: WP-2TB/16-GAL

- Tier: Tier2
- Category: Glass Shelves
- Collection: Waverly Place
- Variant item_ids used (4): shopify_us_4543468830852_32123055145092, shopify_us_4543468830852_32123055538308, shopify_us_4543468830852_32123055603844, shopify_us_4543468830852_32123055931524

Ads 30d (Google Shopping):

- Impressions: 11482
- Clicks: 113
- CTR: 0.98%
- Cost: $187.27
- CPC: $1.66
- Conversions: 8.01
- CVR: 7.09%
- Conversion value: $1,977.74
- Conversion value per click: $17.50
- Conversion value per impression: $0.17
- ROAS: 10.56

GA4 (Shopify):

- 30d items purchased: 1
- 30d item revenue: $211.75
- 90d items purchased: 2
- 90d item revenue: $423.50

Relative position among selected SKUs (percentile):

- Impressions percentile: 97.5%
- Clicks percentile: 97.5%
- CVR percentile: 55.0%
- ROAS percentile: 47.5%
- Conversion value percentile: 100.0%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 97.5% / 97.5%).
- Efficiency band is mid (CVR/ROAS percentiles: 55.0% / 47.5%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: PR-99

- Tier: Tier2
- Category: Shower Curtain Brackets and Rods
- Collection: Prestige Regal
- Variant item_ids used (1): shopify_us_4540068855940_32103798374532

Ads 30d (Google Shopping):

- Impressions: 1634
- Clicks: 18
- CTR: 1.10%
- Cost: $32.58
- CPC: $1.81
- Conversions: 1.00
- CVR: 5.56%
- Conversion value: $238.70
- Conversion value per click: $13.26
- Conversion value per impression: $0.15
- ROAS: 7.33

GA4 (Shopify):

- 30d items purchased: 1
- 30d item revenue: $107.80
- 90d items purchased: 6
- 90d item revenue: $646.80

Relative position among selected SKUs (percentile):

- Impressions percentile: 45.0%
- Clicks percentile: 40.0%
- CVR percentile: 45.0%
- ROAS percentile: 35.0%
- Conversion value percentile: 32.5%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 45.0% / 40.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 45.0% / 35.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection coverage in the final 40-SKU mix.

### SKU: P-730-GB360

- Tier: Tier2
- Category: Grab Bars
- Collection: Pipeline
- Variant item_ids used (1): shopify_us_8033759002850_43853036617954

Ads 30d (Google Shopping):

- Impressions: 632
- Clicks: 17
- CTR: 2.69%
- Cost: $36.26
- CPC: $2.13
- Conversions: 1.00
- CVR: 5.88%
- Conversion value: $386.20
- Conversion value per click: $22.72
- Conversion value per impression: $0.61
- ROAS: 10.65

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 27.5%
- Clicks percentile: 35.0%
- CVR percentile: 50.0%
- ROAS percentile: 50.0%
- Conversion value percentile: 42.5%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 27.5% / 35.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 50.0% / 50.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: BSK-275LA

- Tier: Tier2
- Category: Baskets
- Collection: Unassigned
- Variant item_ids used (2): shopify_us_4531833766020_32063606489220, shopify_us_4531833766020_32063606587524

Ads 30d (Google Shopping):

- Impressions: 1702
- Clicks: 25
- CTR: 1.47%
- Cost: $54.53
- CPC: $2.18
- Conversions: 2.50
- CVR: 10.00%
- Conversion value: $509.36
- Conversion value per click: $20.37
- Conversion value per impression: $0.30
- ROAS: 9.34

GA4 (Shopify):

- 30d items purchased: 1
- 30d item revenue: $157.85
- 90d items purchased: 4
- 90d item revenue: $631.40

Relative position among selected SKUs (percentile):

- Impressions percentile: 50.0%
- Clicks percentile: 55.0%
- CVR percentile: 60.0%
- ROAS percentile: 45.0%
- Conversion value percentile: 65.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 50.0% / 55.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 60.0% / 45.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: WP-1TB/16

- Tier: Tier2
- Category: Glass Shelves
- Collection: Waverly Place
- Variant item_ids used (1): shopify_us_4543457788036_32123003437188

Ads 30d (Google Shopping):

- Impressions: 3677
- Clicks: 34
- CTR: 0.92%
- Cost: $36.87
- CPC: $1.08
- Conversions: 2.00
- CVR: 5.88%
- Conversion value: $315.24
- Conversion value per click: $9.27
- Conversion value per impression: $0.09
- ROAS: 8.55

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 4
- 90d item revenue: $523.60

Relative position among selected SKUs (percentile):

- Impressions percentile: 80.0%
- Clicks percentile: 72.5%
- CVR percentile: 50.0%
- ROAS percentile: 40.0%
- Conversion value percentile: 37.5%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 80.0% / 72.5%).
- Efficiency band is mid (CVR/ROAS percentiles: 50.0% / 40.0%).
- Tier2 selection targets mid-pack performance with dependable traffic for learnable tests; this SKU sits in the mid-range while keeping revenue risk manageable.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: WP-2/22-GAL

- Tier: Tier3
- Category: Glass Shelves
- Collection: Waverly Place
- Variant item_ids used (2): shopify_us_4543465947268_32123035648132, shopify_us_4543465947268_32123035811972

Ads 30d (Google Shopping):

- Impressions: 7911
- Clicks: 89
- CTR: 1.13%
- Cost: $104.01
- CPC: $1.17
- Conversions: 0.00
- CVR: 0.00%
- Conversion value: $0.00
- Conversion value per click: $0.00
- Conversion value per impression: $0.00
- ROAS: 0.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 95.0%
- Clicks percentile: 95.0%
- CVR percentile: 20.0%
- ROAS percentile: 20.0%
- Conversion value percentile: 20.0%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 95.0% / 95.0%).
- Efficiency band is low (CVR/ROAS percentiles: 20.0% / 20.0%).
- Tier3 selection targets high-traffic, low-efficiency items for upside; this SKU shows volume with weaker conversion efficiency, making it a good optimization candidate.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: WP-GTB-2

- Tier: Tier3
- Category: Assorted Wall Accessories
- Collection: Waverly Place
- Variant item_ids used (2): shopify_us_4542830280836_32117943238788, shopify_us_4542830280836_32117943369860

Ads 30d (Google Shopping):

- Impressions: 6344
- Clicks: 81
- CTR: 1.28%
- Cost: $89.39
- CPC: $1.10
- Conversions: 1.17
- CVR: 1.44%
- Conversion value: $800.09
- Conversion value per click: $9.88
- Conversion value per impression: $0.13
- ROAS: 8.95

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 90.0%
- Clicks percentile: 90.0%
- CVR percentile: 25.0%
- ROAS percentile: 42.5%
- Conversion value percentile: 82.5%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 90.0% / 90.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 25.0% / 42.5%).
- Tier3 selection targets high-traffic, low-efficiency items for upside; this SKU shows volume with weaker conversion efficiency, making it a good optimization candidate.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: CL-22

- Tier: Tier3
- Category: Retractable Hooks and Garment Rods
- Collection: Carolina
- Variant item_ids used (1): shopify_us_7721205235938_42803121062114

Ads 30d (Google Shopping):

- Impressions: 3477
- Clicks: 48
- CTR: 1.38%
- Cost: $65.83
- CPC: $1.37
- Conversions: 0.33
- CVR: 0.69%
- Conversion value: $89.83
- Conversion value per click: $1.87
- Conversion value per impression: $0.03
- ROAS: 1.36

GA4 (Shopify):

- 30d items purchased: 2
- 30d item revenue: $161.00
- 90d items purchased: 3
- 90d item revenue: $241.50

Relative position among selected SKUs (percentile):

- Impressions percentile: 77.5%
- Clicks percentile: 85.0%
- CVR percentile: 22.5%
- ROAS percentile: 22.5%
- Conversion value percentile: 22.5%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 77.5% / 85.0%).
- Efficiency band is low (CVR/ROAS percentiles: 22.5% / 22.5%).
- Tier3 selection targets high-traffic, low-efficiency items for upside; this SKU shows volume with weaker conversion efficiency, making it a good optimization candidate.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: A-20

- Tier: Tier3
- Category: Cabinet Hardware
- Collection: Cabinet Hardware
- Variant item_ids used (1): shopify_us_4542922064004_43093937062114

Ads 30d (Google Shopping):

- Impressions: 2417
- Clicks: 43
- CTR: 1.78%
- Cost: $25.37
- CPC: $0.59
- Conversions: 0.00
- CVR: 0.00%
- Conversion value: $0.00
- Conversion value per click: $0.00
- Conversion value per impression: $0.00
- ROAS: 0.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 62.5%
- Clicks percentile: 82.5%
- CVR percentile: 20.0%
- ROAS percentile: 20.0%
- Conversion value percentile: 20.0%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 62.5% / 82.5%).
- Efficiency band is low (CVR/ROAS percentiles: 20.0% / 20.0%).
- Tier3 selection targets high-traffic, low-efficiency items for upside; this SKU shows volume with weaker conversion efficiency, making it a good optimization candidate.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection coverage in the final 40-SKU mix.

### SKU: CL-5-16

- Tier: Tier3
- Category: Glass Shelves
- Collection: Carolina
- Variant item_ids used (1): shopify_us_4543237914756_32121076908164

Ads 30d (Google Shopping):

- Impressions: 1598
- Clicks: 29
- CTR: 1.81%
- Cost: $48.91
- CPC: $1.69
- Conversions: 0.50
- CVR: 1.72%
- Conversion value: $96.25
- Conversion value per click: $3.32
- Conversion value per impression: $0.06
- ROAS: 1.97

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 42.5%
- Clicks percentile: 65.0%
- CVR percentile: 27.5%
- ROAS percentile: 25.0%
- Conversion value percentile: 25.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 42.5% / 65.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 27.5% / 25.0%).
- Tier3 selection targets high-traffic, low-efficiency items for upside; this SKU shows volume with weaker conversion efficiency, making it a good optimization candidate.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: WP-2/16-GAL

- Tier: Fill
- Category: Glass Shelves
- Collection: Waverly Place
- Variant item_ids used (5): shopify_us_4543465947268_32123035123844, shopify_us_4543465947268_32123035287684, shopify_us_4543465947268_32123035451524, shopify_us_4543465947268_32123035484292, shopify_us_4543465947268_43098502529250

Ads 30d (Google Shopping):

- Impressions: 11946
- Clicks: 123
- CTR: 1.03%
- Cost: $174.92
- CPC: $1.42
- Conversions: 4.83
- CVR: 3.93%
- Conversion value: $1,136.25
- Conversion value per click: $9.24
- Conversion value per impression: $0.10
- ROAS: 6.50

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 100.0%
- Clicks percentile: 100.0%
- CVR percentile: 40.0%
- ROAS percentile: 32.5%
- Conversion value percentile: 90.0%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 100.0% / 100.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 40.0% / 32.5%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: MD-22

- Tier: Fill
- Category: Retractable Hooks and Garment Rods
- Collection: Unassigned
- Variant item_ids used (2): shopify_us_7721205596386_42803122307298, shopify_us_7721205596386_42803122340066

Ads 30d (Google Shopping):

- Impressions: 6592
- Clicks: 83
- CTR: 1.26%
- Cost: $81.85
- CPC: $0.99
- Conversions: 2.17
- CVR: 2.61%
- Conversion value: $603.50
- Conversion value per click: $7.27
- Conversion value per impression: $0.09
- ROAS: 7.37

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 9
- 90d item revenue: $666.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 92.5%
- Clicks percentile: 92.5%
- CVR percentile: 32.5%
- ROAS percentile: 37.5%
- Conversion value percentile: 70.0%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 92.5% / 92.5%).
- Efficiency band is mid (CVR/ROAS percentiles: 32.5% / 37.5%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: P-200-18-TB

- Tier: Fill
- Category: Towel Bars
- Collection: Pipeline
- Variant item_ids used (1): shopify_us_4542573609092_32116664991876

Ads 30d (Google Shopping):

- Impressions: 2872
- Clicks: 41
- CTR: 1.43%
- Cost: $39.15
- CPC: $0.95
- Conversions: 1.00
- CVR: 2.44%
- Conversion value: $531.30
- Conversion value per click: $12.96
- Conversion value per impression: $0.18
- ROAS: 13.57

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 72.5%
- Clicks percentile: 80.0%
- CVR percentile: 30.0%
- ROAS percentile: 55.0%
- Conversion value percentile: 67.5%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 72.5% / 80.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 30.0% / 55.0%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: SQ-20

- Tier: Fill
- Category: Squeegee
- Collection: Unassigned
- Variant item_ids used (2): shopify_us_4538723762308_32096366297220, shopify_us_4538723762308_32096366559364

Ads 30d (Google Shopping):

- Impressions: 4219
- Clicks: 36
- CTR: 0.85%
- Cost: $49.93
- CPC: $1.39
- Conversions: 1.00
- CVR: 2.78%
- Conversion value: $293.10
- Conversion value per click: $8.14
- Conversion value per impression: $0.07
- ROAS: 5.87

GA4 (Shopify):

- 30d items purchased: 2
- 30d item revenue: $200.20
- 90d items purchased: 8
- 90d item revenue: $800.80

Relative position among selected SKUs (percentile):

- Impressions percentile: 85.0%
- Clicks percentile: 75.0%
- CVR percentile: 35.0%
- ROAS percentile: 27.5%
- Conversion value percentile: 35.0%

Selection rationale:

- Traffic band is high (impressions/clicks percentiles: 85.0% / 75.0%).
- Efficiency band is mid (CVR/ROAS percentiles: 35.0% / 27.5%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: RC-5/16TB

- Tier: Fill
- Category: Glass Shelves
- Collection: Unassigned
- Variant item_ids used (1): shopify_us_4543385174148_32122228146308

Ads 30d (Google Shopping):

- Impressions: 2480
- Clicks: 34
- CTR: 1.37%
- Cost: $37.04
- CPC: $1.09
- Conversions: 1.49
- CVR: 4.39%
- Conversion value: $233.83
- Conversion value per click: $6.88
- Conversion value per impression: $0.09
- ROAS: 6.31

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 2
- 90d item revenue: $292.60

Relative position among selected SKUs (percentile):

- Impressions percentile: 65.0%
- Clicks percentile: 72.5%
- CVR percentile: 42.5%
- ROAS percentile: 30.0%
- Conversion value percentile: 30.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 65.0% / 72.5%).
- Efficiency band is mid (CVR/ROAS percentiles: 42.5% / 30.0%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: DMF-2/2X

- Tier: Fill
- Category: Make-Up Mirrors
- Collection: Unassigned
- Variant item_ids used (1): shopify_us_4539975336068_32103132627076

Ads 30d (Google Shopping):

- Impressions: 2305
- Clicks: 28
- CTR: 1.21%
- Cost: $23.20
- CPC: $0.83
- Conversions: 1.00
- CVR: 3.57%
- Conversion value: $465.85
- Conversion value per click: $16.64
- Conversion value per impression: $0.20
- ROAS: 20.08

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 60.0%
- Clicks percentile: 62.5%
- CVR percentile: 37.5%
- ROAS percentile: 67.5%
- Conversion value percentile: 57.5%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 60.0% / 62.5%).
- Efficiency band is mid (CVR/ROAS percentiles: 37.5% / 67.5%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: TS-25

- Tier: Fill
- Category: Freestanding Toilet Tissue Stands
- Collection: Unassigned
- Variant item_ids used (1): shopify_us_4543040258180_43098796294370

Ads 30d (Google Shopping):

- Impressions: 2075
- Clicks: 28
- CTR: 1.35%
- Cost: $40.91
- CPC: $1.46
- Conversions: 0.00
- CVR: 0.00%
- Conversion value: $0.00
- Conversion value per click: $0.00
- Conversion value per impression: $0.00
- ROAS: 0.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 57.5%
- Clicks percentile: 62.5%
- CVR percentile: 20.0%
- ROAS percentile: 20.0%
- Conversion value percentile: 20.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 57.5% / 62.5%).
- Efficiency band is low (CVR/ROAS percentiles: 20.0% / 20.0%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: 1066

- Tier: Fill
- Category: Vanity Top Accessories
- Collection: Unassigned
- Variant item_ids used (1): shopify_us_4538728874116_32096432357508

Ads 30d (Google Shopping):

- Impressions: 1317
- Clicks: 26
- CTR: 1.97%
- Cost: $13.32
- CPC: $0.51
- Conversions: 0.00
- CVR: 0.00%
- Conversion value: $0.00
- Conversion value per click: $0.00
- Conversion value per impression: $0.00
- ROAS: 0.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 1
- 90d item revenue: $146.30

Relative position among selected SKUs (percentile):

- Impressions percentile: 40.0%
- Clicks percentile: 57.5%
- CVR percentile: 20.0%
- ROAS percentile: 20.0%
- Conversion value percentile: 20.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 40.0% / 57.5%).
- Efficiency band is low (CVR/ROAS percentiles: 20.0% / 20.0%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: CL-24C

- Tier: Fill
- Category: Toilet Paper Holders
- Collection: Carolina
- Variant item_ids used (1): shopify_us_4545184530564_32129252491396

Ads 30d (Google Shopping):

- Impressions: 2556
- Clicks: 23
- CTR: 0.90%
- Cost: $25.94
- CPC: $1.13
- Conversions: 0.00
- CVR: 0.00%
- Conversion value: $0.00
- Conversion value per click: $0.00
- Conversion value per impression: $0.00
- ROAS: 0.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 67.5%
- Clicks percentile: 52.5%
- CVR percentile: 20.0%
- ROAS percentile: 20.0%
- Conversion value percentile: 20.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 67.5% / 52.5%).
- Efficiency band is low (CVR/ROAS percentiles: 20.0% / 20.0%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category coverage and collection representation in the final 40-SKU mix.

### SKU: DT-32

- Tier: Fill
- Category: Soap Dishes
- Collection: Dottingham
- Variant item_ids used (1): shopify_us_4545106477188_32128750387332

Ads 30d (Google Shopping):

- Impressions: 1956
- Clicks: 23
- CTR: 1.18%
- Cost: $15.42
- CPC: $0.67
- Conversions: 0.00
- CVR: 0.00%
- Conversion value: $0.00
- Conversion value per click: $0.00
- Conversion value per impression: $0.00
- ROAS: 0.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 2
- 90d item revenue: $110.88

Relative position among selected SKUs (percentile):

- Impressions percentile: 55.0%
- Clicks percentile: 52.5%
- CVR percentile: 20.0%
- ROAS percentile: 20.0%
- Conversion value percentile: 20.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 55.0% / 52.5%).
- Efficiency band is low (CVR/ROAS percentiles: 20.0% / 20.0%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows purchase/revenue signal in the last 90 days, indicating real demand beyond Ads alone.
- Provides category coverage and collection coverage in the final 40-SKU mix.

### SKU: NS-5/16

- Tier: Fill
- Category: Glass Shelves
- Collection: Unassigned
- Variant item_ids used (1): shopify_us_4543306236036_32121537659012

Ads 30d (Google Shopping):

- Impressions: 1700
- Clicks: 23
- CTR: 1.35%
- Cost: $10.94
- CPC: $0.48
- Conversions: 0.00
- CVR: 0.00%
- Conversion value: $0.00
- Conversion value per click: $0.00
- Conversion value per impression: $0.00
- ROAS: 0.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 47.5%
- Clicks percentile: 52.5%
- CVR percentile: 20.0%
- ROAS percentile: 20.0%
- Conversion value percentile: 20.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 47.5% / 52.5%).
- Efficiency band is low (CVR/ROAS percentiles: 20.0% / 20.0%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.

### SKU: TS-28

- Tier: Fill
- Category: Freestanding Toilet Tissue Stands
- Collection: Unassigned
- Variant item_ids used (1): shopify_us_4543047925892_43087513747682

Ads 30d (Google Shopping):

- Impressions: 1107
- Clicks: 22
- CTR: 1.99%
- Cost: $21.56
- CPC: $0.98
- Conversions: 0.00
- CVR: 0.00%
- Conversion value: $0.00
- Conversion value per click: $0.00
- Conversion value per impression: $0.00
- ROAS: 0.00

GA4 (Shopify):

- 30d items purchased: 0
- 30d item revenue: $0.00
- 90d items purchased: 0
- 90d item revenue: $0.00

Relative position among selected SKUs (percentile):

- Impressions percentile: 35.0%
- Clicks percentile: 45.0%
- CVR percentile: 20.0%
- ROAS percentile: 20.0%
- Conversion value percentile: 20.0%

Selection rationale:

- Traffic band is mid (impressions/clicks percentiles: 35.0% / 45.0%).
- Efficiency band is low (CVR/ROAS percentiles: 20.0% / 20.0%).
- Fill selection was used to reach 40 SKUs while preserving category diversity; this SKU adds measurable traffic in a category we need represented.
- GA4 shows no revenue in the last 90 days in this extract, reducing revenue-risk exposure while still enabling learning from Ads traffic.
- Provides category representation and collection representation in the final 40-SKU mix.
