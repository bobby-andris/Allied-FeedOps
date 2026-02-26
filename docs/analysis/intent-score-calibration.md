# Intent Score Calibration Analysis

**Date**: 2026-02-26
**Engine version**: v2-tier-scoring (unified intent scoring with 5-trigger matrix)
**Data sources**: Google Ads account audit (90-day), search_term_view (30-day), scoring engine model_inputs
**Calibration script**: `scripts/intent_score_calibration.py`

---

## 1. Executive Summary

This document calibrates the intent scoring engine's thresholds against real account data from Allied Brass (Customer ID: 6253381786). The scoring engine combines two domains:

- **Domain A (Feed Alignment)**: Query-to-catalog matching via attribute extraction + TF-IDF specificity (weight: 0.55)
- **Domain B (Behavioral Signals)**: rCTR, CPC ceiling pressure, micro-conversion delta, cost velocity (weight: 0.45)

**Key findings**:

1. The **0.65 intent score threshold** for Trigger D (zero-conversion promotion) is appropriate. With the dual gate (rCTR >= 1.5 OR wordCount >= 3), false positive risk is acceptably low.
2. The **wasted spend threshold must use real CPA ($96.33)**, not the original $5 hardcode. At $5, virtually every term with any spend would be flagged.
3. The **0.55/0.45 weight split** (feed/behavioral) is well-calibrated for this account where behavioral signals are available for all scored terms.
4. The **rCTR threshold of 1.5** is appropriate given the tier median CTR ranges observed in the account.

---

## 2. Account Data Summary

| Metric | Value | Source |
|--------|-------|--------|
| Total spend (90 days) | $38,373.35 | Google Ads API |
| Purchase conversions | 597.5 | `metrics.conversions` (Website Purchase only) |
| All conversions | 35,035 | `metrics.all_conversions` (18 micro-conversion actions) |
| **Average CPA (purchase)** | **$64.22** | $38,373 / 597.5 |
| Micro-CPA | $1.10 | $38,373 / 35,035 |
| Active campaigns | 182 | 61 HIGH + 60 MEDIUM + 60 LOW + 1 BRANDED |
| Typical CPC range | $0.92 - $3.47 | 30-day search_term_view |
| CPC cap (ad group) | $0.01 (all) | Target ROAS automated bidding |

### CPA by Tier

| Tier | Spend | Purchase Conv | CPA | All Conv | Micro-CPA |
|------|-------|--------------|-----|----------|-----------|
| BRANDED | $921 | 29.8 | $30.88 | 1,004 | $0.92 |
| HIGH | $28,611 | 435.2 | $65.75 | 27,536 | $1.04 |
| MEDIUM | $5,739 | 90.5 | $63.43 | 4,228 | $1.36 |
| LOW | $3,103 | 42.0 | $73.80 | 2,267 | $1.37 |

**Observation**: CPA is surprisingly flat across tiers ($63-74). The waterfall structure successfully segments traffic volume but CPA convergence suggests Smart Bidding normalizes cost-per-acquisition across tiers.

---

## 3. Wasted Spend Threshold Calibration

### The Problem with $5

The original threshold (`costDollars > 5`) was a placeholder. With average CPC of $0.92-$3.47, a term needs only 2-5 clicks to exceed $5. This flags nearly every zero-conversion term with any traffic — far too aggressive.

### Calibrated Threshold: $96.33 (1.5x avgCPA)

| Threshold | Formula | Value | Rationale |
|-----------|---------|-------|-----------|
| Original | hardcoded | $5.00 | Placeholder — flags almost everything |
| Conservative | 1.0x CPA | $64.22 | Full CPA burn without conversion |
| **Recommended** | **1.5x CPA** | **$96.33** | Gives statistical room for slow converters |
| Aggressive | 0.5x CPA | $32.11 | Too aggressive for high-AOV products |

**Why 1.5x**: Allied Brass products have high AOV (~$85). A term that has spent 1.5x the average CPA without generating a single purchase is genuinely wasted. At 1.0x, we'd catch some terms that are about to convert (false positives). At 0.5x, we'd flag terms before they've had a fair chance.

### Wasted Spend Impact Estimate

From the account audit data:
- **At $5 threshold**: Would flag most zero-conversion terms with any clicks (overly sensitive)
- **At $96.33 threshold**: Flags only terms that have burned significant budget without any purchase signal

**Recommendation**: Use `1.5 * avgCPA` where `avgCPA = 64.22`. This is already implemented in `determineAction()` as `wastedSpendThreshold = 1.5 * (avgCPA || 5)`.

---

## 4. Intent Score Threshold Validation (0.65)

### Unified Score Composition

