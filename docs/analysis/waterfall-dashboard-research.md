# Waterfall Shopping Dashboard — Decision Intelligence Research

**Date:** 2026-02-25
**Purpose:** Comprehensive analysis of what the Tier Intelligence dashboard should surface for decision-making in a 3-tier waterfall Shopping campaign structure.

---

## 1. What Decisions Should the Dashboard Help the User Make?

### The Decision Hierarchy

The dashboard exists to answer one question: **"Which search terms are in the wrong tier, and what is that costing me?"** Every UI element should trace back to a specific, executable action.

### Decision Type 1: Promote a Term (Push Down the Funnel → toward LOW)

**Trigger:** A term in HIGH or MEDIUM is performing above that tier's expected ROAS/CVR distribution — it is a high-intent converter trapped where the algorithm is bidding conservatively.

**Mechanism:** Add the term as a negative keyword to the current campaign (and any campaigns above the target tier). The term cascades down through the waterfall to the next tier that does not block it.

**Example:** "valet rods" appearing in HIGH with ROAS 7.5. HIGH's p50 ROAS is ~1.2. The algorithm is bidding conservatively on a term that converts at 6x the tier median. Promoting it to LOW frees the algorithm to bid aggressively.

**Data points that drive this decision:**
- Term ROAS vs. tier ROAS p50/p75
- Term CVR vs. tier CVR p50/p75
- Fit score delta: how much better does the term fit LOW vs. its current tier?
- Confidence: is there enough click/conversion data to be sure?
- Impact estimate: monthly revenue delta if moved to LOW

**Priority signal:** Terms currently in HIGH with LOW-tier ROAS are the highest-leverage promotions. They are being penalized most by the bidding constraint.

---

### Decision Type 2: Demote a Term (Pull Up the Funnel → toward HIGH)

**Trigger:** A term in LOW or MEDIUM is performing below that tier's expected ROAS/CVR distribution. The algorithm is bidding aggressively on a poor converter, rapidly draining the bottom-of-funnel budget.

**Mechanism:** Remove the term's negative keyword entries from the upper campaigns. The term is then caught by a higher-priority campaign (HIGH), where the restrictive target ROAS / CPC caps constrain spending automatically.

**Data points that drive this decision:**
- Term ROAS vs. tier ROAS p25 (below p25 is a red flag)
- Cost already spent on this term in LOW/MEDIUM (urgency signal)
- Zero or near-zero conversions despite meaningful cost
- Query specificity score: is the term structurally a broad query stuck in a narrow tier?

**Priority signal:** Demotions from LOW are most urgent — LOW has the most aggressive bidding, so a bad term there burns budget fastest.

---

### Decision Type 3: Block a Term (Account-Level Negative)

**Trigger:** A term is generating cost with zero relevance to the product. No tier is appropriate — the term should never surface again.

**Distinguishing from Demote:** A demotion makes sense when the term is relevant but low-converting. A block makes sense when the query is structurally irrelevant (wrong product category, navigational query, etc.).

**Signals for block vs. demote:**
- `has_mismatch_risk` flag: "replacement part", "repair", "used", "diy", "free", "cheap"
- Zero conversions over a long window (not just a cold-start issue)
- The term is already in HIGH (the most restrictive tier) and still wasting spend — demotion has nowhere to go, only block makes sense

---

### Decision Type 4: Keep (Confirm Correct Placement)

**Trigger:** A term's performance aligns with its current tier's distribution. The scoring engine's `dataConfirmed` flag is true.

**Value:** Confirmed terms reduce noise. The user should be able to quickly dismiss correctly-placed terms and focus attention on the actionable queue.

---

### Decision Prioritization Framework

Sort the action queue by urgency, not just impact size:

| Priority | Condition | Reason |
|----------|-----------|--------|
| P0 | Wasted spend in LOW tier | Most aggressive bidding — highest budget burn rate |
| P1 | Wasted spend in MEDIUM tier | Moderate bidding — meaningful but not maximum damage |
| P2 | Under-invested terms in HIGH/MEDIUM | Revenue left on table — profitable terms bidding conservatively |
| P3 | Misplaced terms (HIGH→LOW promotion) | Tier mismatch costing opportunity |
| P4 | Misplaced terms (LOW/MEDIUM→HIGH demotion) | Already partially constrained in current tier |
| P5 | Wasted spend in HIGH tier | Already constrained — lowest urgency |

---

## 2. What Insights Should the Dashboard Surface?

### Revenue Leakage Detection

**Definition:** Revenue leakage is money spent that either (a) generates zero return or (b) generates return that would be significantly higher with correct tier placement.

**Leakage Type A — Active Waste:** Cost > $5 with zero conversions. The term is consuming budget with no output. Urgency scales with tier depth: LOW waste > MEDIUM waste > HIGH waste.

**Leakage Type B — Misplacement Loss:** A term producing, say, 4.0 ROAS in HIGH when LOW-tier terms produce 5.5 ROAS p50. The delta (1.5 ROAS × monthly spend) is the opportunity cost. This is not zero-conversion waste — it is underperformance relative to what correct placement would yield.

**Key display:** A dollar-denominated leakage total surfaced prominently. "Estimated $X/month in misrouted search terms." This number is the sum of impact.mid across all misplaced and wasted-spend terms.

---

### Opportunity Identification (Under-Invested)

**Definition:** A term with high actual ROAS trapped in a tier that constrains the algorithm from bidding enough to capture available volume.

**Detection logic:**
1. Term's actual ROAS substantially exceeds current tier's p75
2. Term's impression share is low (Keyword Planner avgMonthlySearches >> actual impressions)
3. Impact direction is "downward" (toward LOW, where aggressive bidding is allowed)

**The insight to surface:** "This term converts at 2x your tier's median, but you're only capturing 15% of available search volume. Moving it to LOW could unlock 6x more impression share at profitable ROAS."

---

### Query Specificity Pattern

The waterfall model's defining characteristic is that query specificity maps directly to tier appropriateness:

```
Attribute count → Expected tier
0 attributes    → HIGH  (generic: "grab bar")
1 attribute     → MEDIUM (category + 1: "polished nickel grab bar")
2+ attributes   → LOW   (specific: "polished nickel grab bar 18in", "Allied Brass oil rubbed bronze towel ring")
```

**The dashboard should display the specificity classification alongside every term.** When a term's computed specificity level disagrees with its actual tier, that structural mismatch is a leading indicator of misplacement — even before performance data accumulates.

This matters especially for cold-start terms (low impressions, few clicks). Performance data may be noisy, but query structure is deterministic.

**Specificity score formula (suggested):**
```
specificity = base_product_token (1)
            + finish_token present (+1)
            + dimension_token present (+1)
            + brand_token present (+1)
            + collection_token present (+1)
            + model_number present (+2)  // strong signal, weight higher

score 0-1 → HIGH
score 2   → MEDIUM
score 3+  → LOW
```

---

### Tier Health Summary

At the top of the dashboard, before any per-term detail, surface a tier health overview:

| Metric | HIGH | MEDIUM | LOW |
|--------|------|--------|-----|
| Actual ROAS (median) | — | — | — |
| Terms in tier | N | N | N |
| % of terms correctly placed | % | % | % |
| Flagged for action | N | N | N |
| Estimated monthly leakage | $— | $— | $— |

This lets the user see at a glance which tier has the most problems before drilling into individual terms.

---

## 3. How Should NLP / Intent Classification Work?

### Feature Extraction Design

The current `decomposeSearchTerm()` function in `query-intelligence.ts` extracts product objects, modifiers, use-case tokens, brand tokens, and competitor tokens. This is a good foundation. The critical missing piece is a **specificity score** that maps the extracted features to an expected waterfall tier.

### Feature Set for Intent Classification

