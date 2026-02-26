# Action Queue + Scoring Engine — Continuation State

**Date:** 2026-02-26
**Status:** Partially fixed, needs deeper investigation

## What was done this session

### Pushed (commit cc886d94)
- ActionQueueRow now uses `term.actionReason || term.verdict` + ReasonBadge + Block/Constrain/Approve/Reject buttons
- ActionQueueTable accepts ClassifiedTerm[] instead of raw TermScore[]
- HeroSummary updated copy
- page.tsx wires classifiedTerms + recommendation hooks to Action Queue

### Pushed (commit de027634, from prior session)
- Migration 041: search_buildout_recommendations table (applied to production Supabase)
- tier-scoring/route.ts: persists actualRoas/totalConversions/totalCostMicros in model_inputs + auto-populates search candidates
- recommendations/route.ts: fixed identify_search_candidates field names

## What's STILL wrong (user's feedback)

User says: "no demotion action items only promotion and all the actions still don't make sense"

### Root cause analysis (incomplete — ran out of context)

The `determineAction()` function in `tier-scoring.ts:484-508` has this logic:
```
1. Wasted spend (0 conversions, >$5) → block (if HIGH) or constrain (if not HIGH)
2. Misplaced + funnelDepth[recommended] > funnelDepth[current] → 'promote'
3. Misplaced + funnelDepth[recommended] < funnelDepth[current] → 'constrain'
4. Otherwise → 'observe'
```

funnelDepth mapping: { HIGH: 0, MEDIUM: 1, LOW: 2 }

The `recommendedTier` is still computed by the OLD descriptive logic (line ~228):
```
picks tier with highest fit score (closest statistical match)
```

**THE PROBLEM**: The `recommendedTier` is still computed descriptively (best statistical fit), which for underperforming terms often picks LOW (because LOW's broken distribution has low ROAS). Then `determineAction()` sees funnelDepth[LOW]=2 > funnelDepth[HIGH]=0 → 'promote'.

So ALL underperforming terms get 'promote' (push to LOW) because:
- recommendedTier = LOW (statistical fit to broken data)
- funnelDepth[LOW] > funnelDepth[current] → direction is "promote"
- But "promote to LOW" for a BAD performer is wrong — it should be "constrain to HIGH"

The `determineAction()` only overrides for wasted spend (0 conversions). Terms with SOME conversions but poor ROAS still get the wrong direction.

### What needs to happen

1. **The recommendedTier computation itself needs fixing** — it should be prescriptive, not just picking best statistical fit. A term with 0.5x ROAS should be recommended to HIGH (constrain), not to LOW (just because LOW's broken distribution has similar ROAS).

2. **OR determineAction() needs to look at the term's actual ROAS** relative to tier expectations, not just rely on recommendedTier direction. For example:
   - If term ROAS < currentTier p25 → constrain (push toward HIGH)
   - If term ROAS > currentTier p75 → promote (push toward LOW)
   - This would be truly prescriptive

3. **The "Misplaced" badge** on all non-wasted terms needs more nuance — terms being constrained should show differently from terms being promoted.

### Key files to investigate
- `dashboard/src/lib/optimization/tier-scoring.ts` — `scoreTerm()` around line 228 (recommendedTier computation), `determineAction()` at line 484
- The research doc (34.1-RESEARCH.md) Pattern 1 code example shows the intended logic with actual ROAS comparison, but `determineAction()` doesn't do this

### How to verify
Open https://allied-feed-ops.vercel.app/tier-scoring, look at Action Queue. All terms say "Promote to LOW" — there should be a mix of promote/constrain/block based on whether the term is over or under-performing.
