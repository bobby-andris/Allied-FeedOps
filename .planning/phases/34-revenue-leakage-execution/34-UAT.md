---
status: testing
phase: 34-revenue-leakage-execution
source: 34-01-SUMMARY.md, 34-02-SUMMARY.md, 34-03-SUMMARY.md, 34-04-SUMMARY.md
started: 2026-02-26T01:15:00Z
updated: 2026-02-26T01:15:00Z
---

## Current Test

number: 2
name: Revenue Leakage Tab — Hero Card and Box Plot
expected: |
  Click the "Revenue Leakage" tab. Should show a LeakageHero card with estimated revenue leakage range, confidence dot, and ROAS box plot visualization.
awaiting: user response

## Tests

### 1. Tier Scoring Page Shows 4 Tabs
expected: Navigate to /tier-scoring. The page should display 4 tabs: Action Queue, Explorer, Revenue Leakage, and History. Revenue Leakage tab should show a badge with pending recommendation count.
result: issue
reported: "Two bugs: (1) View full scorecard button does not work. (2) Every custom_label_0 shows X out of 3 terms scored. Also raised fundamental domain concern about whether system understands waterfall shopping intent structure."
severity: major

### 2. Revenue Leakage Tab — Hero Card and Box Plot
expected: Click the "Revenue Leakage" tab. Should show a LeakageHero card with estimated revenue leakage range (e.g., "$X - $Y"), a confidence dot (green/yellow/red), and a ROAS box plot visualization comparing tier distributions.
result: [pending]

### 3. Revenue Leakage Tab — Term List with Reason Codes
expected: Below the hero/box plot, a list of classified search terms should appear. Each term shows a reason badge (misplaced, wasted spend, or under-invested) with color coding. Terms are sorted by priority.
result: [pending]

### 4. Approve/Reject Inline Actions on Term Rows
expected: Each pending term row should have Approve and Reject buttons. For wasted spend terms, buttons should show "Block" and "Demote" instead. Clicking Approve should immediately update the row to show an "Accepted" badge with an Undo button (optimistic update).
result: [pending]

### 5. Batch Approve Bar
expected: When multiple high-confidence recommendations are pending, a sticky batch approve bar should appear at the bottom with a count and "Approve All" button.
result: [pending]

### 6. History Tab — Day-Grouped Audit Trail
expected: Click the "History" tab. Should show recommendation actions grouped by day in reverse chronological order, with action icons, tier arrows, and timestamps. Accepted entries should have an Undo button.
result: [pending]

### 7. Apply Recommendations Button Navigation
expected: On the main Action Queue tab, the HeroSummary card should have an "Apply Recommendations" button. Clicking it should switch to the Revenue Leakage tab.
result: [pending]

### 8. Action Queue Undo for Accepted Recommendations
expected: In the Action Queue tab, rows that have been accepted should show an Undo button. Clicking Undo should revert the recommendation status.
result: [pending]

### 9. Unit Tests Pass (Phase 34 specific)
expected: Running `npx vitest run` should pass all Phase 34 tests: reason-codes (14 tests), leakage-hero (7 tests), box-plot (7 tests), history (10 tests), plain-verdict (10 tests). Total 48/48 green.
result: pass

## Summary

total: 9
passed: 1
issues: 1
pending: 7
skipped: 0

## Gaps

- truth: "View full scorecard navigates to scorecard view"
  status: failed
  reason: "User reported: View full scorecard button does not work"
  severity: major
  test: 1
  root_cause: "onViewDetails sets actionSelectedTerm which only renders in Action Queue TabsContent, not Revenue Leakage tab"
  artifacts:
    - path: "dashboard/src/app/(dashboard)/tier-scoring/page.tsx"
      issue: "line 251: onViewDetails={setActionSelectedTerm} sets state for wrong tab"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/LeakageTermRow.tsx"
      issue: "line 277: View full scorecard calls onViewDetails which doesn't switch tabs"
  missing:
    - "Either switch to actions tab when viewing details, or render TermScorecard within Revenue Leakage tab"

- truth: "Explorer cards show correct scored vs total term counts"
  status: failed
  reason: "User reported: Every custom_label_0 has X out of 3 terms scored"
  severity: major
  test: 1
  root_cause: "totalTerms in computeTierDistributions counts LabelTierPerformance aggregate rows (1 per tier = always 3), not individual search terms"
  artifacts:
    - path: "dashboard/src/lib/optimization/tier-scoring.ts"
      issue: "line 109-113: totalTerms += tierRows.length counts tier aggregate rows, not search terms"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx"
      issue: "line 150: displays scoredTerms of totalTerms where totalTerms is always 3"
  missing:
    - "totalTerms should count actual search terms in the group, not tier-level aggregate performance rows"

- truth: "Expanded term detail shows actual ROAS, not fit score"
  status: failed
  reason: "Display shows fit score as 'Current ROAS' (e.g., -0.55, -0.87)"
  severity: major
  test: 1
  root_cause: "LeakageTermRow.tsx line 262-263 displays tierFitScores[currentTier] labeled as 'Current ROAS' — tierFitScores is z-score-based fit metric, not actual ROAS"
  artifacts:
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/LeakageTermRow.tsx"
      issue: "line 262: shows tierFitScores as Current ROAS"
  missing:
    - "Need to pass actual term ROAS through TermScore and display it instead of fit score"

- truth: "Default tier distributions match Google Shopping waterfall model"
  status: failed
  reason: "User reported: defaults have HIGH=highest ROAS and LOW=lowest ROAS, but in waterfall HIGH priority catches broad traffic (low ROAS) and LOW priority catches highest intent (high ROAS)"
  severity: blocker
  test: 1
  root_cause: "DEFAULT_DISTRIBUTIONS in tier-scoring.ts has inverted ROAS expectations — HIGH p50=5.5, LOW p50=1.2 when it should be reversed"
  artifacts:
    - path: "dashboard/src/lib/optimization/tier-scoring.ts"
      issue: "lines 48-82: DEFAULT_DISTRIBUTIONS HIGH/LOW ROAS values are inverted"
  missing:
    - "Swap HIGH and LOW default distributions to match waterfall model"
    - "Fix NLP intent alignment (branded → LOW not HIGH)"
    - "Fix Demote action for wasted spend (should not send to LOW)"
