# Zero-Conversion Intent Scoring Engine — Research Synthesis

**Date:** 2026-02-26
**Status:** Research complete, pending review before implementation
**Sources:** Agent 1 (Semantic & Feed Alignment), Agent 2 (Google Ads API Data Science)

---

## The Problem

With 80,000 SKUs, most search terms have ZERO conversions due to data sparsity. The current system relies on a brittle "exact MPN match" rule to promote terms. This paralyzes the account — high-intent queries sit in restrictive HIGH tiers burning impressions without aggressive bidding because we can't prove they convert.

## The Solution: Dual-Domain Intent Scoring

Two independent scoring domains, combined into a single composite score:

```
┌─────────────────────────────────────────────────────────────┐
│              UNIFIED INTENT SCORE (0-1)                     │
│                                                             │
│  DOMAIN A: Feed Alignment Score (0-1)                       │
│  "How closely does this query match our product catalog?"   │
│  ├── Layer 1: Attribute Extraction (deterministic)          │
│  ├── Layer 2: TF-IDF Specificity (statistical)              │
│  └── Layer 3: Semantic Embeddings (optional, deferred)      │
│                                                             │
│  DOMAIN B: Behavioral Intent Score (0-1)                    │
│  "What does Google Ads data tell us about this query?"      │
│  ├── Signal 1: Relative CTR (rCTR vs tier peers)            │
│  ├── Signal 2: CPC Ceiling Pressure (hitting Max CPC cap)   │
│  ├── Signal 3: Micro-Conversion Delta (all_conv - conv)     │
│  ├── Signal 4: Cross-Device Conversions (researched, later) │
│  └── Signal 5: Cost Velocity (spend accumulation rate)      │
│                                                             │
│  COMPOSITE = 0.55 * FeedAlignment + 0.45 * BehavioralIntent│
└─────────────────────────────────────────────────────────────┘
```

---

## DOMAIN A: Feed Alignment Score

### Layer 1: Attribute Extraction (Deterministic, <1ms, highest ROI)

Build dictionaries from `product_catalog` database:
- **28 finishes** with aliases + 2-3 char codes (PB, ABR, ORB, etc.)
- **41 collections** (Prestige Regal, Waverly Place, etc.)
- **Product types** from `custom_label_0` (Towel Bar, Soap Dish, etc.)
- **Dimensions** via regex (`\d+\s*(?:inch|in|")`)
- **Model numbers** via regex (`[A-Za-z]{2,4}[-/]\d+(?:[-/]\d+[A-Za-z]*)*`)
- **Brand** ("allied brass", "allied")

**Matching approach:**
- Substring match for brand, product type
- Fuzzy match (rapidfuzz `token_set_ratio >= 85`) for finishes and collections
- Regex for dimensions and model numbers
- Short codes (PB, ORB) require exact word-boundary match to avoid false positives

**Scoring by attribute count (weighted):**

| Attribute | Weight | Rationale |
|-----------|--------|-----------|
| Model number | 1.0 (short-circuit) | Definitive SKU-level intent |
| Collection | 0.30 | Unique to Allied Brass, very specific |
| Finish | 0.25 | Variant-level intent |
| Dimension | 0.25 | Size-specific = high intent |
| Product type | 0.15 | Category-level |
| Brand | 0.10 | Necessary but not sufficient |

**Examples:**

| Query | Attributes Found | Attribute Score |
|-------|-----------------|-----------------|
| "bathroom accessories" | 0 | 0.00 |
| "towel bar" | product_type | 0.15 |
| "polished nickel towel bar" | finish + product_type | 0.40 |
| "prestige regal 18 inch towel bar" | collection + dimension + product_type | 0.70 |
| "PR-41/18-ABR" | model_number | 1.00 |

### Layer 2: TF-IDF Specificity (Statistical, <1ms)

Build TF-IDF model from product titles + descriptions (80K documents). Use IDF scores to measure how "rare" and therefore specific the query terms are.

