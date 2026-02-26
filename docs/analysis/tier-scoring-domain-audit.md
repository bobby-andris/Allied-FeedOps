# Tier Scoring System — Domain Audit (v2 — Corrected)

**Date:** 2026-02-25
**Updated with:** Bobby's authoritative domain knowledge document
**Reference:** `docs/domain/waterfall-shopping-structure.md`

**Short answer: No. The system has fundamental domain misunderstandings that produce unreliable recommendations.**

---

## The Critical Paradox the System Misses

**Target ROAS Setting** (the constraint on the algorithm) is INVERSE to **Actual ROAS** (the result):

| Tier | Campaign Priority | Target ROAS Setting | Actual ROAS Result | Why |
|------|-------------------|--------------------|--------------------|-----|
| HIGH | Highest | **Highest** (constrains bidding) | **Lowest** | Broad traffic, algorithm bids conservatively |
| MEDIUM | Medium | Moderate | Moderate | Filtered traffic |
| LOW | Lowest | **Lowest** (removes ceiling) | **Highest** | High-intent only, algorithm bids aggressively |

The system must understand: LOW priority campaigns have the LOWEST target ROAS setting so the algorithm bids AGGRESSIVELY on the high-intent terms that survive the negative keyword gauntlet. This produces the HIGHEST actual ROAS.

---

## What the Scoring System Gets Wrong

### 1. Default Distributions Are Inverted

When there's insufficient per-group data (ALL groups currently), the system falls back to:

```
Current (WRONG):                          Correct:
HIGH:   ROAS p50=5.5 (highest)           HIGH:   ROAS p50=1.2 (lowest — broad traffic)
MEDIUM: ROAS p50=3.0 (middle)            MEDIUM: ROAS p50=3.0 (middle)
LOW:    ROAS p50=1.2 (lowest)            LOW:    ROAS p50=5.5 (highest — high-intent)
```

**Impact:** Every recommendation when using defaults is systematically backwards.

### 2. "Demote" Button for Wasted Spend Goes to Wrong Tier

Current code (`LeakageTermRow.tsx:84`):
```tsx
handleDemote → onApprove(term, { recommendedAction: 'funnel', recommendedTier: 'low' })
```

This sends wasted-spend terms to LOW (the most aggressive tier). Per the domain document:
- **Wasted spend "Demote"** should push to **HIGH** — where the restrictive tROAS/CPC caps constrain spending
- LOW is the WORST place for a non-converting term — it removes the bidding ceiling

### 3. Misplaced Term Actions Don't Match Domain Model

The system shows "Approve/Reject" for misplaced terms. The domain requires two distinct actions:

| Domain Action | Meaning | Mechanism | Current System |
|--------------|---------|-----------|---------------|
| **Promote** (push DOWN funnel) | High-performing term trapped in broad tier | Add negative to current tier → cascades to lower priority | Not distinguished |
| **Demote** (pull UP funnel) | Poor performer wasting aggressive-bid budget | Remove negatives from upper tiers → caught by higher priority | Not distinguished |

"Approve" doesn't communicate whether the user is promoting or demoting. The recommendation direction matters.

### 4. Under-Invested Logic Is Inverted

Current code (`reason-codes.ts:48-49`):
```tsx
if (term.impact.direction === 'upward' && ...)  // "upward" = toward HIGH in code
```

But per domain doc, under-invested terms should go to **LOW** (more aggressive bidding). The code's `tierRank` has `{ HIGH: 3, MEDIUM: 2, LOW: 1 }`, so "upward" means toward HIGH — the opposite of what under-invested needs.

**Under-invested terms**: High ROAS + low volume in HIGH/MEDIUM → Route to LOW where aggressive bidding captures the profitable volume.

### 5. NLP Intent Alignment Is Wrong

Current (`tier-scoring.ts:307-318`):
```
branded + HIGH → 0.9 alignment     WRONG: branded is high-intent → belongs in LOW
competitor + LOW → 0.8 alignment    DEBATABLE: competitor queries may be defensive
product-specific + MEDIUM → 0.7    ROUGHLY OK
```

Correct alignment:
```
branded → LOW (high-intent, high-converting, let algorithm bid aggressively)
broad/generic → HIGH (discovery, constrain bidding)
product-specific → MEDIUM or LOW depending on specificity
```

### 6. "Promote" and "Demote" Terminology Is Confusing

In the waterfall domain:
- "Promote" = push DOWN the funnel (toward LOW) — counterintuitive but correct
- "Demote" = push UP the funnel (toward HIGH)

The code uses "upward" and "downward" based on `tierRank` where HIGH=3, LOW=1. This means:
- Code "upward" = toward HIGH = domain "demote"
- Code "downward" = toward LOW = domain "promote"

This inversion permeates the impact estimation and reason code classification.

---

## Walking Through Screenshot Examples (Corrected Analysis)