**Feature 1: Finish Token Detection**
The 28 Allied Brass finishes are the single most powerful tier-routing signal. A finish name in a query is one attribute that immediately pushes the term toward MEDIUM.

Finish tokens to detect (full list, case-insensitive):
- Polished Nickel, Satin Nickel, Brushed Nickel
- Oil Rubbed Bronze, Venetian Bronze, Antique Bronze
- Polished Chrome, Satin Chrome, Brushed Chrome
- Polished Brass, Antique Brass, Satin Brass, Unlacquered Brass
- Matte Black, Flat Black
- French Gold, Antique Gold
- Pewter, Antique Pewter
- Copper, Venetian Copper
- Alabaster White, Navy, Bisque
- (plus abbreviations: PN, SN, ORB, PC, SC, MB, PB, AB)

**Current gap:** `query-intelligence.ts` has partial finish detection via MODIFIER_HINTS ("polished", "satin", "chrome", "nickel", "bronze", "matte") but these are individual tokens — they don't reliably detect multi-word finishes like "Oil Rubbed Bronze" as a single attribute.

**Recommendation:** Add a dedicated `FINISH_TOKENS` array using the full 28-finish list (multi-word phrases first to avoid partial matches). Detection returns the matched finish name or null.

---

**Feature 2: Dimension / Size Detection**
Dimensions strongly signal high-intent — the buyer knows exactly what they need.

Patterns to match:
- `\d+\s*(?:in|inch|inches|")\b` — e.g., "18in", "24 inch", "36""
- `\d+\s*(?:mm|cm)\b`
- `\d+\s*x\s*\d+` — e.g., "18x4"
- Named sizes: "small", "large", "compact" (weaker signal, +0.5 weight)

**Feature 3: Brand Detection**
"Allied Brass" in a query is a maximum-intent signal. The user is specifically looking for this brand. These terms belong in LOW without exception (unless they have mismatch-risk tokens).

Current tokens: `['allied brass', 'alliedbrass', 'avd']` — this is correct but should also detect "allied" alone in context (risky — common word, may need minimum context of also having a product token).

**Feature 4: Collection / Model Number Detection**
Collection names (e.g., "Waverly Place", "Monte Carlo", "Prestige") and model numbers (e.g., "920D-6", "WP-16") are the strongest possible HIGH→LOW routing signals. A user querying a specific model number has maximum purchase intent.

Patterns:
- Model numbers: `[A-Z]{2,5}-\d{1,4}[A-Z]?` regex
- Collection names: dictionary lookup against the 41 named collections in `config/collection_stories.yaml`

**Feature 5: Word Count Relative to Category Baseline**
Word count is a useful proxy for specificity. Compute:
```
extra_tokens = word_count(query) - word_count(matched_product_object)
```
- extra_tokens = 0 → likely HIGH
- extra_tokens = 1-2 → likely MEDIUM
- extra_tokens = 3+ → likely LOW

This is a fallback signal when named-entity extraction fails.

---

### Specificity Score Computation

```typescript
interface QuerySpecificity {
  score: number              // 0–5+ (higher = more specific)
  expectedTier: FunnelTier  // HIGH | MEDIUM | LOW
  signals: {
    hasProductObject: boolean
    hasFinish: boolean       // +1
    hasDimension: boolean    // +1
    hasBrand: boolean        // +1
    hasCollection: boolean   // +1
    hasModelNumber: boolean  // +2 (strongest signal)
    extraTokenCount: number  // fallback
  }
}

function computeSpecificity(query: string): QuerySpecificity {
  // ... extract features ...
  const score = (hasFinish ? 1 : 0)
              + (hasDimension ? 1 : 0)
              + (hasBrand ? 1 : 0)
              + (hasCollection ? 1 : 0)
              + (hasModelNumber ? 2 : 0)

  const expectedTier: FunnelTier =
    score === 0 ? 'HIGH' :
    score === 1 ? 'MEDIUM' : 'LOW'

  return { score, expectedTier, signals }
}
```

---

### Using Specificity in the Confidence Score