- "bathroom" → IDF ~1.2 (very common, low specificity)
- "polished nickel" → IDF ~4.8 (specific finish)
- "prestige regal" → IDF ~7.2 (specific collection)
- "PR-41" → IDF ~9.0+ (near-unique identifier)

Unknown terms (not in product corpus) get 80% of max IDF — they're likely model numbers, competitor names, or very specific phrases.

**Computation:** Average IDF of query tokens, normalized to 0-1.

Catches what attribute extraction misses: padded-but-vague queries like "best nice bathroom towel bar for home" get LOW specificity because "best", "nice", "home" have very low IDF in a product catalog corpus.

### Layer 3: Semantic Embeddings (Deferred, ~10ms)

`all-MiniLM-L6-v2` (384 dims, 22M params, free, self-hosted). Pre-embed all 80K product titles (~120MB matrix). At query time, encode query + dot product against matrix.

**Deferred until calibration shows Layers 1+2 miss >10% of high-intent queries.** Adds complexity and memory for marginal improvement when product attributes are well-structured.

### Feed Alignment Composite (Layers 1+2)

```
feed_alignment_score = 0.60 * attribute_score + 0.40 * specificity_score
```

---

## DOMAIN B: Behavioral Intent Score (Google Ads API Signals)

### Signal 1: Relative CTR (rCTR) — Weight: 0.30

**What:** Term's CTR compared to the median CTR of its current tier.

```
rCTR = term_ctr / tier_median_ctr
rCTR_score = min(rCTR / 3.0, 1.0)   // 3x median = max score
```

**Why it matters:** CTR is the strongest pre-conversion signal. A user clicking an ad means the product closely matched their intent. A term with 2x the tier median CTR is getting clicked far more than expected.

**Impression share caveat:** Low impression share + high CTR is MORE meaningful — every time the ad showed, users clicked.

**Availability:** `metrics.ctr` on `search_term_view`. Already fetched in `service.ts`.

### Signal 2: CPC Ceiling Pressure — Weight: 0.25

**What:** In the HIGH tier, Max CPC caps restrict bidding. If a term's average CPC is >=80% of the cap, Google is trying to bid higher but we're blocking it.

```
cpc_ceiling_ratio = term_avg_cpc / ad_group_max_cpc_bid
cpc_score = min(cpc_ceiling_ratio / 1.0, 1.0)
```

**Why it matters:** This is UNIQUE to the waterfall structure. Competitors value this term enough to push auction prices near our cap. The term's commercial value exceeds what the HIGH tier allows.

**Availability:** `metrics.average_cpc` on `search_term_view` + `ad_group.cpc_bid_micros` from `ad_group` resource. **Both need to be added to existing queries.**

### Signal 3: Micro-Conversion Delta — Weight: 0.20

**What:** `all_conversions - conversions` captures micro-conversions (add-to-cart, product page views, begin-checkout, cross-device conversions) configured as secondary conversion actions.

```
micro_conversion_delta = all_conversions - conversions
micro_score = min(micro_conversion_delta / 2.0, 1.0)  // 2+ micro-convs = max
```

**Why it matters:** A term with 0 purchases but 3 add-to-carts is showing clear intent. This is the closest thing to conversion data without actual purchases.

**Availability:** `metrics.all_conversions` on `search_term_view`. **Needs to be added to existing query.** Value depends on which conversion actions are configured (need to audit the 19 conversion actions in the account).

### Signal 4: Cross-Device Conversions — Weight: 0.15

**What:** User clicked on one device, converted on another. A "zero-conversion" term that has cross-device conversions IS converting — just not on the same device.

```
cross_device_score = cross_device_conversions > 0 ? 1.0 : 0.0
```

**Availability:** `metrics.cross_device_conversions` — **needs testing on `search_term_view`**. Available at campaign level.

### Signal 5: Cost Velocity — Weight: 0.10

**What:** How fast a term is burning budget relative to tier peers.

For terms WITH micro-conversions: fast spend can be acceptable (high demand, converting).
For terms WITHOUT any signals: fast spend = Google burning money, negative signal.

