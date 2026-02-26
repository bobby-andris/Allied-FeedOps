# Phase 34: Revenue Leakage and Execution - Research

**Researched:** 2026-02-25
**Domain:** Revenue leakage visualization, one-click tier movement approvals, optimistic UI, and history tracking
**Confidence:** HIGH

## Summary

Phase 34 transforms the existing tier scoring Action Queue (Phase 33.2) from a read-only view into an actionable decision layer. The scoring engine, distribution computations, impact estimates, and term-level data all exist. This phase adds: (1) a Revenue Leakage tab with a hero number showing total estimated leakage as a range with confidence coloring, (2) a flat list of flagged terms sorted by dollar impact with reason code badges (Misplaced, Wasted $, Under-invested), expandable rows, and inline approve/reject with optimistic updates, (3) ROAS distribution box plots showing tier overlap zones, (4) batch approve for high-confidence recommendations, (5) persist approvals to the existing `routing_recommendations` table (exists in production from 033b migration), (6) undo capability (status revert from approved to pending), and (7) a History tab showing all approve/reject/undo actions grouped by day.

The primary technical challenge is the UI interaction pattern (optimistic updates, inline approve/reject, sticky batch bar) -- not the data model. The `routing_recommendations` table already exists with the right schema (pending/accepted/rejected/expired statuses, search_term, custom_label_0, recommended_tier, confidence, review_status). The existing `policy_action_execution_log` table handles history logging. The `TermScore` type from Phase 33 already contains all needed fields (impact range, confidence, tier fit scores, reason codes).

**Primary recommendation:** Add two new tabs (Revenue Leakage, History) to the existing Tier Intelligence page using the same `Tabs` pattern from Phase 33.2. Reuse `useTierScoring` hook data for the leakage view. Create a new `useRecommendations` hook for CRUD operations against `routing_recommendations`. Build box plots using Recharts (already installed) with custom bar components. Create a new API route `/api/shopping-funnel/recommendations` for approve/reject/undo/batch operations.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Leakage hero number**: Range with midpoint format: "$1,200 - $3,400/mo (est. $2,300)". Confidence coloring (high/medium/low) as a dot indicator. "Last computed" timestamp displayed below the range.
- **Term list organization**: Flat list sorted by estimated revenue impact (highest first). Reason codes as colored badges: Misplaced, Wasted $, Under-invested. Badge + expandable detail: click to see specifics (ROAS value, current vs recommended tier, peer average, confidence score). No grouping by reason type -- single unified list.
- **ROAS distribution box plots**: Inline above the term list showing tier distributions side-by-side. Shows overlap zones between tiers. Always visible (not collapsible).
- **Approve/reject interaction**: Inline with optimistic update: click approve -> row instantly shows "Approved" state -> DB write in background. No confirmation modal, no extra step. After approval, row shows "Approved" status with an always-available [Undo] button. Reject is one-click with an optional (non-blocking) reason text field that appears after clicking reject.
- **Batch approve**: Sticky top bar above the term list: "N high-confidence recommendations -> [Approve All]". Applies to all terms with confidence > 0.80. Count updates as individual actions happen.
- **Execution model**: Approval writes to routing_recommendations table only (status: approved, timestamp, user). NO Google Ads API calls in this phase -- actual execution is Phase 36 or manual. This phase is the decision/approval layer, not the execution layer.
- **Undo behavior**: Undo reverts status from "approved" back to "pending" in routing_recommendations. Term reappears in the leakage list with original recommendation. Undo always available (no time limit) -- safe because no Google Ads changes until Phase 36. Future: if already executed to Google Ads (Phase 36+), undo writes a reversal to policy_action_execution_log.
- **History view**: History tab on the Tier Intelligence page (alongside Action Queue, Explorer, Revenue Leakage). Reverse-chronological log of all approve/reject/undo actions. Grouped by day with timestamps. Shows: term, action type (approved/rejected/undone), tier movement (from->to), timestamp. Rejected items show the optional reason note inline (as subtitle) if one was provided.
- **Page structure**: New "Revenue Leakage" and "History" tabs added to the existing Tier Intelligence page. Tab order: [Action Queue] [Explorer] [Revenue Leakage . N] [History]. Revenue Leakage tab label shows badge count of actionable items. Sidebar navigation stays as single entry -- tabs handle sub-navigation.
- **Action Queue relationship**: Revenue Leakage tab = see flagged terms, approve/reject (the decision view). Action Queue tab = see all approved movements awaiting execution (the tracking view). Approved items move from Revenue Leakage to Action Queue. Undo available in both Action Queue and History views.

