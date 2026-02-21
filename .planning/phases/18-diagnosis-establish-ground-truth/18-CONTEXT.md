# Phase 18: Diagnosis — Establish Ground Truth - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Answer four sequential diagnostic questions with evidence: Is content reaching GMC? Which code path runs in production? Are feature flags wired to the active path? Is the SKU coverage funnel wide enough to move metrics? This phase produces findings — it does NOT fix anything.

</domain>

<decisions>
## Implementation Decisions

### Coverage Funnel Output
- Dashboard page: visual funnel on the **overview page** (not a new page)
- Clickable stages: clicking a funnel stage shows an **expandable SKU list** inline (not navigation to another page)
- Drop-off display: Claude's discretion on whether to show percentages between stages or just raw counts — pick what's most useful for diagnosis

### Code Path Tracing
- **Side-by-side comparison**: trace both single-SKU UI regeneration path AND batch path, highlighting where they diverge
- Format: Claude's discretion — flowchart, markdown call graph, or hybrid — pick what makes the divergence clearest
- Documentation lives in **both** places: `docs/architecture/` for long-term reference + `.planning/phases/18-*/` diagnostic report for immediate downstream consumption
- Feature flag audit (DIAG-03): Claude's discretion on whether to integrate into the path trace or keep as a separate deliverable — pick what makes the evidence clearest

### Propagation Spot-Check
- SKU selection: **mix of criteria** — some recently published, some older, some high-value, some random — broader diagnostic coverage
- Comparison scope: **Supabase approved_content vs Google Sheets rows only** (not full chain to GMC — that's monitoring territory)
- Automation: Claude's discretion on whether to build a reusable script or do a one-time investigation — pick based on future utility
- Discrepancy threshold: Claude's discretion — define what counts as a meaningful mismatch vs insignificant formatting difference

### Results Format & Consumers
- **Dual audience**: Bobby via dashboard + downstream agents (Phase 19-20) via structured files
- Dashboard presentation: Claude's discretion on whether detailed findings go on overview page alongside funnel or on a separate /diagnosis page — pick based on information density
- Agent-consumable format: **both** database tables (for dashboard queries) AND markdown reports in `.planning/` (for agent context)
- **Freshness indicators**: all diagnostic data shows timestamps ("Last run: X") so staleness is visible

### Claude's Discretion
- Funnel drop-off presentation (percentages vs raw counts)
- Code path trace format (flowchart vs markdown vs hybrid)
- Feature flag audit placement (inline on trace vs separate)
- Spot-check automation level (reusable script vs one-time)
- Discrepancy threshold definition
- Dashboard layout for detailed findings (overview vs dedicated page)

</decisions>

<specifics>
## Specific Ideas

- Funnel should be visual and on the overview page — Bobby wants to see pipeline health at a glance without navigating
- Path trace should make divergence between single-SKU and batch paths obvious — this is the key diagnostic insight
- Architecture docs should be permanent reference, phase reports are for immediate downstream use

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-diagnosis-establish-ground-truth*
*Context gathered: 2026-02-20*
