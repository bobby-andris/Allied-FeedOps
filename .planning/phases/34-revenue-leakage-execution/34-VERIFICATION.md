---
phase: 34-revenue-leakage-execution
verified: 2026-02-25T20:10:00Z
status: gaps_found
score: 10/11 must-haves verified
re_verification: false
gaps:
  - truth: "Wasted spend Block action stores 'global_block' in routing_recommendations"
    status: failed
    reason: "useRecommendations.approve() only accepts (term: TermScore) — no ApproveOptions parameter. When LeakageTermRow calls onApprove(term, { recommendedAction: 'global_block' }), the options object is silently dropped. The API always receives the default 'funnel' recommended_action, never 'global_block'. Block and Approve produce identical DB records."
    artifacts:
      - path: "dashboard/src/app/(dashboard)/tier-scoring/hooks/useRecommendations.ts"
        issue: "approve() signature is (term: TermScore) with no options param. Line 40/111 both confirm this."
      - path: "dashboard/src/app/(dashboard)/tier-scoring/components/LeakageTermRow.tsx"
        issue: "TODO on line 64 acknowledges badge differentiation (Block/Demote/Approved) is incomplete — hook doesn't pass metadata back."
    missing:
      - "Add ApproveOptions parameter to useRecommendations.approve(): approve(term: TermScore, options?: ApproveOptions) => Promise<void>"
      - "Pass options.recommendedAction to the POST body in useRecommendations.approve() so Block actions send recommended_action='global_block' to the API"
      - "Update UseRecommendationsReturn interface approve signature to match"
      - "Resolve TODO in LeakageTermRow.getApprovedBadgeText() to distinguish Block/Demote/Approved badges using stored metadata"
human_verification:
  - test: "Open the Revenue Leakage tab, find a wasted_spend term, click Block, then open Supabase routing_recommendations table and verify recommended_action='global_block'"
    expected: "Row in routing_recommendations has recommended_action='global_block' for the blocked term"
    why_human: "Cannot query production Supabase from verifier; end-to-end persistence requires live DB"
  - test: "Approve a term in Revenue Leakage tab, then navigate to Action Queue tab and verify the term appears at the top with an Undo button"
    expected: "Approved term moves to top of Action Queue with green Undo button visible"
    why_human: "Cross-tab state flow requires browser interaction"
  - test: "Click 'Apply Recommendations' on HeroSummary and verify it activates the Revenue Leakage tab"
    expected: "Active tab switches to Revenue Leakage, badge count visible"
    why_human: "Tab switching behavior requires browser interaction"
  - test: "Approve a term, then click Undo, then verify the term returns to Revenue Leakage tab pending state"
    expected: "Term reappears in Revenue Leakage list with Approve/Reject buttons"
    why_human: "Optimistic update revert flow requires browser interaction"
---

# Phase 34: Revenue Leakage Execution Verification Report

**Phase Goal:** Users can identify revenue opportunities with dollar-value estimates and act on them with one-click tier movements that persist and can be undone
**Verified:** 2026-02-25T20:10:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | User sees hero number with dollar range and confidence dot on Revenue Leakage tab | VERIFIED | LeakageHero.tsx: range format `{formatDollars(low)} - {formatDollars(high)}/mo (est. {formatDollars(mid)})` with `getConfidenceDotColor()` returning green/yellow/red based on avgConfidence thresholds (0.70/0.40) |
| 2  | User sees "Last computed" timestamp on revenue leakage data | VERIFIED | LeakageHero.tsx line 69: `Last computed {formatTimestamp(computedAt)}` renders ISO string as formatted date |
| 3  | User sees misplaced terms sorted by dollar impact with reason code badges | VERIFIED | classifyAllTerms() sorts by `impact.mid` descending; LeakageTermRow shows ReasonBadge (Misplaced/Wasted $/Under-invested) |
| 4  | User sees wasted spend terms with Block/Demote buttons | VERIFIED | LeakageTermRow lines 156-198: `isWastedSpend` flag shows Block (global_block) and Demote (funnel/low) instead of Approve/Reject |
| 5  | Block action stores 'global_block' in routing_recommendations | FAILED | useRecommendations.approve() drops the ApproveOptions — recommendedAction:'global_block' never reaches the API. Both Block and standard Approve write recommended_action='funnel'. |
| 6  | User sees ROAS box plots showing tier distributions | VERIFIED | RoasBoxPlot.tsx: pure CSS box plot with aggregateDistributions() + detectOverlaps() confirmed by 7 passing unit tests |
| 7  | User can one-click approve/reject with optimistic updates that revert on failure | VERIFIED | useRecommendations hook: approve/reject/undo all implement optimistic update pattern (save previous, update immediately, revert on error) |
| 8  | User can batch-approve high-confidence terms (>0.80) in one action | VERIFIED | BatchApproveBar shows count of confidence>0.80 pending terms; page.tsx filters `pendingTerms.filter(t => t.confidence.score > 0.80)` before passing to batchApprove() |
| 9  | Approved terms persist to routing_recommendations table | VERIFIED | API route (route.ts) upserts with review_status='accepted', accepted=true, accepted_at, accepted_by='operator' using unique constraint on (search_term, custom_label_0) |
| 10 | User can undo an approval (status reverts to pending) | VERIFIED | undo() in hook and API route: sets review_status='pending', accepted=false, accepted_at=null, appends history entry. Available in both Revenue Leakage rows and History tab |
| 11 | User can view day-grouped history of all approval decisions | VERIFIED | HistoryView.tsx + groupHistoryByDay() function confirmed by 5 passing history tests; shows action icon, term, tier movement, timestamp, undo button for accepted entries |