### Claude's Discretion
- Loading states and skeleton patterns
- Exact spacing, typography, and color palette for badges
- Empty state design (when no leakage detected)
- Box plot visualization library choice
- Error handling for failed DB writes during optimistic updates
- How to handle stale data (e.g., scoring data updated while user is reviewing)

### Deferred Ideas (OUT OF SCOPE)
- Actual Google Ads API execution of tier movements -- Phase 36 (Automation and Experiments)
- Automated rule-based tier rebalancing -- Phase 36
- A/B experiments on tier assignments -- Phase 36
- Optimization impact tracking (before/after) -- Phase 37
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LEAK-01 | User can see total revenue leakage estimate as a hero number showing a range with confidence coloring | Existing `totalImpact` (ImpactRange with low/mid/high) from `useTierScoring` hook response. Add confidence dot coloring based on weighted average confidence of misplaced terms. Format as "$X - $Y/mo (est. $Z)". |
| LEAK-02 | User can view misplaced terms sorted by dollar impact with revenue estimate ranges (not point values) and reason codes | Existing `TermScore.isMisplaced`, `TermScore.impact` (ImpactRange), `TermScore.confidence`. Add reason code classification: "Misplaced" (tier mismatch), "Wasted $" (zero conversions + spend), "Under-invested" (impression share gap via keyword_metrics.avg_monthly_searches). |
| LEAK-03 | User can view wasted spend alerts for terms with zero conversions and high spend, with Block/Demote action buttons | Filter existing scored terms: `total_conversions === 0 && total_cost_micros > threshold`. Action buttons write to `routing_recommendations` with recommended_action = "funnel" and recommended_tier = "low" or campaign_negative. |
| LEAK-04 | User can view under-invested winners showing impression share gap (actual vs Keyword Planner market) with potential revenue gain | Join scored terms with `keyword_metrics` table for `avg_monthly_searches`. Gap = avg_monthly_searches - actual_impressions. Potential gain = gap * current_ctr * current_cvr * AOV. |
| LEAK-05 | User can view tier ROAS distribution box plots showing overlap zones between tiers | Existing `TierDistribution.metrics.roas` (p25/p50/p75/min/max) per tier from `useTierScoring` response. Build box plot with Recharts custom bar component showing all three tiers side-by-side with overlap zones highlighted. |
| LEAK-06 | User can see "Last computed" timestamp on all revenue leakage data | Existing `computedAt` field in `useTierScoring` response. Display below hero number as "Last computed [date]". |
| EXEC-01 | User can approve/reject individual tier movement recommendations with one click | New API route `POST /api/shopping-funnel/recommendations` upserts to `routing_recommendations` table (exists in production). Optimistic UI update in React state. |
| EXEC-02 | User can batch-approve all high-confidence recommendations (confidence > 0.80) in one action | Filter scored terms by `confidence.score > 0.80`, call recommendations API with array of terms. Sticky top bar with count and "Approve All" button. |
| EXEC-03 | User can undo a tier movement using negative_registry audit trail and criterion IDs | Undo = update `routing_recommendations.review_status` from "accepted" back to "pending". No Google Ads changes in this phase (Phase 36 handles actual execution + undo via negative_registry). |
| EXEC-04 | User can view movement history from policy_action_execution_log | New History tab reads from `routing_recommendations` (not policy_action_execution_log -- that table is for actual Google Ads executions in Phase 36). Group by day, show action type, tier movement, timestamp. |
| EXEC-05 | Recommendations persist to routing_recommendations table for asynchronous operator review | `routing_recommendations` table exists in production (created via 033b migration). Schema: search_term, custom_label_0, recommended_action, recommended_tier, confidence, review_status (pending/accepted/rejected/expired), accepted_at, accepted_by, metadata. Write on scoring computation, read on page load. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| recharts | ^3.7.0 (installed) | Box plot visualization for ROAS distributions | Already installed and used by DistributionChart. Custom bar components for box-and-whisker rendering. |
| simple-statistics | ^7.8.8 (installed) | Any additional statistical computation needed | Already installed and used by tier-scoring.ts. |
| @supabase/supabase-js | installed | CRUD operations on routing_recommendations | Already installed. Use createAdminClient for API route writes. |
| shadcn/ui components | installed | Tabs, Badge, Button, Card, Tooltip, Collapsible | Already installed. All needed UI primitives available. |
| lucide-react | installed | Icons (Check, X, Undo2, AlertTriangle, TrendingDown, etc.) | Already installed. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| formatDollars | @/lib/formatting | Dollar formatting | Already exists, used by HeroSummary and ImpactBadge |
| useTierScoring hook | existing | Scoring data source | Reuse for Revenue Leakage tab -- no new data fetch needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Recharts custom box plot | plotly.js | 3MB bundle, overkill for one chart type; Recharts already installed |
| Recharts custom box plot | @nivo/boxplot | New dependency, limited customization; Recharts bar+scatter can simulate box plots |
| Manual SVG box plot | Any charting library | More control but maintenance burden; Recharts composable API is sufficient |