In `tier-scoring.ts`, the `computeConfidence()` function has an `intentAlignment` factor (20% weight). Currently this uses broad product-object detection. Replace or augment with the specificity score:

```typescript
// intentAlignment based on specificity tier vs. current tier
const specificity = computeSpecificity(searchTerm)
const tierDepth = { HIGH: 1, MEDIUM: 2, LOW: 3 }
const specificityDepth = tierDepth[specificity.expectedTier]
const currentDepth = tierDepth[currentTier]
const alignmentDelta = Math.abs(specificityDepth - currentDepth)

intentAlignment = alignmentDelta === 0 ? 0.9   // perfect structural alignment
                : alignmentDelta === 1 ? 0.5   // one tier off
                : 0.2                          // two tiers off (structural mismatch)
```

---

### Cold-Start Problem

For terms with fewer than 50 clicks (insufficient performance data), the scoring engine falls back to defaults. But the specificity score is available immediately from the query string alone — no data required.

**Cold-start strategy:**
1. Classify the query by specificity score → assign expected tier
2. If actual tier ≠ expected tier, flag as "structural mismatch" with a distinct visual treatment (different from data-confirmed misplacement)
3. Show the structural mismatch signal but do not compute dollar impact (insufficient data)
4. As data accumulates, transition from "structural flag" to "data-confirmed recommendation"
5. Surface cold-start structural mismatches in a separate section below the data-confirmed action queue

This gives the user early warning on newly observed terms before waiting for statistical confidence.

---

## 4. What's Missing from the Current Implementation?

### Missing Feature 1: Tier-Aware Urgency Sorting

The current `classifyAllTerms()` sorts by `impact.mid` (dollar impact). This is directionally correct but misses the urgency dimension. A $20/month wasted-spend term in LOW is more urgent than a $100/month misplacement from HIGH, because the LOW term is burning budget at aggressive bidding rates right now.

**Fix:** Add a composite urgency score:
```
urgency = (dollar_impact × tier_urgency_multiplier)
tier_urgency_multiplier = { LOW: 3.0, MEDIUM: 1.5, HIGH: 0.5 }
```
Sort the primary action queue by urgency, with dollar impact as a secondary signal.

---

### Missing Feature 2: "Already in Most Restrictive Tier" Guard

The current wasted-spend handler does not check whether a term is already in HIGH. When a term with wasted spend is already in HIGH, "Demote to HIGH" is a no-op — the term is already there. The only valid actions are Block or Keep (accept conservative spend).

**Fix in `reason-codes.ts`:** Before assigning the `wasted_spend` reason code, check `currentTier`. If `currentTier === 'HIGH'` and wasted spend is confirmed, the available actions should be Block or Accept — not Demote.

---

### Missing Feature 3: Structural Mismatch Signal (Cold-Start)

There is no mechanism to flag terms that are structurally wrong (specificity score disagrees with current tier) before enough click data exists to score them statistically.

**What to build:** A `structuralMismatch` flag on `TermScore`, populated from the specificity score. Display these in a "Needs Monitoring" section separate from the confirmed action queue.

---

### Missing Feature 4: Finish-Aware Analysis

Allied Brass has 28 finishes per product. The same base product can have very different performance by finish. A term like "polished nickel grab bar" converts at a different rate than "oil rubbed bronze grab bar" — not just because of the tier, but because of finish-level demand differences.

**Missing insight:** "Which finish tokens in your search terms are over- or under-represented in LOW tier relative to their actual conversion rates?"

This would let the user understand whether certain finishes should be more aggressively promoted (pushed to LOW) across all their SKUs.

---

### Missing Feature 5: Negative Keyword Execution Integration

The audit (`tier-scoring-domain-audit.md`) notes that `removeSharedKeyword` already exists in `service.ts`. The approval flow (Approve → Reject in the UI) does not currently trigger the Google Ads API call to actually add/remove negative keywords.