```
cost_velocity_ratio = term_daily_spend / tier_median_daily_spend

// Inverted for zero-signal terms (fast spend = bad)
cost_velocity_score = has_any_intent_signal
  ? min(cost_velocity_ratio / 3.0, 1.0) * 0.5
  : 1.0 - min(cost_velocity_ratio / 3.0, 1.0)
```

**Availability:** Already computed from existing `total_cost_micros` data.

### Bonus: Underserved Term Detection

```
underserved_bonus = (campaign_impression_share < 0.30 && rCTR > 1.5) ? 0.15 : 0.0
```

Campaign-level impression share tells us if we're losing auctions. Terms with high CTR in low-share campaigns are being underserved — promotion captures more of their value.

**Availability:** `metrics.search_impression_share` at campaign level only (NOT search term level).

### Behavioral Intent Composite

```
behavioral_intent_score = (
  0.30 * rCTR_score +
  0.25 * cpc_ceiling_score +
  0.20 * micro_conversion_score +
  0.15 * cross_device_score +
  0.10 * cost_velocity_score +
  underserved_bonus
)
```

---

## UNIFIED COMPOSITE: The Decision Engine

```
unified_intent_score = 0.55 * feed_alignment_score + 0.45 * behavioral_intent_score
```

Feed alignment gets slightly more weight because:
- It's deterministic and explainable ("we promoted because query contains finish + dimension + collection")
- It's available for ALL terms (behavioral signals require minimum impressions/clicks)
- It directly maps to the domain model (attribute count = tier mapping)

### The Decision Matrix

```
function determineAction(
  currentTier, currentTierDist, termRoas, totalConversions,
  totalCostMicros, isMisplaced, intentScore, queryWordCount
):

  // ── Override A: Wasted Spend ──
  if (totalConversions == 0 AND costDollars > 1.5 * avgCPA):
    if (currentTier == 'HIGH'):
      return { action: 'block', targetTier: 'HIGH' }
    else:
      return { action: 'demote', targetTier: TIER_UP[currentTier] }

  // ── Override B: Cross-Device Recovery ──
  // If the term appears to have zero conversions but has cross-device
  // conversions, do NOT treat as wasted spend. Let other rules handle it.

  // ── Trigger C: Demote (Underperforming) ──
  if (has conversions AND termRoas < currentTier.p25_ROAS):
    return { action: 'demote', targetTier: TIER_UP[currentTier] }

  // ── Trigger D: Promote (Conversion-Proven) ──
  if (termRoas > currentTier.p75_ROAS):
    return { action: 'promote', targetTier: TIER_DOWN[currentTier] }

  // ── Trigger E: Promote (Intent-Proven, Zero Conversions) ──
  // THIS IS THE NEW RULE that replaces brittle MPN matching
  if (totalConversions == 0
      AND intentScore >= 0.65
      AND (rCTR >= 1.5 OR queryWordCount >= 3)):
    return { action: 'promote', targetTier: TIER_DOWN[currentTier] }

  // ── Trigger F: Under-Invested ──
  if (meets promote criteria AND campaign_impression_share < 0.30):
    return { action: 'promote', targetTier: TIER_DOWN[currentTier] }
    // Flag in UI with "Under-Invested" badge

  // ── Default: Observe ──
  return { action: 'observe', targetTier: currentTier }
```

### Tier Mapping from Unified Score

| Unified Score | Query Example | Tier |
|---------------|--------------|------|
| 0.00 - 0.25 | "bathroom accessories" | HIGH |
| 0.25 - 0.50 | "brass towel bar" | HIGH (borderline) |
| 0.50 - 0.65 | "polished nickel towel bar" | MEDIUM |
| 0.65 - 0.85 | "prestige regal 18 inch towel bar" | LOW |
| 0.85 - 1.00 | "PR-41/18-ABR" | LOW (definitive) |

---

## What's NOT Available (API Limitations)