**Installation:**
```bash
# No new installations needed -- all dependencies already installed
```

## Architecture Patterns

### Recommended Project Structure
```
dashboard/src/app/(dashboard)/tier-scoring/
  page.tsx                           # Add two new tabs: Revenue Leakage, History
  hooks/
    useTierScoring.ts                # Existing -- provides scoring data
    useRecommendations.ts            # NEW -- CRUD for routing_recommendations
  components/
    # Existing (reuse)
    ActionQueueTable.tsx             # MODIFY -- show undo button for approved items
    ActionQueueRow.tsx               # MODIFY -- add undo button
    HeroSummary.tsx                  # MODIFY -- enable "Apply Recommendations" button
    TierMovementArrow.tsx            # Reuse as-is
    ImpactBadge.tsx                  # Reuse as-is
    ConfidenceBadge.tsx              # Reuse as-is
    DistributionChart.tsx            # Reference for box plot pattern
    # NEW
    LeakageHero.tsx                  # Hero number with range + confidence dot
    LeakageTermList.tsx              # Flat sorted list with approve/reject
    LeakageTermRow.tsx               # Single term with inline actions
    ReasonBadge.tsx                  # Colored badge: Misplaced | Wasted $ | Under-invested
    BatchApproveBar.tsx              # Sticky bar: "N recommendations -> [Approve All]"
    RoasBoxPlot.tsx                  # Box plots for tier distributions
    HistoryView.tsx                  # History tab content
    HistoryDayGroup.tsx              # Day-grouped history entries

dashboard/src/app/api/shopping-funnel/
  recommendations/route.ts           # NEW -- POST (approve/reject/undo/batch), GET (load statuses)
```

### Pattern 1: Optimistic UI Updates
**What:** Update local state immediately on user action, then sync to DB in background. Revert on failure.
**When to use:** All approve/reject/undo operations (EXEC-01, EXEC-02, EXEC-03).
**Example:**
```typescript
// In useRecommendations hook
async function approve(term: TermScore) {
  // 1. Optimistic update -- instant UI feedback
  setStatuses(prev => ({
    ...prev,
    [term.searchTerm]: { status: 'accepted', updatedAt: new Date().toISOString() }
  }))

  // 2. Background DB write
  try {
    await fetch('/api/shopping-funnel/recommendations', {
      method: 'POST',
      body: JSON.stringify({
        action: 'approve',
        searchTerm: term.searchTerm,
        customLabel0: term.customLabel0,
        recommendedTier: term.recommendedTier,
        currentTier: term.currentTier,
        confidence: term.confidence.score,
        impact: term.impact,
      })
    })
  } catch (error) {
    // 3. Revert on failure
    setStatuses(prev => ({
      ...prev,
      [term.searchTerm]: { status: 'pending', updatedAt: null }
    }))
    // Show toast notification of failure
  }
}
```

