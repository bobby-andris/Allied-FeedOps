# Phase 35: Market Intelligence - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can understand demand patterns, competitive positioning, and product group health to make strategic decisions beyond individual term optimization. Covers 11 requirements: DEMAND-01 through DEMAND-07 (demand intelligence) and PROD-01 through PROD-04 (product intelligence). Does NOT include automation rules, A/B experiments, or reporting — those are Phases 36 and 37.

</domain>

<decisions>
## Implementation Decisions

### Dashboard layout
- New top-level page "Market Intelligence" in sidebar nav, separate from Waterfall/Search Insights
- 3 sub-tabs: **Demand** | **Competitive** | **Products**
- Demand tab: impression share gaps, CPC opportunity, seasonal trends, new term discovery, long-tail analysis
- Competitive tab: brand vs non-brand revenue split, competitor mention tracking
- Products tab: BCG bubble chart + table view
- Per-tab KPI summary cards at top (3-4 cards per tab, contextual to that tab's data)
- Default shows all data (all 59 product groups), user filters down by product group, tier, or custom_label_0

### BCG visualization (Products tab)
- Bubble chart is the primary/default view, with toggle to switch to sortable table
- X-axis: ROAS, Y-axis: Revenue, Bubble size: Total spend, Color: Trend direction
- Quadrant boundaries: Median ROAS and median Revenue across all 59 product groups (dynamic)
- Click bubble → right-side slide-out panel with product group detail (chart dims behind it)
- Slide-out shows: quadrant label, ROAS, Revenue, Spend, Trend %, and top terms with their tiers

### Claude's Discretion
- **Demand metrics visualization**: Chart types for impression share gaps, CPC opportunity, seasonal patterns, new term discovery, and long-tail analysis. Claude should pick the most effective visualization for each metric (bar charts, sparklines, tables, etc.)
- **Competitive intel layout**: How to present brand/non-brand split, competitor token tracking, and actionable insights. Claude should balance visual impact with data density
- **Color scheme and styling**: Consistent with existing dashboard patterns (Tailwind, shadcn/ui)
- **Mobile/responsive behavior**: Adapt charts for smaller screens
- **Loading states and error handling**: Skeleton loaders, empty states per tab
- **Seasonal pattern flagging**: How to highlight terms spiking/declining >20%
- **New term discovery presentation**: Count + list format, how many to show
- **Long-tail grouping**: Word count buckets and comparison chart design

</decisions>

<specifics>
## Specific Ideas

- BCG slide-out panel mockup was approved — shows chart dimmed with detail panel on right (see discussion)
- Demand tab layout mockup was approved — 2x2 grid (Impression Share | CPC Opportunity / Seasonal Trends | New Terms) with Long-tail Analysis full-width below
- Per-tab KPI cards keep context tight to the active tab rather than showing global metrics

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 35-market-intelligence*
*Context gathered: 2026-02-25*