**Score:** 10/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/039_routing_recommendations_table.sql` | Table with upsert unique constraint | VERIFIED | CREATE TABLE IF NOT EXISTS with unique constraint on (search_term, custom_label_0), check constraints for recommended_action/review_status, RLS enabled |
| `dashboard/src/app/api/shopping-funnel/recommendations/route.ts` | GET + POST CRUD route | VERIFIED | Exports GET (queue/history/statuses) and POST (approve/reject/undo/batch_approve); uses createAdminClient |
| `dashboard/src/app/api/shopping-funnel/recommendations/__tests__/route.test.ts` | 10 unit tests | VERIFIED | 10/10 passing: all 4 POST actions, global_block override, GET history/statuses, edge cases |
| `dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts` | classifyLeakageReason, classifyAllTerms, REASON_LABELS, REASON_COLORS | VERIFIED | All 4 exports present; wasted_spend detection uses totalConversions/totalCostMicros; 14 tests pass |
| `dashboard/src/app/(dashboard)/tier-scoring/hooks/useRecommendations.ts` | approve/reject/undo/batchApprove with optimistic updates | PARTIAL | All 4 methods present with optimistic update/revert. Gap: approve() missing ApproveOptions parameter |
| `dashboard/src/app/(dashboard)/tier-scoring/components/LeakageHero.tsx` | Hero card with range + confidence dot + timestamp | VERIFIED | Full implementation; exports getConfidenceDotColor/formatTimestamp for testing; 7 unit tests pass |
| `dashboard/src/app/(dashboard)/tier-scoring/components/RoasBoxPlot.tsx` | Pure CSS box plots with overlap detection | VERIFIED | aggregateDistributions() + detectOverlaps() exported for testing; 7 unit tests pass |
| `dashboard/src/app/(dashboard)/tier-scoring/components/LeakageTermRow.tsx` | Inline approve/reject + Block/Demote for wasted_spend + state transitions | VERIFIED (with note) | All state transitions implemented. TODO on line 64: badge text ("Approved"/"Blocked"/"Demoted") not yet differentiated |
| `dashboard/src/app/(dashboard)/tier-scoring/components/LeakageTermList.tsx` | Flat list with pagination + accepted-term filtering | VERIFIED | Filters accepted terms from display; PAGE_SIZE=20 with "Show N more"; empty state |
| `dashboard/src/app/(dashboard)/tier-scoring/components/BatchApproveBar.tsx` | Sticky bar with high-confidence count + Approve All | VERIFIED | Sticky positioning; returns null when count<=0; loading state support |
| `dashboard/src/app/(dashboard)/tier-scoring/components/ReasonBadge.tsx` | 3-color reason badge | VERIFIED | Uses REASON_COLORS from reason-codes.ts |
| `dashboard/src/app/(dashboard)/tier-scoring/components/HistoryView.tsx` | Day-grouped history with groupHistoryByDay() exported | VERIFIED | groupHistoryByDay exported as pure function; loads on mount; refresh button; empty state |
| `dashboard/src/app/(dashboard)/tier-scoring/components/HistoryDayGroup.tsx` | Entry rows with action icons, tier arrows, timestamps, undo | VERIFIED | Check/X/Undo2 icons; getActionLabel distinguishes Approved/Rejected/Undone; rejection reason subtitle |
| `dashboard/src/app/(dashboard)/tier-scoring/page.tsx` | 4 tabs: Action Queue, Explorer, Revenue Leakage (badge), History | VERIFIED | 4 TabsTrigger elements; controlled Tabs state; Revenue Leakage badge count; all 4 TabsContent wired |
| `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx` | Accepts recommendationStatuses + onUndo, shows accepted first | VERIFIED | Partitions accepted terms to top; passes showUndo={true} + onUndo to accepted rows |
| `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx` | Optional Undo button | VERIFIED | showUndo prop renders Undo2 ghost button with stopPropagation |
| `dashboard/src/app/(dashboard)/tier-scoring/components/HeroSummary.tsx` | Apply Recommendations button enabled + fires onApplyClick | VERIFIED | Button has onClick={onApplyClick}, no disabled prop, no tooltip wrapper |
| `dashboard/src/lib/optimization/tier-scoring.types.ts` | TermScore extended with totalConversions + totalCostMicros | VERIFIED | Lines 82-83 confirm both fields added with LEAK-03 comment |
| `dashboard/src/app/(dashboard)/tier-scoring/__tests__/reason-codes.test.ts` | 14 tests | VERIFIED | 14/14 passing |
| `dashboard/src/app/(dashboard)/tier-scoring/__tests__/leakage-hero.test.ts` | 7 tests | VERIFIED | 7/7 passing |
| `dashboard/src/app/(dashboard)/tier-scoring/__tests__/box-plot.test.ts` | 7 tests | VERIFIED | 7/7 passing |
| `dashboard/src/app/(dashboard)/tier-scoring/__tests__/history.test.ts` | 10 tests | VERIFIED | 10/10 passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| page.tsx | useRecommendations | `const recommendations = useRecommendations()` | WIRED | Line 38 of page.tsx |
| page.tsx | classifyAllTerms | `import { classifyAllTerms }` + `useMemo` | WIRED | Lines 11, 52-55 of page.tsx |
| page.tsx | LeakageTermList | `onApprove={recommendations.approve}` | PARTIAL | Type signature mismatch: LeakageTermList expects `(term, options?)` but recommendations.approve is `(term)`. TypeScript accepts this (extra args dropped), but ApproveOptions are never forwarded to API |
| LeakageTermRow | useRecommendations.approve | `onApprove(term, { recommendedAction: 'global_block' })` | NOT WIRED | Block button correctly calls onApprove with global_block option, but the option is silently dropped by recommendations.approve() |
| useRecommendations.approve | API POST | `fetch('/api/shopping-funnel/recommendations', { method: 'POST', body: JSON.stringify({ action: 'approve', ... }) })` | PARTIAL | Correct endpoint and action, but `recommendedAction` field never passed in body for Block/Demote actions |
| API route POST | routing_recommendations | `supabase.from('routing_recommendations').upsert(...)` | WIRED | Uses onConflict:'search_term,custom_label_0'; review_status='accepted' |
| useRecommendations.undo | API POST | `fetch POST { action: 'undo' }` | WIRED | Correct undo flow; API reverts to pending |
| page.tsx HeroSummary | Revenue Leakage tab | `onApplyClick={() => setActiveTab('leakage')}` | WIRED | Controlled Tabs with useState('actions') |
| page.tsx ActionQueueTable | useRecommendations.undo | `onUndo={recommendations.undo}` | WIRED | Line 179 of page.tsx |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LEAK-01 | 34-03, 34-04 | Hero number with range and confidence coloring | SATISFIED | LeakageHero with getConfidenceDotColor (green>=0.70 / yellow>=0.40 / red<0.40); 7 unit tests |
| LEAK-02 | 34-02, 34-03, 34-04 | Misplaced terms sorted by dollar impact with reason codes | SATISFIED | classifyAllTerms sorts by impact.mid desc; ReasonBadge shows Misplaced/Wasted$/Under-invested |
| LEAK-03 | 34-01, 34-02, 34-03, 34-04 | Wasted spend Block/Demote actions | PARTIAL | Block/Demote buttons exist in UI with correct calls; but ApproveOptions dropped by useRecommendations.approve() — global_block never persisted |
| LEAK-04 | 34-02, 34-03, 34-04 | Under-invested terms with impression gap | SATISFIED | classifyLeakageReason detects under_invested when keywordData.avgMonthlySearches present + upward direction; under_invested badge in UI |
| LEAK-05 | 34-03, 34-04 | ROAS box plots showing tier overlap zones | SATISFIED | RoasBoxPlot with aggregateDistributions() + detectOverlaps(); 7 unit tests confirm data transformation |
| LEAK-06 | 34-03, 34-04 | "Last computed" timestamp on all leakage data | SATISFIED | LeakageHero shows formatTimestamp(computedAt); test confirms rendering |
| EXEC-01 | 34-01, 34-02, 34-03, 34-04 | One-click approve/reject per term | SATISFIED | LeakageTermRow with inline approve/reject; optimistic updates in useRecommendations |
| EXEC-02 | 34-01, 34-02, 34-03, 34-04 | Batch-approve high-confidence (>0.80) | SATISFIED | BatchApproveBar + page.tsx filtering; batchApprove() upserts all in one call |
| EXEC-03 | 34-01, 34-02, 34-04 | Undo tier movement (status revert) | SATISFIED (PARTIAL per plan) | undo() reverts to pending in DB + optimistic update; plan notes this phase only covers routing_recommendations revert, not Google Ads criterion IDs (Phase 36) |
| EXEC-04 | 34-04 | View movement history | SATISFIED (PARTIAL per plan) | History tab reads from routing_recommendations; day-grouped entries; plan notes PAEL (execution log) is Phase 36 |
| EXEC-05 | 34-01, 34-02, 34-04 | Recommendations persist to routing_recommendations | SATISFIED | Migration 039 creates table; API upserts on (search_term, custom_label_0); statuses loaded on mount |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `LeakageTermRow.tsx` | 64 | `// TODO: when hook passes metadata back, use it to distinguish Block/Demote/Approved` | Warning | Badge text always shows "Approved" for all accepted states (Block, Demote, standard Approve). Non-blocking for primary flow but incomplete per LEAK-03 spec |
| `useRecommendations.ts` | 40, 111 | `approve: (term: TermScore) => Promise<void>` — missing ApproveOptions | Blocker | The `recommendedAction: 'global_block'` from Block actions is silently dropped. All approvals write `recommended_action='funnel'` to DB regardless of Block/Demote/Approve |