### Pattern 2: Recommendation Status Overlay
**What:** Layer approval statuses on top of existing scoring data without duplicating state.
**When to use:** Revenue Leakage and Action Queue tabs share the same TermScore data but add approval status.
**Example:**
```typescript
// useRecommendations hook loads statuses from routing_recommendations
// and merges with TermScore[] from useTierScoring

interface RecommendationStatus {
  status: 'pending' | 'accepted' | 'rejected' | 'expired'
  updatedAt: string | null
  rejectionReason?: string
}

// Components receive TermScore + RecommendationStatus
// Revenue Leakage shows: pending + rejected terms (actionable)
// Action Queue shows: accepted terms (awaiting execution)
```

### Pattern 3: Reason Code Classification
**What:** Classify existing scored terms into reason categories for the unified leakage list.
**When to use:** Building the flat leakage term list (LEAK-02, LEAK-03, LEAK-04).
**Example:**
```typescript
type ReasonCode = 'misplaced' | 'wasted_spend' | 'under_invested'

function classifyLeakageReason(term: TermScore, keywordData?: KeywordMetrics): ReasonCode {
  // Zero conversions + meaningful spend = wasted
  if (term.totalConversions === 0 && term.totalCostMicros > 5_000_000) {
    return 'wasted_spend'
  }
  // Has keyword data showing impression gap = under-invested
  if (keywordData?.avg_monthly_searches && keywordData.avg_monthly_searches > term.totalImpressions * 2) {
    return 'under_invested'
  }
  // Default: tier mismatch = misplaced
  return 'misplaced'
}
```

### Pattern 4: Recharts Box Plot via Custom Shape
**What:** Build box-and-whisker plots using Recharts Bar + ReferenceLine + custom shape renderer.
**When to use:** ROAS distribution visualization (LEAK-05).
**Example:**
```typescript
// Use Recharts BarChart with custom bar shape to render box plot:
// - Vertical Bar: p25 to p75 (IQR box)
// - ReferenceLine at p50 (median line)
// - Error bars or scatter dots for min/max (whiskers)
// - Three bars side-by-side per tier (HIGH, MEDIUM, LOW)
// - Overlap zone = where p75 of lower tier > p25 of higher tier
//
// Data shape:
// [{ tier: 'HIGH', min, p25, p50, p75, max },
//  { tier: 'MEDIUM', min, p25, p50, p75, max },
//  { tier: 'LOW', min, p25, p50, p75, max }]
```

### Anti-Patterns to Avoid
- **Separate data fetch for leakage:** The scoring data already contains everything needed (impact, confidence, tier fit). Do NOT create a separate API endpoint that re-computes scores. Reuse `useTierScoring` data and overlay recommendation statuses.
- **Confirmation modals on approve/reject:** CONTEXT.md explicitly says "No confirmation modal, no extra step." Use optimistic inline updates.
- **Storing leakage amounts in routing_recommendations:** The impact values come from scoring computation and change when scores are refreshed. Store only the approval decision (status, timestamp, user) in `routing_recommendations`, not the computed dollar values. Dollar values come from the live scoring data.
- **Using policy_action_execution_log for Phase 34 history:** That table is for actual Google Ads execution (Phase 36). Phase 34 history should read from `routing_recommendations` status changes. The existing schema has `accepted_at`, `accepted_by` for tracking.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dollar formatting | Custom formatter | `formatDollars()` from `@/lib/formatting` | Already exists, used by 6+ components |
| Tier movement arrow | Custom tier display | `TierMovementArrow` component | Already exists with correct colors/icons |
| Impact range display | Custom range formatter | `ImpactBadge` component | Already exists with consistent formatting |
| Confidence display | Custom confidence UI | `ConfidenceBadge` component | Already exists with color coding |
| Distribution statistics | Custom math | `simple-statistics` functions | Already imported in tier-scoring.ts |