### "valet rods" — HIGH → MEDIUM, Misplaced

- Current: HIGH (top of funnel, catches all "valet rod" queries)
- ROAS: 7.5 (shown in verdict text)
- System recommendation: Move to MEDIUM

**Corrected analysis:** A term with 7.5 ROAS in HIGH is massively outperforming its tier. In the waterfall model, this term is a high-intent converter trapped in the broad/constrained tier. The correct action is **Promote to LOW** — add "valet rods" as a negative in HIGH (and possibly MEDIUM) so it cascades to LOW, where the algorithm can bid aggressively and capture maximum volume from this profitable term.

The system recommending MEDIUM is a half-measure. It should recommend LOW.

### "bathroom shelves" — HIGH → LOW, Wasted $

- Current: HIGH (top of funnel)
- Zero conversions, meaningful spend
- System: Block / Demote (to LOW)

**Corrected analysis:** "bathroom shelves" is a broad, non-converting query. Per the domain doc:
- **Block** is correct if the term is irrelevant garbage
- **"Demote to HIGH"** (keep in HIGH, constrained) is correct if the term is relevant but low-converting — the HIGH tier's restrictive settings will naturally limit spend
- **Demote to LOW** is the WORST action — it sends a money-losing term to the tier with the most aggressive bidding

Since it's already in HIGH, the real options should be:
1. **Block** — add account-level negative
2. **Keep** — it's already in the most restrictive tier, so spending is already capped

---

## Priority-Wasted Spend Insight (from domain doc)

> "Your highest priority recommendations must identify terms in the MEDIUM and LOW tiers that are spending heavily with low Actual ROAS. Because these tiers have the most aggressive (lowest) Target ROAS settings, bad terms here will rapidly drain the budget."

The current wasted-spend detection (`reason-codes.ts:40`) checks for zero conversions + meaningful spend regardless of tier. But the **urgency** differs dramatically by tier:
- Wasted spend in HIGH: Low priority — the restrictive settings are already capping damage
- Wasted spend in MEDIUM: Medium priority — moderate bidding aggression
- Wasted spend in LOW: **CRITICAL** — the algorithm is bidding aggressively on a non-converter

The UI should sort/prioritize wasted spend by tier urgency: LOW > MEDIUM > HIGH.

---

## Display Bugs (unchanged from v1)

1. **"Current ROAS" shows fit score, not actual ROAS** — `tierFitScores[currentTier]` is z-score, not ROAS
2. **"X of 3 terms scored"** — `totalTerms` counts tier aggregate rows (always 3), not search terms
3. **"View full scorecard"** — sets state for Action Queue tab, invisible on Revenue Leakage tab

---

## Comprehensive Fix List (Priority Order)

### P0: Fix default distributions (BLOCKER)
Swap HIGH and LOW ROAS/CVR/CPC/CTR distributions in `DEFAULT_DISTRIBUTIONS`. This corrects all fallback-based recommendations.

### P0: Fix "Demote" action for wasted spend
- Current: sends to LOW (`recommendedTier: 'low'`)
- Correct: sends to HIGH (`recommendedTier: 'high'`) — where restrictive settings constrain spending
- For terms already in HIGH with wasted spend: only offer Block (they're already in the most restrictive tier)

### P1: Fix under-invested direction logic
- Under-invested = high ROAS + low volume → should route to LOW for aggressive bidding
- Current code checks `direction === 'upward'` (toward HIGH) — should check `direction === 'downward'` (toward LOW)

### P1: Fix NLP intent alignment
- Branded → LOW (high-intent, high-converting)
- Broad/generic → HIGH (discovery, constrain)
- Product-specific → MEDIUM

### P1: Add tier-aware wasted spend urgency
- Wasted spend in LOW = CRITICAL (most aggressive bidding, max budget drain)
- Wasted spend in MEDIUM = HIGH priority
- Wasted spend in HIGH = LOW priority (already constrained)

### P2: Clarify action semantics
Replace "Approve/Reject" with domain-specific actions:
- "Promote to LOW" (add negative, let algorithm bid aggressively)
- "Demote to HIGH" (remove negatives, constrain bidding)
- "Block" (account-level negative)

### P3: Fix display bugs
- Show actual ROAS (needs to be added to TermScore or computed from existing fields)
- Fix totalTerms counting
- Fix View Scorecard cross-tab navigation

### P4: Wire to Google Ads API
- Approved promotions → add negative keywords via shared lists
- Approved demotions → remove negative keywords
- Approved blocks → add account-level negatives
- The codebase already has `removeSharedKeyword` in `service.ts`

---

## Summary

The scoring ENGINE (distribution math, z-scores, confidence) is sound. The DOMAIN MODEL feeding it is inverted. Fixing the defaults, action semantics, and direction logic will make the system's recommendations trustworthy. The existing Google Ads API integration already supports the execution mechanism — it just needs to be wired to the approval flow.