**The gap:** Approving a term promotion in the dashboard does nothing to the actual campaigns. The recommendation loop is broken at execution. The dashboard is currently a reporting tool, not an optimization tool.

**What to build:** When a user approves a Promote action, call the Google Ads Mutate API to add the search term as a negative keyword in the appropriate shared negative list. When a user approves a Demote, remove the negative keyword. Log the action in Supabase for audit trail.

---

### Missing Feature 6: Actual ROAS Display Bug

From the audit: `tierFitScores[currentTier]` is a z-score (negative number) but the UI labels it "Current ROAS." This is misleading. The `TermScore` object already has `actualRoas` — the UI should display that field, not the fit score.

---

### Missing Feature 7: Cross-Term Pattern Detection

The dashboard evaluates terms independently. Missing: **pattern-level analysis** across terms.

Examples:
- "All queries containing 'grab bar' in HIGH are converting above p75 — consider whether the entire grab bar product group is miscategorized"
- "8 of your 12 finish-qualified queries are stuck in HIGH — systematic promotion opportunity"
- "The query modifier 'wall mount' correlates with above-p75 CVR across all tiers — high-intent signal"

These cluster-level insights surface optimization opportunities that per-term analysis misses.

---

## 5. What Would a Data-Driven / ML Approach Look Like?

### Why Hardcoded Thresholds Fail

The current `estimateTierFromMetrics()` in `query-intelligence.ts` uses fixed ROAS thresholds (3.6 for LOW, 3.1 for MEDIUM). These were likely set from intuition or a single snapshot of data. They will be wrong when:
- Seasonal effects shift the overall ROAS baseline (holiday vs. off-season)
- The product mix changes (new SKUs with different price points change conversion value)
- Google's algorithm behavior changes (Smart Bidding strategy updates)
- The bid settings themselves change (new target ROAS values reset what "normal" looks like)

The distribution-based approach in `tier-scoring.ts` (median/MAD, per-group distributions) is architecturally correct and self-calibrating. The goal is to extend this approach to replace the remaining hardcoded thresholds.

---

### Learning Tier Expectations from Actual Data

**Step 1: Bootstrap from observed data, not hardcoded priors**

The `DEFAULT_DISTRIBUTIONS` in `tier-scoring.ts` are now correctly oriented (HIGH p50=1.2, LOW p50=5.5). These should be replaced by values computed from the actual account's rolling 90-day performance as soon as enough data is available.

**Bootstrapping threshold:** When a tier has ≥ 20 terms with ≥ 50 clicks each, switch from `DEFAULT_DISTRIBUTIONS` to `global` fallback. When a product group (custom_label_0) has ≥ 5 terms per tier, switch to `per_group` distributions. The current MIN_SAMPLE_SIZE=5 is reasonable.

**Step 2: Smoothed rolling distributions**

Instead of recomputing distributions from a fixed 30-day window, maintain exponentially weighted moving distributions. New observations get higher weight than old ones. This allows the system to adapt to gradual drift (seasonal changes) while being resistant to sudden outliers.

**Step 3: Product-group-specific calibration**

Not all product groups behave the same. "Grab bars" may naturally have higher CVR than "glass shelves" because of the ADA compliance purchase driver. The per-group distribution mechanism already handles this — but the boundary-capping logic (15% max shift per cycle) prevents rapid adaptation when a new product group is introduced with no history.

**Recommendation:** For product groups with zero history, skip the boundary-capping entirely and use the raw computed values for the first 30 days. Apply capping starting from cycle 2.

---

### Features for a Classifier

If the system graduates from rule-based z-score scoring to a trained classifier, the feature vector for each (search_term, tier) observation should include:

**Query features (static, from NLP):**
- `specificity_score` (0–5+)
- `has_finish` (bool)
- `has_dimension` (bool)
- `has_brand` (bool)
- `has_collection` (bool)
- `has_model_number` (bool)
- `word_count` (int)
- `extra_token_count` (word_count - product_object_word_count)
- `has_high_intent_token` (bool: "buy", "shop", "near me")
- `has_mismatch_risk` (bool: "repair", "replacement", "used")
- `is_competitor` (bool)

