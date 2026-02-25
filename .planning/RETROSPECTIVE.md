# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.3b — Architecture Validation & Data Persistence

**Shipped:** 2026-02-25
**Phases:** 5 | **Plans:** 13 | **Tasks:** 27

### What Was Built
- Complete data flow map with 11 Mermaid diagrams mapping Google Ads API → DB → Dashboard → Actions
- Migration triage for 18 deferred tables (14 KEEP, 4 DEFER) with per-table decision cards
- Content Impact dashboard — landing page with 10-column table and drill-down detail with search term gained/lost
- Historical funnel persistence — daily snapshot capture, trend cards, backfill endpoint
- SCHEMA.md rebuilt from production (56 tables, 1,589 lines, [KEEP]/[DEFER] tags)
- GmcDisapprovalBadge and PromptLineagePanel wired into SKU Review
- Coming Soon states for DEFER'd pages with sidebar badges
- E2E loop validation with FT-16 through generate → publish → baseline → snapshot

### What Worked
- **Research-first phase approach** — Phase 28 audit produced evidence that directly informed Phases 29-31 design decisions (NULL rates, quota headroom, triage)
- **Sequential phase dependencies** — Each phase built on verified foundations from the previous one
- **5 phases in 1 day** — clean scope definition and validated architecture made execution fast
- **Verification at every phase** — VERIFICATION.md files caught the pg_tables gap in Phase 28 early

### What Was Inefficient
- **Funnel backfill data loss** — Phase 30.1 backfilled 4,093 rows but production table ended up empty; cause unclear (possible environment issue)
- **MCP access gaps in sub-agents** — Phase 28 Plan 01 couldn't run pg_tables query, requiring orchestrator re-verification
- **DiD compute pipeline not built** — performance_impact_scores table exists but nothing writes to it; should have been scoped clearly as future work from the start

### Patterns Established
- **[KEEP]/[DEFER] tagging in SCHEMA.md** — clear visual markers for table lifecycle status
- **Coming Soon server components** — pattern for pages that query non-existent or empty tables (no 'use client', static card)
- **Forward-only enforcement** — application-layer validation for new data without breaking legacy rows (FEED-04 pattern)
- **Write-behind persistence** — capture endpoints that don't block live query paths

### Key Lessons
1. **Data-starved flows are not the same as broken flows** — all 3 "broken" flows in the integration check had correct code wiring; they just lacked production data. Important to distinguish code completeness from operational readiness.
2. **Operational activation (scheduler, secrets, backfill) should be tracked explicitly** — these fell through the cracks between plan completion and milestone audit.
3. **Sub-agent MCP access should be validated during planning** — Phase 28 Plan 01 was designed to run SQL queries but the executor agent couldn't access MCP tools, requiring workarounds.

### Cost Observations
- Model mix: ~70% sonnet (executors, verifiers, researchers), ~20% opus (orchestrator, planners), ~10% haiku (checkers)
- Sessions: ~4 (Phase 28-29, Phase 30-30.1, Phase 31, audit+complete)
- Notable: 106 commits in 1 day — high velocity due to clean architecture scope

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.3b | ~4 | 5 | First milestone with formal 3-source requirements cross-reference in audit |

### Top Lessons (Verified Across Milestones)

1. Research-first before code changes produces better outcomes (validated in v1.2, v1.3a, v1.3b)
2. Schema documentation prevents query errors — SCHEMA.md check before SQL is mandatory (validated in v1.2, v1.3b)
3. GPT-5.2 SYSTEM_PROMPT is hyper-sensitive to changes — test after each line change (validated in v1.3a)
