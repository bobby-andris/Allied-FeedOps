# Phase 11: Performance Page Enhancements - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Enhance the performance page to show published SKUs' pre/post-publish metric comparison with trend direction at a glance. 36 published SKUs with 44 real snapshots are available for testing. The page already exists — this phase adds the comparison layer, time selectors, trend indicators, and a SKU detail view.

</domain>

<decisions>
## Implementation Decisions

### Comparison Layout
- All four metrics shown in the table: CTR, impressions, clicks, CVR — each gets its own column(s)
- Whether to use side-by-side (baseline | snapshot | delta) vs. delta-only with baseline on hover: **Claude's discretion**
- Whether to redesign the current page or add a new section/tab: **Claude's discretion**
- Whether rows expand inline for detail or use a flat table: **Claude's discretion** (note: detail view is required — see SKU Detail View section)

### Time Selectors
- Both the pre-publish baseline AND the post-publish snapshot have time window selectors
- Pre-publish windows: 7d / 30d / 60d before publish
- Post-publish windows: 7d / 30d / 60d after publish
- Days-since-publish appears as BOTH a per-SKU column in the table AND is contextualized by the global time selector
- Whether to show actual publish date or elapsed days per row: **Claude's discretion**

### Trend Indicators
- All four metrics get per-metric delta display with color-coded direction
- Visual style (arrow icons vs. colored numbers): **Claude's discretion** — pick what fits the existing dashboard style
- Row-level trend summary signal (which metric drives it): **Claude's discretion**
- Neutral/no-change threshold: **Claude's discretion** — avoid coloring noise
- CVR treatment (may have lower data availability and higher noise): **Claude's discretion**

### Coverage & Filter
- Filter toggle: All SKUs / Published only — user can switch between views
- Default filter state: **Claude's discretion**
- For published SKUs with no snapshot for the selected time window: **Claude's discretion** — handle gracefully with clear visual state
- Default sort order on page load: **Claude's discretion**
- Column headers are **sortable** — clicking a metric's column sorts by that metric's delta

### SKU Detail View
- Clicking a SKU row opens a detail view (navigation method: **Claude's discretion** — inline expansion or slide-out panel)
- Detail view contains:
  1. **Variant-level performance breakdown** — same baseline vs. snapshot comparison, but per variant/finish for that master SKU
  2. **Search term list** — top search terms for that SKU from the `search_queries` table
- The detail view keeps the same time window selections as the parent table

### Claude's Discretion
- Presentation style for comparison (side-by-side vs. delta-only)
- Whether to redesign or add to the current performance page
- Flat vs. expandable row mechanism (given detail view exists, Claude picks the right UI pattern)
- Visual style for trend indicators (arrows, colored numbers, icons)
- Metric driving the row-level trend summary
- Neutral threshold for trend coloring
- CVR treatment
- Missing snapshot handling (visual state for no-data cells)
- Default sort order
- Default filter state (All vs. Published only)
- Publish date display (date vs. elapsed days vs. both)
- SKU detail view UI pattern (inline expansion vs. slide-out panel)

</decisions>

<specifics>
## Specific Ideas

- User specifically asked for time selectors on BOTH sides (pre-publish baseline AND post-publish snapshot) — this is a key differentiator from a simple "latest vs. baseline" design
- User wants to see variant-level data when drilling into a SKU — since master SKUs aggregate across variants in Google Ads, per-variant breakdown is genuinely useful
- Search terms in the detail view should come from the existing `search_queries` table (already populated)

</specifics>

<deferred>
## Deferred Ideas

- Search term trends / keyword analytics as a standalone view — user expressed interest in "other relevant information" beyond what's in scope here; full search analytics belongs in its own phase or as an expansion of the existing Search Insights page

</deferred>

---

*Phase: 11-performance-page-enhancements*
*Context gathered: 2026-02-18*