**Key insight:** Phase 33/33.1/33.2 built nearly all the UI primitives needed. Phase 34 is primarily about wiring approve/reject/undo interactions to the existing `routing_recommendations` table and adding the Revenue Leakage + History tab views.

## Common Pitfalls

### Pitfall 1: routing_recommendations Schema Mismatch
**What goes wrong:** The `routing_recommendations` table was created in migration 033b with `review_status` (not `approval_status`), `accepted` boolean (not `approved`), and `recommended_action` check constraint limited to ('global_block', 'competitor', 'branded', 'funnel').
**Why it happens:** CONTEXT.md says "approval writes to routing_recommendations table (status: approved)" but the actual column is `review_status` with values ('pending', 'accepted', 'rejected', 'expired').
**How to avoid:** Use the actual column names from the 033b migration: `review_status` (not status/approval_status), `accepted` (boolean), `accepted_at`, `accepted_by`. The recommended_action should be 'funnel' for tier movements.
**Warning signs:** SQL errors about missing columns or check constraint violations.

### Pitfall 2: Stale Scoring Data During Review
**What goes wrong:** User opens Revenue Leakage tab, reviews terms for 20 minutes, scores are recomputed in the background (10-min cache TTL), and impact values change while user is still reviewing.
**Why it happens:** The `useTierScoring` hook has a module-level cache with CACHE_TTL_MS = 10 minutes. A refresh by another tab or auto-refresh could change the data underneath.
**How to avoid:** Show the `computedAt` timestamp prominently (LEAK-06). When data refreshes, show a non-blocking banner: "Scores updated -- impact values may have changed." Don't auto-dismiss in-progress approvals.
**Warning signs:** User approves a term and the impact value visually changes on re-render.

### Pitfall 3: Optimistic Update Race Conditions
**What goes wrong:** User rapidly clicks approve on multiple terms. Some DB writes succeed, some fail. The local state and DB state diverge.
**Why it happens:** Each approve/reject triggers an independent fetch. Without request deduplication or queuing, failures can leave state inconsistent.
**How to avoid:** Use a request queue or debounced batch approach. For individual actions, catch errors and revert the specific term's status. For batch approve, use a single API call. Show per-row loading indicators (not full page loading).
**Warning signs:** Terms showing wrong status after page refresh.

### Pitfall 4: routing_recommendations May Not Exist
**What goes wrong:** Migration 037 created `query_value_scores` with CREATE IF NOT EXISTS from 033b, but it did NOT create `routing_recommendations`. The 033b migration file was labeled DEFERRED but may have been applied out-of-band.
**Why it happens:** Phase 32 migration 037 only cherry-picked specific tables from 033b (query_value_scores, experiment_registry, experiment_outcomes). `routing_recommendations` was not included.
**How to avoid:** Write a new migration (039 or similar) that uses CREATE TABLE IF NOT EXISTS for `routing_recommendations` with the exact schema from 033b. Include idempotent constraint creation. Apply before deploying the UI.
**Warning signs:** API route returns 500 with "relation routing_recommendations does not exist".

### Pitfall 5: Under-Invested Detection Requires keyword_metrics Join
**What goes wrong:** LEAK-04 (under-invested winners) requires `avg_monthly_searches` from the `keyword_metrics` table, but the current tier scoring API only returns `TermScore` without keyword data.
**Why it happens:** The scoring engine in `tier-scoring.ts` operates on `ExistingFunnelTerm` data which doesn't include keyword_metrics.
**How to avoid:** Either (a) enrich the scoring API response with keyword data from `keyword_metrics` table (join on search_term), or (b) make a separate lightweight query for keyword_metrics and merge client-side. Option (a) is cleaner but adds API complexity. Option (b) is simpler for Phase 34.
**Warning signs:** All terms classified as "Misplaced" with none as "Under-invested".

