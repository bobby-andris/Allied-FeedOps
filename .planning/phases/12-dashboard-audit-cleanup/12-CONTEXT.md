# Phase 12: Dashboard Audit & Cleanup - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit every dashboard page to determine its current health (working, broken, stale, dead end). Fix all broken and stale pages — regardless of complexity. Remove or redirect dead-end experiences. Add contextual empty states where data is missing. Verify all changes via agent-browser in the live environment.

New features and capabilities (e.g., new data sources, new workflows) are out of scope — this phase is about making what exists work correctly.

</domain>

<decisions>
## Implementation Decisions

### Fix vs. defer bar
- **Fix everything found** — broken pages and stale data get fixed, no exceptions for "minor" issues
- **Stale pages treated same as broken** — if data is old or misleading, fix it
- **Complex fixes are in scope** — if a fix requires a new API endpoint or component rewrite, create the work; Phase 12 absorbs it
- **Working but rarely used pages** — do NOT change them; flag them in the audit doc for separate consideration later

### Low-value page treatment
- **Batch management page**: Keep it as-is; fix only if broken — it exists for publishing workflow
- **Backfill monitoring page**: Keep it — useful for occasional re-runs even though v1.0 is complete
- **Low-priority pages (Settings, Competitor Intelligence, etc.)**: Note usage level in audit + confirm working; don't change if working
- **Broken + irrelevant to current workflow**: Claude's discretion per page — judge whether the feature has any future value before deciding fix vs. remove

### Empty state design
- **Content**: Every empty state includes a message AND contextual guidance — explain why it's empty and what steps would lead to data appearing
- **Visual style**: Claude's discretion — match the page tone and existing component patterns
- **Page-specificity**: Claude's discretion — generic pattern is fine where the message is the same; use page-specific copy where context matters
- **Loading and error states**: Claude's discretion — fix what's obviously broken or missing during the walkthrough; not required to audit every loading/error state explicitly

### Audit documentation
- **Format**: Markdown table in `12-AUDIT.md` in the phase directory — one row per page with status, issue summary, and action
- **Committed**: Yes — lives in `.planning/phases/12-dashboard-audit-cleanup/`
- **Status labels**: Claude's discretion — use whatever labels make the audit table clear and actionable
- **Audit environment**: Audit locally first (faster iteration), verify fixes on live Vercel URL (allied-feed-ops.vercel.app) before marking complete

### Claude's Discretion
- Empty state visual design (icon choice, layout, styling)
- Empty state component architecture (single generic component vs. per-page)
- Status labels in the audit table
- Loading/error state audit depth
- Per-page fix vs. remove decisions for broken + irrelevant pages

</decisions>

<specifics>
## Specific Ideas

- The audit doc (AUDIT.md) should be written before any fixes begin — document first, then act
- agent-browser walkthrough on localhost during audit, then on Vercel after fixes are deployed
- Phase 12 context from STATE.md: "Audit is exploratory — do a full page walkthrough before fixing. Document every page status before touching code."

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 12-dashboard-audit-cleanup*
*Context gathered: 2026-02-18*