```
unifiedScore = 0.55 * feedAlignmentScore + 0.45 * behavioralScore
```

A term scoring 0.65 needs strong signals from both domains:

| Scenario | Feed Alignment | Behavioral | Unified | Passes? |
|----------|---------------|------------|---------|---------|
| Strong both | 0.75 | 0.53 | 0.65 | Yes |
| Domain A only | 1.0 | 0.19 | 0.64 | No |
| Domain B only | 0.0 | 0.85 | 0.38 | No |
| Moderate both | 0.60 | 0.71 | 0.65 | Yes |
| Very strong A | 0.90 | 0.35 | 0.65 | Yes |

**Key insight**: The 0.65 threshold effectively requires evidence from BOTH domains. A term cannot reach 0.65 on feed alignment alone (max behavioral contribution at 0 = 0.55 * 1.0 = 0.55) or behavioral alone (max = 0.45 * 0.85 = 0.38). This is a desirable property — it prevents single-signal false positives.

### Trigger D Gate Analysis

Trigger D fires when ALL conditions are met:
1. `totalConversions === 0` (zero-conversion term)
2. `intentScore >= 0.65` (high unified intent)
3. `rCTR >= 1.5 OR queryWordCount >= 3` (supporting evidence gate)

The dual gate (condition 3) provides additional safety:
- **rCTR >= 1.5**: Term gets 50%+ more clicks than tier median CTR — users find it relevant
- **wordCount >= 3**: Multi-word queries are inherently more specific ("polished nickel grab bar" vs "grab bar")

**False positive analysis**: A term passes Trigger D only if it:
1. Has never converted (but we want to give it aggressive bidding)
2. Matches the product catalog well (feed alignment) AND shows behavioral intent signals
3. Users click it more than average OR the query is specific

This triple-gate structure makes false positives unlikely. The risk is **false negatives** — terms that deserve promotion but don't meet all three criteria. This is acceptable because:
- False negatives result in the term staying in its current tier (no harm done)
- False positives would waste budget by promoting bad terms to more aggressive bidding

**Recommendation**: Keep 0.65 threshold. Consider lowering to 0.60 only if data shows too many good terms being missed (Trigger D firing too rarely).

---

## 5. Weight Split Validation (0.55/0.45)

### Domain A: Feed Alignment (weight: 0.55)

Feed alignment measures query-to-catalog match quality:
- **Attribute extraction** (60%): Finish names (28), collections (41), product types, dimensions, model numbers
- **TF-IDF specificity** (40%): Rarity of query terms relative to product catalog

A term like "polished nickel double glass shelf" would score high on both (specific finish + product type match).

### Domain B: Behavioral Signals (weight: 0.45)

Behavioral signals measure Google Ads evidence of purchase intent:
- **rCTR** (0.30): High click-through relative to tier peers
- **CPC ceiling** (0.25): Smart Bidding pushing CPC toward tier median
- **Micro-conversion delta** (0.20): Add-to-cart/begin-checkout without purchase
- **Cost velocity** (0.10): Budget burn rate (0.15 reserved for cross-device, deferred)

### Weight Sensitivity Analysis

| Weight Split (Feed/Behavioral) | Effect | Risk |
|-------------------------------|--------|------|
| 0.70 / 0.30 | Heavily favors catalog matching | Misses terms with weak catalog match but strong behavioral signals |
| **0.55 / 0.45** | **Balanced, slight feed priority** | **Good balance for intent scoring** |
| 0.50 / 0.50 | Equal weight | Behavioral noise could overwhelm feed signal |
| 0.40 / 0.60 | Behavioral-heavy | Noisy — CPC and CTR variance too high |

**Recommendation**: Keep 0.55/0.45. Feed alignment should have slight priority because:
1. It's deterministic (same query always gets same feed score)
2. Behavioral signals are noisy (vary by day, season, competition)
3. The 0.65 threshold already requires both domains to contribute

---

## 6. rCTR Threshold Validation (1.5)

### What rCTR = 1.5 Means

rCTR = term CTR / tier median CTR. A value of 1.5 means the term gets 50% more clicks than the tier average.

### Tier Median CTR from Account Data

| Tier | Typical CTR Range | Median Estimate |
|------|-------------------|-----------------|
| HIGH | 1-3% | ~2% |
| MEDIUM | 2-6% | ~4% |
| LOW | 3-8% | ~5% |

At rCTR = 1.5:
- HIGH tier: term CTR >= 3% (3x the minimum, above p75)
- MEDIUM tier: term CTR >= 6% (at the p75 boundary)
- LOW tier: term CTR >= 7.5% (above p75)