**Performance features (dynamic, from Google Ads):**
- `roas` (float)
- `cvr` (float)
- `ctr` (float)
- `cpc` (float)
- `impression_share` (float, requires Google Ads impression share data)
- `clicks` (int, used as sample weight)
- `conversions` (int)
- `days_observed` (int — terms with more history get higher sample weight)

**Tier context features:**
- `group_roas_p50` for current tier (the baseline to beat)
- `group_cvr_p50` for current tier
- `roas_percentile_in_group` (where does this term rank?)
- `peer_count_in_tier` (how many peer terms in this tier)

**Target label:** correct tier (HIGH / MEDIUM / LOW), learned from terms where the current tier produces above-median performance AND the z-score fit is strong (using existing scoring as a pseudo-label generator).

**Training approach:** Semi-supervised. Start by treating terms with `dataConfirmed=true` (strong fit to current tier, high confidence) as labeled positive examples of correct placement. Terms with `isMisplaced=true` and high confidence are labeled with `recommendedTier` as the true label. Use a gradient-boosted tree (XGBoost or LightGBM) — these handle mixed feature types and small datasets well.

---

### Cold-Start Handling in the ML Model

**Problem:** A new search term appears with 0 clicks. No performance features are available. The model must still produce a routing recommendation.

**Solution:** Train two sub-models:
1. **Query-only model** (features: only NLP features) — handles cold-start
2. **Full model** (features: NLP + performance) — handles warm terms

**Routing logic:**
```
if clicks < 30:
    use query-only model → output "structural recommendation"
    confidence = query_only_probability
elif clicks < 100:
    blend(query_only_model * (1 - alpha), full_model * alpha)
    alpha = (clicks - 30) / 70   # linear interpolation
else:
    use full model exclusively
```

This gives the user a structural signal immediately when a term appears, with explicit uncertainty communication, transitioning to data-driven recommendations as the term accumulates history.

---

### Handling Seasonality

Google Ads performance in bathroom hardware peaks around new construction/renovation seasons and holiday periods. A term might belong in LOW during Q4 but perform like a MEDIUM term in Q1.

**Recommended approach:** Maintain a 12-week rolling window rather than a fixed 30-day window. Tag distributions with the week-of-year. When computing recommendations, blend the trailing 12-week distribution with a same-period-last-year distribution (if available) to separate true performance degradation from seasonal variation.

**Display:** Surface seasonality context alongside recommendations: "This term's ROAS of 2.1 is below MEDIUM tier p50 (3.0), but this matches its historical pattern in February. Consider monitoring before acting."

---

## Summary: Priority Build Order

Based on this analysis, the highest-leverage improvements to the dashboard, in order:

| Priority | Feature | Impact |
|----------|---------|--------|
| P0 | Fix "Demote" wasted-spend action (send to HIGH, not LOW) | Eliminates incorrect recommendations currently shown |
| P0 | Fix ROAS display (show actualRoas, not fit z-score) | Fixes misleading metric in UI |
| P1 | Add tier-aware urgency sorting (LOW waste = highest priority) | Correctly prioritizes the action queue |
| P1 | Add "already in HIGH" guard for wasted-spend terms | Prevents no-op Demote recommendations |
| P1 | Add full 28-finish token detection | Improves structural tier classification |
| P1 | Add dimension detection regex | Adds second most important HIGH-intent signal |
| P2 | Add specificity score to TermScore | Enables structural mismatch detection for cold-start |
| P2 | Surface cold-start structural mismatches in separate section | Early warning before data confirms |
| P2 | Add tier health summary view | Tier-level overview before per-term detail |
| P3 | Wire approvals to Google Ads Mutate API | Closes the execution loop |
| P3 | Add cross-term pattern detection (cluster insights) | Surfaces systemic opportunities |
| P4 | Implement ML classifier | Replaces rule-based thresholds with learned distributions |
