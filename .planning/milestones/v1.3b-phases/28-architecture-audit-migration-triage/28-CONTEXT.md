# Phase 28: Architecture Audit & Migration Triage - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Map the complete production data flow from Google Ads API through to dashboard actions. Verify schema state against what's actually in production. Triage all 18 deferred migration tables (035b + 034b) with KEEP/DEFER/PRUNE decisions. Audit join chain integrity for the feedback loop. Validate API quota sustainability for daily snapshot capture.

This phase produces **findings and decisions only** — no schema changes, no code changes, no data fixes. Phases 29-31 act on these findings.

</domain>

<decisions>
## Implementation Decisions

### Migration Triage Criteria
- Evaluate ALL 18 tables for KEEP — including 034b GA4 tables (user considers GA4 important for the master plan)
- Claude decides per-table based on: code references, downstream need for v1.3b-v1.4, complexity, and alignment with the feedback loop
- Lean toward building infrastructure for future scale rather than aggressive pruning
- For tables with orphaned dashboard components: Claude decides per case — simple wiring now (Phase 31), complex UI deferred to v1.3c/v1.4

### Dead Code Policy
- Pruned tables: delete TypeScript consumer files, keep migration SQL files as reference
- Phase 31 executes the actual deletions based on Phase 28's triage decisions

### Data Quality Thresholds
- **Go/no-go for feedback view**: Any linked data is useful — even 10 records justifies building the view. Don't wait for large sample sizes.
- **NULL rate handling**: Claude decides based on findings — backfill if data exists to derive values, enforce NOT NULL going forward if not
- **Audit scope**: All foreign keys in the publish/performance chain, not just prompt_hash and content_version
- **Phase 28 scope**: Document findings only — no data fixes during the audit. Issues escalate to Phase 29-31.

### Audit Deliverable Format
- **Data flow map (AUDIT-01)**: Mermaid diagrams + annotated prose. Renders in GitHub/VS Code.
- **Migration triage (AUDIT-03)**: Per-table decision cards — each table gets: purpose, code references, data state, decision (KEEP/DEFER/PRUNE), reasoning
- **File locations**: Primary in `.planning/phases/28-*/`, with summary/symlink in `docs/architecture/` for long-term reference
- **Circular flow validation (AUDIT-05)**: Claude decides whether separate document or section within data flow map, based on content volume

### API Quota Strategy
- Standard Access is effectively unlimited for our scale (2,784 SKUs, single account)
- Daily snapshot capture confirmed as target frequency (matches Google Ads daily data freshness)
- Quota analysis depth at Claude's discretion — lightweight confirmation if clearly fine, deeper if surprises emerge
- If redundant API calls found (dashboard + pipeline querying same data), recommend a caching strategy in the audit deliverable

### Claude's Discretion
- Per-table KEEP/DEFER/PRUNE decisions (with infrastructure-forward bias)
- Backfill vs enforce-going-forward for NULL columns
- Simple component wiring (Phase 31) vs deferring complex UI
- Circular flow document structure
- Quota analysis depth
- Caching strategy recommendations

</decisions>

<specifics>
## Specific Ideas

- User explicitly wants GA4 evaluated for KEEP — not dismissed as "no code references." The master plan (v1.3-v1.4) benefits from GA4 attribution infrastructure even if the data pipeline isn't built yet.
- "Build infrastructure to scale up" — preference for keeping tables that support the future feedback loop, even if current code consumers are sparse.
- Deliverables should serve dual purpose: GSD agents (phase directory) AND long-term architecture docs (docs/architecture/).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 28-architecture-audit-migration-triage*
*Context gathered: 2026-02-25*