### Human Verification Required

#### 1. Block Action Persistence (LEAK-03)

**Test:** Find a wasted_spend term in Revenue Leakage tab, click Block. Open Supabase dashboard, query routing_recommendations WHERE search_term = '{term}'.
**Expected:** Row has `recommended_action='global_block'` and `review_status='accepted'`
**Why human:** Cannot query production Supabase from verifier; and this test is currently expected to FAIL due to the ApproveOptions gap

#### 2. Cross-tab Approve Flow

**Test:** Approve a term in Revenue Leakage, then click Action Queue tab.
**Expected:** Approved term appears at top of Action Queue with Undo button visible.
**Why human:** Cross-tab state transitions require browser interaction

#### 3. Apply Recommendations Navigation

**Test:** Click "Apply Recommendations" button on Action Queue hero card.
**Expected:** Active tab switches to Revenue Leakage; badge count is visible.
**Why human:** Tab switching requires browser interaction

#### 4. End-to-End Undo Flow

**Test:** Approve a term, click Undo on the row.
**Expected:** Term reverts to Revenue Leakage list with Approve/Reject buttons; Action Queue count decreases.
**Why human:** Optimistic update flow requires browser interaction

## Gaps Summary

One gap blocking full LEAK-03 goal achievement: The `useRecommendations.approve()` hook does not accept an `ApproveOptions` parameter, so Block actions from `LeakageTermRow` (which pass `{ recommendedAction: 'global_block' }`) have those options silently dropped. Every approval — whether a standard Approve, a Block, or a Demote — writes `recommended_action='funnel'` to the database. The API route correctly handles `recommendedAction` in the POST body (line 152), and the DB constraint allows `'global_block'`. The gap is entirely in the hook's missing parameter forwarding.

The fix is small and isolated: update `useRecommendations.approve()` to accept an optional `ApproveOptions` (or equivalent) parameter and forward `recommendedAction` to the POST body. This would fully satisfy LEAK-03.

All other 10 truths are verified. 58/58 unit tests pass. Build passes. The dashboard page correctly wires all 4 tabs, HeroSummary button navigates to Revenue Leakage, Action Queue shows undo buttons for accepted items, and the History tab day-groups entries with the correct action labels.

---

_Verified: 2026-02-25T20:10:00Z_
_Verifier: Claude (gsd-verifier)_