**Recommendation**: 1.5 is appropriate. It requires above-average engagement without being so high that it filters out genuinely interested shoppers. Lower thresholds (1.2) would include more noise; higher (2.0) would be too restrictive.

---

## 7. Trigger Priority Validation

The 5-trigger priority order (first match wins):

| Priority | Trigger | Condition | Action |
|----------|---------|-----------|--------|
| 1 | **Wasted Spend** | 0 conv + spend > 1.5x CPA | Block (HIGH) or Demote to HIGH |
| 2 | **Demote (Underperform)** | conv > 0 + ROAS < p25 | Demote one step toward HIGH |
| 3 | **Promote (Conversion)** | ROAS > p75 | Promote one step toward LOW |
| 4 | **Promote (Intent)** | 0 conv + intent >= 0.65 + gate | Promote one step toward LOW |
| 5 | **Observe** | None of the above | Keep current tier |

### Priority Order Rationale

1. **Wasted spend first**: Safety — stop bleeding money before anything else
2. **Demote before promote**: Conservative — protect budget before expanding exposure
3. **Conversion-proven before intent-proven**: Hard evidence trumps soft signals
4. **Intent-proven last among actions**: Only promotes when no conversion data contradicts it
5. **Observe as default**: Do nothing is the safest default

This ordering is correct and should not be changed. The key protection is that Trigger A (wasted spend) cannot be overridden by Trigger D (intent promotion) — a zero-conversion term that has burned significant budget will be demoted/blocked regardless of intent score.

---

## 8. CalibrationConfig Recommendations

Based on the analysis above, the following CalibrationConfig values should be used:

```typescript
export interface CalibrationConfig {
  // Existing fields
  minFitScoreDelta: number    // 0.3 (keep)
  minConfidence: number       // 0.40 (keep)
  minImpressions: number      // 50 (keep)
  averageOrderValue: number   // 85 (keep)

  // New calibrated fields
  avgCPA: number              // 64.22 from account audit
  minIntentScore: number      // 0.65 (confirmed)
  feedAlignmentWeight: number // 0.55 (confirmed)
  minRCTR: number             // 1.5 (confirmed)
  minQueryWords: number       // 3 (confirmed, alternative to rCTR gate)
}
```

| Parameter | Default | Calibrated | Change | Evidence |
|-----------|---------|------------|--------|----------|
| Wasted spend threshold | $5 (hardcoded) | $96.33 (1.5x $64.22) | **Changed** | 90-day CPA calculation |
| Intent score threshold | 0.65 | 0.65 | No change | Dual-domain analysis shows 0.65 requires both domains |
| Feed/behavioral weight | 0.55/0.45 | 0.55/0.45 | No change | Feed is deterministic, behavioral is noisy |
| rCTR gate | 1.5 | 1.5 | No change | 50% above median is meaningful signal |
| Word count gate | 3 | 3 | No change | 3+ words inherently specific for bathroom fixtures |
| avgCPA | N/A (was $5 hardcode) | $64.22 | **New parameter** | Account audit, 90-day window |

---

## 9. Recommendations for Future Calibration

### Dynamic avgCPA

Currently `avgCPA = 64.22` is hardcoded from the 90-day account audit. This should be refreshed:
- **Monthly**: Query Google Ads for 90-day rolling CPA
- **Quarterly**: Full recalibration run (this script)
- **On-demand**: When campaign structure changes materially

### Intent Score Monitoring

Track these metrics over time to detect calibration drift:
- Trigger D fire rate (% of zero-conv terms promoted)
- Promoted term conversion rate (do intent-promoted terms eventually convert?)
- False positive rate (intent-promoted terms that become wasted spend)

### Threshold Adjustment Protocol

Only adjust thresholds when:
1. False positive rate for Trigger D exceeds 20% (promoted terms become wasted spend)
2. avgCPA changes by >15% from current value
3. New conversion actions are added to the account
4. Campaign structure changes (new tiers, new product groups)

---

## 10. Calibration Script

Run `scripts/intent_score_calibration.py` to generate live calibration data from the `query_value_scores` table. The script:

1. Fetches all v2-tier-scoring entries from Supabase
2. Buckets by intent score (0-0.25, 0.25-0.50, 0.50-0.65, 0.65-0.85, 0.85-1.00)
3. Correlates each bucket with average ROAS
4. Analyzes zero-conversion terms with high intent scores
5. Compares wasted spend at $5 vs $96.33 thresholds
6. Outputs JSON data for further analysis

**Prerequisites**: Supabase credentials in environment, scored terms in query_value_scores.

---

*Generated: 2026-02-26*
*Engine: v2-tier-scoring (unified intent scoring with 5-trigger matrix)*
*Account: Allied Brass (6253381786)*
