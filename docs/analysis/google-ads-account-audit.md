# Google Ads Account Audit — Allied Brass (Customer ID: 6253381786)

**Date**: 2026-02-26
**Purpose**: Parameterize the zero-conversion intent scoring engine with real account data
**Data range**: 90-day lookback (campaigns/CPA), 30-day lookback (search terms/impression share)

---

## 1. Conversion Actions Catalog (19 Total)

### Primary Conversion (included in "conversions" metric)

| # | Name | Type | Category | Counting | In Conversions |
|---|------|------|----------|----------|----------------|
| 1 | Website Purchase | WEBPAGE | PURCHASE | MANY_PER_CLICK | **YES** |

**Only 1 of 19 actions counts toward the "conversions" metric.** This is the primary purchase action.

### Micro-Conversions (contribute to "all_conversions" only)

| # | Name | Type | Category | Classification |
|---|------|------|----------|---------------|
| 2 | Add to Cart | WEBPAGE | ADD_TO_CART | **Add-to-cart** |
| 3 | Begin checkout | WEBPAGE | BEGIN_CHECKOUT | **Begin-checkout** |
| 4 | Analyzify - Product Detail | WEBPAGE | PAGE_VIEW | **Page-view** |
| 5 | LP Micro - 3+ Pages On Site | UA_GOAL | ENGAGEMENT | **Engagement** |
| 6 | LP Micro - 2+ Minutes On Site | UA_GOAL | ENGAGEMENT | **Engagement** |
| 7 | LP Micro - Cart View | UA_GOAL | DEFAULT | **Cart-view (legacy)** |

### Legacy/System Conversions (not directly actionable)

| # | Name | Type | Category | Classification |
|---|------|------|----------|---------------|
| 8 | Transactions (Master - Allied Brass) | UA_TRANSACTION | PURCHASE | Legacy UA purchase (disabled from reporting) |
| 9 | Allied Brass - GA4 (Old) purchase | GA4_PURCHASE | PURCHASE | GA4 purchase (disabled from reporting) |
| 10 | Analyzify - Purchase test pixel | WEBPAGE | PURCHASE | Test/debug pixel |
| 11 | Calls from ads | AD_CALL | PHONE_CALL_LEAD | Phone lead |
| 12 | Clicks to call | GOOGLE_HOSTED | CONTACT | Local click-to-call |
| 13 | Local actions - Website visits | GOOGLE_HOSTED | PAGE_VIEW | GMB website clicks |
| 14 | Local actions - Other engagements | GOOGLE_HOSTED | ENGAGEMENT | GMB engagements |
| 15 | Local actions - Directions | GOOGLE_HOSTED | GET_DIRECTIONS | GMB directions |
| 16 | Store visits | STORE_VISITS | STORE_VISIT | Estimated store visits |
| 17 | YouTube channel subscriptions | UNKNOWN | ENGAGEMENT | YouTube sub |
| 18 | YouTube follow-on views | UNKNOWN | UNKNOWN | YouTube engagement |
| 19 | Android installs (all other apps) | ANDROID_INSTALLS | DOWNLOAD | App install (N/A) |

### Key Insight: Conversions vs All Conversions

- **`metrics.conversions`** = Website Purchase ONLY (597.5 in 90 days)
- **`metrics.all_conversions`** = Website Purchase + all 18 micro-conversions (35,035 in 90 days)
- **Ratio**: ~58.6 all_conversions per 1 purchase conversion
- **For scoring engine**: Use `conversions` for purchase-based CPA; use `all_conversions` for engagement signal density

---

## 2. Average CPA Calculation (90-Day Window)

### Overall Account

| Metric | Value |
|--------|-------|
| Total spend | $38,373.35 |
| Total purchase conversions | 597.5 |
| Total all_conversions | 35,035.4 |
| **Avg CPA (purchase)** | **$64.22** |
| Avg micro-CPA (all_conversions) | $1.10 |

### CPA by Waterfall Tier

| Tier | Spend | Purchase Conv | CPA | All Conv | Micro-CPA | Campaigns |
|------|-------|--------------|-----|----------|-----------|-----------|
| **BRANDED** | $921 | 29.8 | $30.88 | 1,004 | $0.92 | 1 |
| **HIGH** | $28,611 | 435.2 | $65.75 | 27,536 | $1.04 | 61 |
| **MEDIUM** | $5,739 | 90.5 | $63.43 | 4,228 | $1.36 | 60 |
| **LOW** | $3,103 | 42.0 | $73.80 | 2,267 | $1.37 | 60 |

