# Phase 34: Revenue Leakage and Execution - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can identify revenue opportunities (misplaced terms, wasted spend, under-invested winners) with dollar-value estimates and act on them with one-click tier movement approvals that persist to the database. Actual Google Ads execution is Phase 36. This phase is the decision layer.

Requirements: LEAK-01 through LEAK-06, EXEC-01 through EXEC-05.

</domain>

<decisions>
## Implementation Decisions

### Leakage hero number
- Range with midpoint format: "$1,200 - $3,400/mo (est. $2,300)"
- Confidence coloring (high/medium/low) as a dot indicator
- "Last computed" timestamp displayed below the range

### Term list organization
- Flat list sorted by estimated revenue impact (highest first)
- Reason codes as colored badges: Misplaced, Wasted $, Under-invested
- Badge + expandable detail: click to see specifics (ROAS value, current vs recommended tier, peer average, confidence score)
- No grouping by reason type — single unified list

### ROAS distribution box plots
- Inline above the term list showing tier distributions side-by-side
- Shows overlap zones between tiers
- Always visible (not collapsible)

### Approve/reject interaction
- Inline with optimistic update: click approve → row instantly shows "Approved" state → DB write in background
- No confirmation modal, no extra step
- After approval, row shows "Approved" status with an always-available [Undo] button
- Reject is one-click with an optional (non-blocking) reason text field that appears after clicking reject

### Batch approve
- Sticky top bar above the term list: "N high-confidence recommendations → [Approve All]"
- Applies to all terms with confidence > 0.80
- Count updates as individual actions happen

### Execution model
- Approval writes to routing_recommendations table only (status: approved, timestamp, user)
- NO Google Ads API calls in this phase — actual execution is Phase 36 or manual
- This phase is the decision/approval layer, not the execution layer

### Undo behavior
- Undo reverts status from "approved" back to "pending" in routing_recommendations
- Term reappears in the leakage list with original recommendation
- Undo always available (no time limit) — safe because no Google Ads changes until Phase 36
- Future: if already executed to Google Ads (Phase 36+), undo writes a reversal to policy_action_execution_log

### History view
- History tab on the Search Insights page (alongside Scoring, Action Queue, Revenue Leakage)
- Reverse-chronological log of all approve/reject/undo actions
- Grouped by day with timestamps
- Shows: term, action type (approved/rejected/undone), tier movement (from→to), timestamp
- Rejected items show the optional reason note inline (as subtitle) if one was provided

### Page structure
- New "Revenue Leakage" and "History" tabs added to the existing Search Insights page
- Tab order: [Scoring] [Action Queue] [Revenue Leakage · N] [History]
- Revenue Leakage tab label shows badge count of actionable items
- Sidebar navigation stays as single "Search Insights" entry — tabs handle sub-navigation

### Action Queue relationship
- Revenue Leakage tab = see flagged terms, approve/reject (the decision view)
- Action Queue tab = see all approved movements awaiting execution (the tracking view)
- Approved items move from Revenue Leakage to Action Queue
- Undo available in both Action Queue and History views

### Claude's Discretion
- Loading states and skeleton patterns
- Exact spacing, typography, and color palette for badges
- Empty state design (when no leakage detected)
- Box plot visualization library choice
- Error handling for failed DB writes during optimistic updates
- How to handle stale data (e.g., scoring data updated while user is reviewing)

</decisions>

<specifics>
## Specific Ideas

- The hero number with range + midpoint follows the pattern: show uncertainty honestly but give a focal point for quick decisions
- Expandable rows for reason codes (collapsed by default) — similar to how Phase 33.2 shows term details
- Optimistic updates mean the UI feels instant — DB writes happen in background
- History grouped by day with clear action icons (checkmark, X, undo arrow) for quick scanning

</specifics>

<deferred>
## Deferred Ideas

- Actual Google Ads API execution of tier movements — Phase 36 (Automation and Experiments)
- Automated rule-based tier rebalancing — Phase 36
- A/B experiments on tier assignments — Phase 36
- Optimization impact tracking (before/after) — Phase 37

</deferred>

---

*Phase: 34-revenue-leakage-execution*
*Context gathered: 2026-02-25*