### Pitfall 6: Box Plot with Recharts
**What goes wrong:** Recharts does not have a native BoxPlot chart type. Building one requires custom bar shapes and careful positioning.
**Why it happens:** Recharts is a general charting library; box plots are specialized statistical visualizations.
**How to avoid:** Use the existing `DistributionChart` component as a reference. Build the box plot using a vertical BarChart with stacked/grouped bars for the IQR boxes, ReferenceLine for medians, and custom scatter points for whiskers. Keep it simple -- p25/p50/p75 bars are sufficient; full whiskers to min/max are optional.
**Warning signs:** Bars not aligning correctly, overlap zones not visible, responsive layout breaking.

## Code Examples

### routing_recommendations Upsert (Approve)
```typescript
// Source: 033b migration schema + API pattern from tier-scoring/route.ts
const { error } = await supabase.from('routing_recommendations').upsert(
  {
    search_term: term.searchTerm,
    custom_label_0: term.customLabel0,
    recommended_action: 'funnel',
    recommended_tier: term.recommendedTier.toLowerCase(), // DB uses lowercase
    reason_codes: ['tier_mismatch', `fit_delta_${term.fitScoreDelta.toFixed(2)}`],
    confidence: term.confidence.score,
    review_status: 'accepted',
    accepted: true,
    accepted_at: new Date().toISOString(),
    accepted_by: 'operator', // or auth user
    metadata: {
      current_tier: term.currentTier,
      impact: term.impact,
      approved_from: 'revenue_leakage_tab',
    },
  },
  { onConflict: 'search_term,custom_label_0' } // Need unique constraint
)
```

### routing_recommendations Undo
```typescript
// Revert from accepted back to pending
const { error } = await supabase.from('routing_recommendations')
  .update({
    review_status: 'pending',
    accepted: false,
    accepted_at: null,
    accepted_by: null,
    metadata: {
      // Preserve original metadata, add undo tracking
      ...existingMetadata,
      undone_at: new Date().toISOString(),
      undone_by: 'operator',
    },
  })
  .eq('search_term', term.searchTerm)
  .eq('custom_label_0', term.customLabel0)
```

### Batch Approve (High Confidence)
```typescript
// API route handler
export async function POST(request: NextRequest) {
  const body = await request.json()

  if (body.action === 'batch_approve') {
    const terms = body.terms as Array<{ searchTerm: string; customLabel0: string; recommendedTier: string; confidence: number }>

    // Upsert all in one call
    const rows = terms.map(t => ({
      search_term: t.searchTerm,
      custom_label_0: t.customLabel0,
      recommended_action: 'funnel',
      recommended_tier: t.recommendedTier.toLowerCase(),
      confidence: t.confidence,
      review_status: 'accepted',
      accepted: true,
      accepted_at: new Date().toISOString(),
      accepted_by: 'operator',
      reason_codes: ['batch_approved', 'high_confidence'],
      metadata: { approved_from: 'batch_approve_bar' },
    }))

    const { error } = await supabase.from('routing_recommendations')
      .upsert(rows, { onConflict: 'search_term,custom_label_0' })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ approved: rows.length })
  }
}
```

### Leakage Hero Number Component
```typescript
// LeakageHero.tsx pattern
function LeakageHero({ totalImpact, avgConfidence, computedAt }: LeakageHeroProps) {
  const confidenceLevel = avgConfidence >= 0.70 ? 'high' : avgConfidence >= 0.40 ? 'medium' : 'low'
  const dotColor = { high: 'bg-green-500', medium: 'bg-yellow-500', low: 'bg-red-500' }[confidenceLevel]

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${dotColor}`} />
          <span className="text-2xl font-bold">
            {formatDollars(totalImpact.low)} &ndash; {formatDollars(totalImpact.high)}/mo
          </span>
          <span className="text-lg text-muted-foreground">
            (est. {formatDollars(totalImpact.mid)})
          </span>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Last computed {new Date(computedAt).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
          })}
        </p>
      </CardContent>
    </Card>
  )
}
```

### History Query
```typescript
// Load history from routing_recommendations (not policy_action_execution_log)
const { data, error } = await supabase
  .from('routing_recommendations')
  .select('*')
  .in('review_status', ['accepted', 'rejected'])
  .order('created_at', { ascending: false })
  .limit(200)