### Observations

1. **HIGH tier dominates spend** (74.6% of total) — consistent with waterfall structure where HIGH is top-of-funnel
2. **CPA across tiers is surprisingly flat** ($63-74) — expected LOW to have lower CPA given high-intent traffic
3. **BRANDED CPA is lowest** ($30.88) — expected for brand-aware shoppers
4. **Micro-conversion density is highest in HIGH** (63.3 micro-conv per purchase) — lots of engagement, few purchases
5. **LOW tier micro-CPA is highest** ($1.37) — fewer micro-conversions per dollar spent

### Recommended Wasted Spend Threshold

Current hardcoded threshold: **$5.00**

Based on account data:
- Average purchase CPA: $64.22
- **Recommended threshold: $96.33 (1.5x avg CPA)**
- Rationale: A search term that has spent 1.5x the average CPA without generating a purchase conversion is likely wasted spend. The current $5 threshold flags too many terms (nearly all terms with any spend).

Alternative thresholds:
- Conservative: $64.22 (1.0x CPA) — only flag after full CPA worth of spend with no conversion
- Moderate: $96.33 (1.5x CPA) — recommended
- Aggressive: $32.11 (0.5x CPA) — flag at half CPA spend

---

## 3. CPC Caps per Ad Group

### Finding: All CPC Caps Are $0.01

Every ad group across all 182 shopping campaigns has a CPC bid of **$0.01** (10,000 micros).

This is consistent with **Target ROAS automated bidding** — when Target ROAS is the bidding strategy, the manual CPC cap is set to a nominal minimum and Smart Bidding handles actual bid amounts.

### Actual CPC from Search Term Data (30-day sample)

| Search Term | Avg CPC |
|-------------|---------|
| recessed toilet paper holder | $1.16 |
| polished nickel paper towel holder | $3.15 |
| brass paper towel holder | $2.21 |
| unlacquered brass paper towel holder | $3.47 |
| valet rod | $1.87 |
| shower squeegee | $2.68 |
| polished nickel toilet paper holder | $0.92 |
| polished brass toilet paper holder | $1.15 |
| antique brass paper towel holder | $3.33 |
| unlacquered brass toilet paper holder | $2.33 |

**Typical CPC range**: $0.92 - $3.47

### Implication for Scoring Engine

The CPC ceiling pressure signal cannot use `ad_group.cpc_bid_micros` (all $0.01). Instead, use **`metrics.average_cpc` from search_term_view** to compute actual CPC relative to tier benchmarks.

---

## 4. Campaign Structure Summary

| Tier | Count | Role |
|------|-------|------|
| HIGH | 61 | Top-of-funnel, broad traffic, highest tROAS setting (constrains bidding) |
| MEDIUM | 60 | Mid-funnel, category/brand terms |
| LOW | 60 | Bottom-of-funnel, high-intent, aggressive bidding (lowest tROAS) |
| BRANDED | 1 | Brand-aware traffic |
| **Total** | **182** | |

Each product group (custom_label_0) has 3 campaigns (HIGH/MEDIUM/LOW) in the waterfall structure.

---

## 5. Behavioral Signal Availability Matrix

Tested on search_term_view for shopping campaigns over last 30 days.

| Signal | Available | Notes |
|--------|-----------|-------|
| `metrics.impressions` | YES | Always populated |
| `metrics.clicks` | YES | Available on all terms with traffic |
| `metrics.average_cpc` | YES | In micros (divide by 1M for dollars) |
| `metrics.conversions` | YES | Purchase conversions only |
| `metrics.all_conversions` | YES | Includes all micro-conversions |
| `metrics.cross_device_conversions` | YES | Available but often 0.0 |

### Key Finding: All 6 Signals Available

All behavioral signals needed for the scoring engine are available on `search_term_view`. This is better than expected — `cross_device_conversions` was flagged as potentially unavailable but it does return data.

### Sample Data (Top 10 Terms by Clicks, 30 days)

