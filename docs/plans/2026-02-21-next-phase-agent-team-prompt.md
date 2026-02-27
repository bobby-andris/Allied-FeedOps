# Claude Code Agent Team Prompt: Shopping Keyword Promote/Demote + V2 Expansions

Copy everything below the line into a new Claude Code chat.

---

## Context

You are continuing work on the Allied-FeedOps project in a git worktree at `/Users/bobby/.codex/worktrees/c5bd/Allied-FeedOps`. The Unified Intent Intelligence & Execution System has completed all 4 phases (16 batches) of its 120-day roadmap. Read the full plan and execution status at Notion page `30d1adf992e980338b73d8361ecddaa9` and the operator runbook at `30d1adf992e98168ac77e2af8468c50f` using the Notion MCP server.

### What's built (all verified: tests pass, lint clean, build passes)

**Phase 1**: Unified intent taxonomy (`taxonomy.ts`), policy engine (`policy.ts`), 8 API routes (`/api/intent/*`), 3 new dashboard pages (Intent Control Center, Search Governance, Experiment Lab), migration `035_unified_intent_execution_system.sql`.

**Phase 2**: Search governance candidates/drafts/movements/apply, guardrail incidents, bid policy with CPA mode, rollback with snapshot listing and cross-channel negative deactivation.

**Phase 3**: Value-confidence enrichment from `attribution_confidence_daily`, margin-aware value signals from `sku_margin_daily`/`order_line_returns_daily`, operator calibration analytics (`/api/intent/review-analytics`), query mining + buildout intelligence (`/api/search/governance/buildouts`), experiment holdouts + weekly governance checkpoints.

**Phase 4**: Input validation/sanitization (`input-validation.ts`), GA4/Shopify value consistency (`value-consistency.ts`), incident automation (`incident-automation.ts`), rollback readiness endpoint, executive scorecards (`executive-scorecard.ts`, `/api/intent/scorecard`), channel adapter contracts (`channel-adapter.ts`).

**Test count**: 99 intent-specific tests across 13 test files, all passing.

### Key files to read first

- `dashboard/src/lib/intent/policy.ts` — Core policy engine (all 5 decision functions)
- `dashboard/src/lib/intent/types.ts` — All TypeScript types
- `dashboard/src/lib/intent/taxonomy.ts` — Intent classification
- `dashboard/src/app/(dashboard)/intent-control-center/page.tsx` — Main control center UI
- `dashboard/src/app/(dashboard)/shopping-funnel/page.tsx` — Shopping funnel UI
- `dashboard/src/app/api/intent/promote-demote/route.ts` — Current promote/demote API
- `dashboard/src/app/api/search-terms/save-decisions/route.ts` — Existing Shopping decision save flow
- `dashboard/src/app/api/shopping-funnel/recommendations/route.ts` — Shopping recommendations
- `docs/plans/2026-02-20-intent-control-operator-runbook.md` — Full operator runbook
- `CLAUDE.md` — Critical project conventions and rules

## Task: Shopping Keyword Promote/Demote Execution + V2 Expansions

### Priority 1: Shopping Keyword Promote/Demote (CRITICAL NEW FEATURE)

The intent system currently evaluates promote/demote decisions (`evaluatePromotionDemotion` in `policy.ts`) but these decisions stay in the policy layer — they don't actually execute keyword movements within the Google Shopping campaign structure. We need:

1. **Shopping tier movement execution**: When the policy engine recommends promoting a keyword from LOW→MEDIUM or MEDIUM→HIGH (or demoting), the system needs to:
   - Update the keyword's tier assignment in the `custom_label_0` field (which controls Shopping campaign segmentation)
   - Update the supplemental feed via Google Sheets (the production feed at sheet `1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg`, sheet name `SupplementalFeedData`, column E = `custom_label_0`)
   - Record the movement in `policy_action_execution_log` with full audit trail
   - Apply cross-tier negatives when promoting (to prevent the keyword from matching in the old tier's campaign)

2. **Shopping Funnel integration**: The `/shopping-funnel` page needs a "Promote/Demote" action panel that:
   - Shows keywords recommended for tier movement by the policy engine
   - Lets the operator approve/reject/defer each recommendation
   - Executes approved movements in batch (update Google Sheets feed + log actions)
   - Shows movement history and rollback capability

3. **API endpoint**: `POST /api/shopping/tier-movement` that:
   - Accepts keyword IDs and target tier
   - Validates against policy engine thresholds
   - Updates Google Sheets supplemental feed `custom_label_0` values
   - Creates `policy_action_execution_log` entries
   - Creates cross-tier negatives in `negative_registry`
   - Returns execution results with audit IDs

4. **Guardrail enforcement**:
   - Block all movements when guardrail status is `blocked`
   - Require review when `hold`
   - Respect confidence gates (>=0.75 auto-safe, 0.55-0.74 review, <0.55 observe-only)

### Priority 2: V2 Expansions (from the 7 initiatives)

These are the planned v2 expansions that haven't been implemented yet. Tackle these after Priority 1:

**Initiative 1 v2**: Adaptive subclass rules and seasonality-aware context for taxonomy.
**Initiative 2 v2**: Semi-automated Shopping→Search graduation activation with holdout experiments.
**Initiative 3 v2**: Full COGS/returns integration and lag-adjusted profit forecasting.
**Initiative 5 v2**: Reviewer calibration analytics and workload balancing.
**Initiative 6 v2**: Continuous query mining with auto-generated campaign drafts.
**Initiative 7 v2**: Multi-cell experiments and automated winner rollout.

## Execution Instructions

### Use the `superpowers:executing-plans` skill workflow

### Use agent teams for parallel work

Spawn a team with these agents:

1. **policy-engine** (general-purpose): Handles `policy.ts` changes, new tier movement logic, policy validation, and tests. Works in `dashboard/src/lib/intent/` and `dashboard/src/lib/intent/__tests__/`.

2. **api-routes** (general-purpose): Handles new API routes (`/api/shopping/tier-movement`), integration with Google Sheets publishing (`dashboard/src/lib/publishing/google-sheets.ts`), and route tests. Works in `dashboard/src/app/api/`.

3. **ui-frontend** (general-purpose): Handles Shopping Funnel page updates (`shopping-funnel/page.tsx`), Intent Control Center updates, new UI panels, and component tests. Works in `dashboard/src/app/(dashboard)/`.

4. **docs-verification** (general-purpose): Handles operator runbook updates, Notion page updates (both pages), schema doc updates, and runs final verification gate (lint + test + build).

### Task dependency order:
1. **policy-engine** starts first (defines types and logic other agents depend on)
2. **api-routes** starts after policy-engine defines the tier movement types
3. **ui-frontend** starts after api-routes defines the API contract
4. **docs-verification** runs last after all code is written

### Mandatory workflow rules:
- **TDD**: RED (failing tests) → GREEN (make pass) → REFACTOR
- **Verification gate per batch**: `npm run lint` clean, `npx vitest run` passes, `npm run build` passes
- **No fabricated data**: Query database first, verify data is real
- **Pre-deploy gates**: `cd dashboard && npm run build` MUST pass before any commit
- **Google Sheets caution**: The supplemental feed is PRODUCTION data. Use the existing `updateSupplementalFeedRows()` pattern from `dashboard/src/lib/publishing/google-sheets.ts`. Offer ID format: uppercase `shopify_US_` for sheets, lowercase `shopify_us_` in database.
- **Update Notion**: After each major completion, update both Notion pages (plan: `30d1adf992e980338b73d8361ecddaa9`, runbook: `30d1adf992e98168ac77e2af8468c50f`)

### Key conventions (from CLAUDE.md):
- TypeScript for dashboard/API routes
- ESLint: underscore prefix does NOT suppress `no-unused-vars` — use `// eslint-disable-next-line`
- Column naming: `approval_status` not `status`, check `docs/database/SCHEMA.md` before ANY query
- GMC offer IDs: uppercase `shopify_US_` for Google Sheets, lowercase `shopify_us_` in database
- Use existing `createAdminClient()` from `@/lib/supabase/admin` for server-side DB access
- Use existing `extractErrorMessage()` and `isMissingRelationError()` from `@/lib/intent/persistence` for safe error handling