// Group by day for display
const grouped = data.reduce((acc, row) => {
  const day = new Date(row.accepted_at || row.created_at).toLocaleDateString()
  if (!acc[day]) acc[day] = []
  acc[day].push(row)
  return acc
}, {} as Record<string, typeof data>)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded tier thresholds (3.6/3.1/2.6) | Distribution-based scoring with robust z-scores | Phase 33 (2026-02-25) | Dynamic, data-driven recommendations |
| No approval workflow | Read-only Action Queue with disabled "Apply" button | Phase 33.2 (2026-02-25) | Placeholder for Phase 34 |
| policy_action_execution_log for all history | routing_recommendations for approvals, PAEL for actual execution | Phase 34 (this phase) | Separates decision layer from execution layer |

**Deprecated/outdated:**
- `executeTierMovement()` in `tier-movement.ts` -- this function performs actual tier changes (writes to policy_action_execution_log, negative_registry, term_intent_state). Phase 34 does NOT call this. It only writes to routing_recommendations. Phase 36 will use executeTierMovement for actual Google Ads execution.

## Open Questions

1. **Does routing_recommendations table actually exist in production?**
   - What we know: Migration 033b SQL has CREATE TABLE for it. 033b was labeled DEFERRED. Migration 037 created query_value_scores from 033b but NOT routing_recommendations. Phase 32 summary says "Tables created out-of-band" for 033b but only explicitly verified query_value_scores.
   - What's unclear: Whether routing_recommendations was created out-of-band along with query_value_scores, or was missed.
   - Recommendation: Start Phase 34 implementation with a new migration (039) that uses CREATE TABLE IF NOT EXISTS for routing_recommendations. This is safe regardless of current state.

2. **routing_recommendations unique constraint on (search_term, custom_label_0)**
   - What we know: The 033b migration does NOT define a unique constraint on (search_term, custom_label_0). It only has indexes. But Supabase upsert requires onConflict to target a unique constraint.
   - What's unclear: Whether a unique constraint needs to be added.
   - Recommendation: Add a unique constraint in the new migration. Each search_term + custom_label_0 combination should have at most one active recommendation.

3. **Under-invested term detection (LEAK-04) data availability**
   - What we know: `keyword_metrics` table has `avg_monthly_searches` per search term. The tier scoring API does not currently return this data.
   - What's unclear: How many terms have keyword_metrics data. The table has 30-day TTL caching.
   - Recommendation: Add a lightweight keyword_metrics fetch to the recommendations API or enrich the scoring response. If data coverage is low, show "Under-invested" category only for terms with keyword data and show a "Keyword data unavailable" state for others.

4. **History tracking granularity**
   - What we know: CONTEXT.md wants history of approve/reject/undo actions. The routing_recommendations table only stores current state (no change log).
   - What's unclear: Whether to add a separate history/audit table or use the metadata JSONB column to track state changes.
   - Recommendation: Use the `metadata` JSONB column to append a history array on each state change: `{ history: [{ action: 'approved', at: '...', by: '...' }, { action: 'undone', at: '...', by: '...' }] }`. This avoids a new table while still providing full history.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 3.2.4 |