| Signal | Available? | Workaround |
|--------|-----------|------------|
| Impression share per search term | No | Campaign-level proxy |
| Auction insights per search term | No | Campaign-level only |
| Bounce rate / time on site | No | GA4 audience import as micro-conversion |
| Repeat searches (same user) | No | Not available via any API |
| Product click concentration | Indirect | Ad group listing group product count |
| `conversion_action` segment on `search_term_view` | Needs testing | Available on `shopping_performance_view` |

---

## Implementation Roadmap

### Phase 1: Feed Alignment (Python, 1-2 days)

No ML infrastructure needed. Deploy on Cloud Run.

1. Query `product_catalog` to build attribute dictionaries
2. Fit TF-IDF model from product titles/descriptions
3. Implement `IntentScorer` class with Layers 1+2
4. New endpoint: `POST /score-intent`
5. Dependencies: `rapidfuzz`, `scikit-learn` (both lightweight)
6. Memory: ~52MB (dictionaries + TF-IDF model)
7. Latency: <2ms per query

### Phase 2: Behavioral Signals (TypeScript, 1-2 days)

Augment existing `service.ts` GAQL queries.

1. Add `metrics.average_cpc`, `metrics.all_conversions` to `search_term_view` query
2. Fetch `ad_group.cpc_bid_micros` in existing ad group query
3. Test `metrics.cross_device_conversions` on `search_term_view`
4. Compute rCTR, CPC ceiling ratio, micro-conversion delta in `tier-scoring.ts`
5. Replace `significance` in `computeConfidence()` with behavioral intent score

### Phase 3: Unified Scoring + Calibration (1-2 days)

1. Wire feed alignment score (from Cloud Run) into tier-scoring pipeline
2. Combine with behavioral intent score using 0.55/0.45 weights
3. Implement the new `determineAction()` decision matrix
4. Pull 1000+ search terms with actual ROAS data to calibrate thresholds
5. Adjust 0.25/0.50/0.65 tier boundaries based on real data

### Phase 4: UI + Terminology Fix (the original quick task)

1. Rename `constrain` → `demote` across codebase
2. Add `targetTier` to `TermScore` type
3. Fix TierMovementArrow to use `targetTier`
4. Add Promote/Demote buttons with target tier labels
5. Show intent score breakdown in UI (attribute + behavioral + composite)

### Phase 5: Semantic Embeddings (deferred)

Only if calibration shows >10% missed high-intent queries.

1. Add `sentence-transformers` to Python dependencies
2. Pre-embed 80K product titles (~120MB, `all-MiniLM-L6-v2`)
3. Add as Layer 3 to `IntentScorer`
4. Memory: ~260MB total (vs 52MB without)

---

## Technical Infrastructure

| Component | Location | Memory | Latency |
|-----------|----------|--------|---------|
| Attribute dictionaries | Cloud Run startup | ~2MB | <1ms |
| TF-IDF model | Cloud Run startup | ~50MB | <1ms |
| Product embeddings (deferred) | Cloud Run startup | ~120MB | ~10ms |
| Behavioral signals | Dashboard API | ~0 (computed on the fly) | ~0ms (data already fetched) |
| Composite scoring | `tier-scoring.ts` | ~0 | <1ms |

---

## Key Decisions for Bobby

1. **Audit the 19 conversion actions** in the Google Ads account — which are micro-conversions (add-to-cart, page view) vs purchases? This determines how valuable Signal 3 (micro-conversion delta) is.

2. **What is the account's average CPA?** The wasted spend threshold should be 1.5x avg CPA, not a fixed $5.

3. **Do we want Search campaign graduation?** The Master Directive includes a 4th tier (LOW → Search). Is this active in the account today?

4. **Weight calibration:** The 0.55/0.45 split between feed alignment and behavioral intent is a starting point. Real data will tell us the right balance.

5. **Threshold calibration:** The tier boundaries (0.25/0.50/0.65) need validation against 1000+ scored terms with actual ROAS outcomes.
