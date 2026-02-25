# Phase 29: Content-Performance Feedback Linkage - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Connect published content changes to measurable search performance outcomes. Users can see how their content edits affected CTR/CVR for any published SKU, with impact scores and search term-level changes. Covers: feedback view, diff-in-diff impact scores, search term snapshots post-publish, and prompt_hash NOT NULL enforcement. Does NOT cover: automated re-optimization based on feedback, alerting/notifications, or historical funnel persistence (Phase 30).

</domain>

<decisions>
## Implementation Decisions

### Feedback View Presentation
- Dedicated page at a new top-level route (e.g., `/feedback` or `/content-impact`)
- Landing view: SKU list table with impact summary — columns include SKU, publish date, baseline CTR, current CTR, delta, impact score
- Click a row to drill into detailed view (search terms, control cohort, history)
- CTR/CVR deltas displayed as color-coded percentages: green for positive, red for negative, gray for insufficient data
- All three time windows shown by default: 7-day, 14-day, 30-day columns

### Impact Score Interpretation
- Scores presented as labeled tiers: "Strong Improvement", "Moderate Improvement", "No Significant Change", "Decline" — color-coded
- Low-data SKUs show gray "Insufficient Data" badge instead of a score, with tooltip explaining minimum thresholds
- Control cohort: auto-select similar unpublished SKUs from same product category for diff-in-diff comparison
- Control methodology transparency: expandable detail row shows which control SKUs were used, raw numbers, methodology note

### Search Term Change Display
- Gained/Lost split view: "Terms Gained" on left, "Terms Lost" on right, color-coded
- Each term row shows: search term text, impression delta (+/-), click delta (+/-)
- New terms (zero pre-publish impressions) get a "New" badge to distinguish from existing terms gaining volume
- Top 10 terms per side by default, "Show all" to expand

### Edge Cases & Data Gaps
- Recently published SKUs: show available windows with data, gray out unavailable windows with "Pending (X days)" countdown
- Re-published SKUs: show latest publish event's impact by default, expandable "History" section for prior publishes
- Missing baselines: show post-publish metrics with "No baseline" warning badge — don't hide the SKU
- Existing NULL prompt_hashes: leave as-is, enforce NOT NULL going forward only. Legacy rows display as "Legacy publish (no version tracking)" in UI

### Claude's Discretion
- Exact threshold values for impact score tiers (what numeric ranges map to "Strong", "Moderate", etc.)
- Algorithm for selecting control cohort SKUs (category matching, similarity criteria)
- Minimum impression threshold for "Insufficient Data" badge
- Page routing path and navigation placement
- Drill-down detail layout and component structure
- Error state handling and loading states

</decisions>

<specifics>
## Specific Ideas

- Feedback table should feel scannable — users want to quickly see "which of my published SKUs are performing better/worse"
- The expandable detail row pattern (for control cohort and publish history) keeps the default view clean while providing power-user depth
- "New" badge on search terms is specifically for distinguishing content that unlocked new queries vs content that boosted existing query performance

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 29-content-performance-feedback-linkage*
*Context gathered: 2026-02-25*