| Config file | `dashboard/vitest.config.ts` |
| Quick run command | `cd dashboard && npx vitest run --reporter=verbose` |
| Full suite command | `cd dashboard && npx vitest run` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LEAK-01 | Hero number formats range with confidence coloring | unit | `npx vitest run src/app/\\(dashboard\\)/tier-scoring/__tests__/leakage-hero.test.ts -x` | Wave 0 |
| LEAK-02 | Reason code classification (misplaced/wasted/under-invested) | unit | `npx vitest run src/app/\\(dashboard\\)/tier-scoring/__tests__/reason-codes.test.ts -x` | Wave 0 |
| LEAK-03 | Wasted spend filter (zero conversions + high spend) | unit | `npx vitest run src/app/\\(dashboard\\)/tier-scoring/__tests__/reason-codes.test.ts -x` | Wave 0 |
| LEAK-04 | Under-invested gap calculation | unit | `npx vitest run src/app/\\(dashboard\\)/tier-scoring/__tests__/reason-codes.test.ts -x` | Wave 0 |
| LEAK-05 | Box plot data transformation | unit | `npx vitest run src/app/\\(dashboard\\)/tier-scoring/__tests__/box-plot.test.ts -x` | Wave 0 |
| LEAK-06 | computedAt timestamp display | manual-only | Visual check -- timestamp renders correctly | N/A |
| EXEC-01 | Approve writes to routing_recommendations | unit | `npx vitest run src/app/api/shopping-funnel/recommendations/__tests__/route.test.ts -x` | Wave 0 |
| EXEC-02 | Batch approve filters by confidence > 0.80 | unit | `npx vitest run src/app/api/shopping-funnel/recommendations/__tests__/route.test.ts -x` | Wave 0 |
| EXEC-03 | Undo reverts status to pending | unit | `npx vitest run src/app/api/shopping-funnel/recommendations/__tests__/route.test.ts -x` | Wave 0 |
| EXEC-04 | History query groups by day | unit | `npx vitest run src/app/\\(dashboard\\)/tier-scoring/__tests__/history.test.ts -x` | Wave 0 |
| EXEC-05 | Recommendations persist with correct schema | unit | `npx vitest run src/app/api/shopping-funnel/recommendations/__tests__/route.test.ts -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd dashboard && npx vitest run --reporter=verbose`
- **Per wave merge:** `cd dashboard && npx vitest run && npm run build`
- **Phase gate:** Full suite green + build passes before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `dashboard/src/app/(dashboard)/tier-scoring/__tests__/leakage-hero.test.ts` -- covers LEAK-01
- [ ] `dashboard/src/app/(dashboard)/tier-scoring/__tests__/reason-codes.test.ts` -- covers LEAK-02, LEAK-03, LEAK-04
- [ ] `dashboard/src/app/(dashboard)/tier-scoring/__tests__/box-plot.test.ts` -- covers LEAK-05
- [ ] `dashboard/src/app/(dashboard)/tier-scoring/__tests__/history.test.ts` -- covers EXEC-04
- [ ] `dashboard/src/app/api/shopping-funnel/recommendations/__tests__/route.test.ts` -- covers EXEC-01, EXEC-02, EXEC-03, EXEC-05

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `dashboard/src/app/(dashboard)/tier-scoring/` -- complete component tree, hooks, types
- Codebase analysis: `dashboard/src/lib/optimization/tier-scoring.ts` -- scoring engine, all computation functions
- Codebase analysis: `dashboard/src/lib/optimization/tier-scoring.types.ts` -- TermScore, ImpactRange, GroupDistributions
- Codebase analysis: `supabase/migrations/033b_DEFERRED_optimization_control_plane.sql` -- routing_recommendations schema
- Codebase analysis: `dashboard/src/lib/intent/tier-movement.ts` -- existing execution pipeline (Phase 36, not Phase 34)
- Codebase analysis: `docs/database/SCHEMA.md` -- policy_action_execution_log, negative_registry, term_intent_state schemas

### Secondary (MEDIUM confidence)
- Phase 32/33 research and summaries -- confirms table creation status, schema extensions
- CONTEXT.md decisions -- UI interaction patterns, page structure

### Tertiary (LOW confidence)
- Recharts box plot capability -- Recharts does not have native box plot; custom implementation needed. Confidence is LOW on exact implementation pattern but HIGH that it is feasible with custom bar shapes.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and proven in Phases 33/33.1/33.2
- Architecture: HIGH -- extends existing page with 2 new tabs; data model already exists; patterns well-established
- Pitfalls: HIGH -- routing_recommendations schema is documented in migration 033b; optimistic UI is standard React pattern
- Box plot implementation: MEDIUM -- Recharts custom shapes require experimentation; DistributionChart provides reference

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable domain, no external dependencies changing)