| Search Term | Impressions | Clicks | Avg CPC | Conversions | All Conv | Cross-Device |
|-------------|-------------|--------|---------|-------------|----------|--------------|
| recessed toilet paper holder | 6,658 | 43 | $1.16 | 0.99 | 57.7 | 0.0 |
| polished nickel paper towel holder | 2,003 | 41 | $3.15 | 5.74 | 71.5 | 0.3 |
| brass paper towel holder | 2,753 | 34 | $2.21 | 1.50 | 55.9 | 1.9 |
| unlacquered brass paper towel holder | 804 | 22 | $3.47 | 2.00 | 43.5 | 0.0 |
| valet rod | 4,523 | 21 | $1.87 | 1.00 | 45.5 | 0.0 |
| shower squeegee | 3,733 | 20 | $2.68 | 1.00 | 23.0 | 0.0 |
| polished nickel toilet paper holder | 562 | 17 | $0.92 | 1.00 | 27.9 | 0.0 |
| polished brass toilet paper holder | 449 | 15 | $1.15 | 1.93 | 23.0 | 0.3 |
| antique brass paper towel holder | 938 | 15 | $3.33 | 0.00 | 17.0 | 0.0 |
| unlacquered brass toilet paper holder | 1,411 | 15 | $2.33 | 1.00 | 28.1 | 0.0 |

---

## 6. Campaign Impression Share (30-Day)

| Tier | Avg Impression Share | Min | Max | Campaigns with Data |
|------|---------------------|-----|-----|---------------------|
| BRANDED | 92.9% | 92.9% | 92.9% | 1 |
| HIGH | 62.3% | 41.3% | 76.6% | 60 |
| MEDIUM | 85.8% | 62.5% | 100.0% | 57 |
| LOW | 87.5% | 10.0% | 100.0% | 43 |

### Observations

1. **HIGH tier has lowest impression share** (62.3%) — constrained by high tROAS setting, as expected in waterfall
2. **LOW tier has highest variance** (10%-100%) — some product groups have very few high-intent queries
3. **MEDIUM tier is well-covered** (85.8% avg) — healthy middle funnel
4. **17 LOW-tier campaigns have no impression share data** — likely no qualifying queries in 30 days

---

## 7. Scoring Engine Parameterization Recommendations

Based on this audit, the following parameters should be used in the intent scoring engine:

| Parameter | Current Value | Recommended Value | Source |
|-----------|--------------|-------------------|--------|
| Wasted spend threshold | $5.00 (hardcoded) | **$96.33** (1.5x avg CPA) | 90-day CPA calculation |
| CPC ceiling source | `ad_group.cpc_bid_micros` | **`metrics.average_cpc`** from search_term_view | All CPC caps are $0.01 (Target ROAS bidding) |
| Primary conversion metric | `conversions` | `conversions` (purchase only) | Only 1 action has `include_in_conversions=true` |
| Engagement density metric | N/A | `all_conversions` (58.6x multiplier over purchases) | 18 micro-conversion actions contribute |
| Purchase CPA benchmark (HIGH) | N/A | $65.75 | 90-day tier-level data |
| Purchase CPA benchmark (MEDIUM) | N/A | $63.43 | 90-day tier-level data |
| Purchase CPA benchmark (LOW) | N/A | $73.80 | 90-day tier-level data |
| Typical CPC range | N/A | $0.92 - $3.47 | 30-day search term sample |

### Micro-Conversion Funnel Stages

For the micro-conversion delta signal, classify the 6 active micro-conversions into funnel stages:

| Stage | Conversion Action | Signal Strength |
|-------|------------------|-----------------|
| **Browse** | Product Detail view, 3+ Pages, 2+ Minutes | Low intent |
| **Consider** | Cart View, Add to Cart | Medium intent |
| **Intent** | Begin Checkout | High intent |
| **Purchase** | Website Purchase | Conversion |

Terms with Begin Checkout but no Purchase are high-intent near-converters.
Terms with Add to Cart but no Begin Checkout show consideration but friction.
Terms with only Browse signals are awareness-stage only.

---

## 8. Data Collection Method

All data queried via Google Ads API (GAQL) on 2026-02-26 using the `google-ads` Python client library.
Script: `scripts/google_ads_account_audit.py`
Raw data: `docs/analysis/_audit_raw.json`
