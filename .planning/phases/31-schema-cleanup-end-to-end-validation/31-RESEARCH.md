# Phase 31: Schema Cleanup & End-to-End Validation - Research

**Researched:** 2026-02-25
**Domain:** Database schema management, dashboard component wiring, end-to-end data flow validation
**Confidence:** HIGH

## Summary

Phase 31 is the capstone of v1.3b -- it ensures the production database reflects reality, dead/orphaned UI elements are resolved, and the full generate-publish-capture-feedback loop works end-to-end. The work is primarily integration and cleanup, not new feature development. There are no external libraries to adopt or complex architectural decisions to make.

The phase has four clear tracks: (1) verify/validate the 14 KEEP'd and 4 DEFER'd tables from the Phase 28 triage, (2) wire two orphaned components (GmcDisapprovalBadge, PromptLineagePanel) into the main SKU Review variant, (3) add "Coming Soon" gates on two DEFER'd pages (Optimization Control Center, Intent Control Center), and (4) rebuild SCHEMA.md from scratch via `information_schema.columns` queries. The E2E validation is a manual walkthrough documented as a report.

**Primary recommendation:** Execute schema verification first (establishes ground truth), then component wiring and page gates in parallel, then SCHEMA.md rebuild, and finally the E2E validation walkthrough as the capstone that confirms everything works together.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Orphaned components**: Wire GmcDisapprovalBadge and PromptLineagePanel into the **main SKU Review variant only** (not magazine or original variants). Hide when no data -- don't render component shell if underlying data is missing/empty.
- **DEFER'd pages** (Optimization Control Center, Intent Control Center): Show "Coming Soon" / "Coming in v1.3c" state when accessed. Keep pages in sidebar navigation with a visual indicator (badge or dimmed text).
- **KEEP'd pages** (Search Governance, Experiment Lab): Validate with seed data, then clean up test rows.
- **Shopping Funnel**: DO NOT TOUCH the existing page. It is a critical production workflow used daily (Bobby's dad uses it for hours). Create a **new separate page** for tier movement features.
- **Seed data approach**: Build a lightweight Python seed script that reads existing search_queries data and populates term_intent_state with basic intent classifications. Clean up seed data after validation.
- **Dead code / DEFER'd file consumers**: Leave files referencing DEFER'd tables **as-is** (profit-forecast.ts, value-signal.ts, bid-policy/route.ts). They already handle empty results gracefully.
- **SCHEMA.md update**: Full refresh from production -- query `information_schema.columns` and rebuild from scratch. Document ALL 18 deferred tables with clear [KEEP] and [DEFER] status tags. Include Phase 29-30 tables.
- **E2E validation**: Manual walkthrough with a real production SKU that already has performance baselines and published content. Document findings as a validation report.

### Claude's Discretion
- Exact "Coming Soon" UI treatment (banner, overlay, redirect)
- Which real SKU to use for E2E validation (pick one with richest data coverage)
- New page name and nav placement for tier movements
- Seed script design -- how many rows, which intent classes to simulate
- Order of operations for the phase

### Deferred Ideas (OUT OF SCOPE)
- Automated E2E smoke test script (manual walkthrough sufficient for Phase 31)
- Cloud Scheduler setup for GA4 snapshot-capture endpoint
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MIGR-01 | Subset of 035b tables applied (4-8 tables as prerequisites for v1.3c), schema verified against TypeScript consumer expectations | Phase 28 triage identified 10 KEEP'd 035b tables + 4 KEEP'd 034b tables. All 14 already exist in production (applied out-of-band). Verification = `information_schema.columns` query vs. migration SQL. TypeScript consumer files identified in triage doc with exact file paths. |
| MIGR-02 | Dead TypeScript files for pruned tables deleted or deprecated, build passes after cleanup | Phase 28 triage resulted in **zero PRUNE'd tables**. No files to delete. However, DEFER'd table consumers (3 files) should be confirmed to handle empty data gracefully. Build verification via `npm run build`. |
| MIGR-03 | Orphaned dashboard components (GmcDisapprovalBadge, PromptLineagePanel) either wired into dashboard pages or removed | Both components exist and are fully implemented. GmcDisapprovalBadge depends on `gmc_product_status` table (which exists). PromptLineagePanel fetches from `/api/prompt-lineage` route (which exists and queries `publish_events` + `regeneration_history`). Wire into SkuReviewClient main variant only, conditional on data availability. |
| MIGR-04 | SCHEMA.md updated to reflect true production state after all migration changes | Current SCHEMA.md is missing `funnel_snapshots_daily` (Phase 30), `search_query_snapshots` (Phase 29 -- referenced in code but not in SCHEMA.md). Full refresh from `information_schema.columns` will capture everything including the 18 deferred tables. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 14.x | Dashboard framework | Already in use; all page/component work is within this framework |
| Supabase JS | 2.x | Database queries (schema verification, seed data) | Already in use; `information_schema` queries use same client |
| Python 3.11+ | - | Seed script for term_intent_state | Project convention: Python for standalone scripts |
| Vitest | 2.x | Test runner (dashboard) | Already configured in `dashboard/vitest.config.ts` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | existing | Icons for Coming Soon badges, component indicators | Already used across dashboard |
| shadcn/ui components | existing | Card, Badge, Button for Coming Soon UI | Already used across dashboard |

### Alternatives Considered
None -- this phase uses exclusively existing stack components. No new dependencies needed.

## Architecture Patterns

### Pattern 1: Orphaned Component Wiring (GmcDisapprovalBadge)
**What:** Wire GmcDisapprovalBadge into SkuReviewClient main variant. The component already renders nothing when `issueCount === 0`, satisfying the "hide when no data" requirement.
**When to use:** When the parent component (SkuReviewClient) has the master_sku available.
**Implementation approach:**
1. In the SkuReviewClient main variant, add a client-side `useEffect` to fetch `/api/gmc/status?master_sku={sku}`
2. If the response has products with `disapproval_count > 0` or `issue_count > 0`, render the badge near the SKU header
3. The component already handles the zero-data case internally (returns null)

**Key files:**
- Component: `dashboard/src/components/gmc/GmcDisapprovalBadge.tsx`
- API route: `dashboard/src/app/api/gmc/status/route.ts` (reads from `gmc_product_status` table)
- Target: `dashboard/src/components/review/SkuReviewClient.tsx` (main variant only, NOT `.magazine.tsx` or `.original.tsx`)

### Pattern 2: Orphaned Component Wiring (PromptLineagePanel)
**What:** Wire PromptLineagePanel into SkuReviewClient main variant. The component fetches from `/api/prompt-lineage` on expand (lazy loading via Collapsible). It already shows a "not available" message when no lineage data exists.
**When to use:** When the SKU has been published at least once (has publish_events with prompt_hash).
**Implementation approach:**
1. Add `<PromptLineagePanel masterSku={masterSku} platform={selectedPlatform} />` to the SkuReviewClient render
2. Place it in a logical location (e.g., below the content section, above or near the performance section)
3. The component is self-contained -- it fetches its own data on expand, handles loading and empty states

**Key files:**
- Component: `dashboard/src/components/lineage/PromptLineagePanel.tsx`
- API route: `dashboard/src/app/api/prompt-lineage/route.ts` (reads from `publish_events` + `regeneration_history`)
- Target: `dashboard/src/components/review/SkuReviewClient.tsx` (main variant only)

### Pattern 3: "Coming Soon" Page Gate
**What:** Wrap DEFER'd page content in a conditional that shows a Coming Soon card instead of the current functional UI (which queries empty tables).
**Recommended approach:** A simple Card component at the top of the page with a clear message, replacing the current page content.

```tsx
// Recommended pattern for Coming Soon pages
export default function OptimizationControlCenterPage() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Optimization Control Center</h1>
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <Construction className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold">Coming in v1.3c</h2>
          <p className="text-muted-foreground mt-2 max-w-md">
            Distribution-based scoring, revenue leakage analysis, and profitability-aware optimization.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
```

**Sidebar visual indicator:** Add a badge or suffix to the sidebar nav item:
```tsx
{ name: 'Optimization Control', href: '/optimization-control-center', icon: Gauge, badge: 'Soon' }
```

### Pattern 4: New Tier Movements Page
**What:** Create a new page (separate from Shopping Funnel) for term_intent_state tier movement features.
**Recommended name:** "Intent Intelligence" -- broader scope than just tier movements, aligns with the term_intent_state table.
**Nav placement:** Below Shopping Funnel in the sidebar, with a "New" badge initially.
**Key consideration:** This page queries `term_intent_state`, `policy_action_execution_log`, and `negative_registry` -- all KEEP'd tables. It does NOT touch the Shopping Funnel page or its data sources.

### Pattern 5: SCHEMA.md Full Refresh
**What:** Query `information_schema.columns` for every table in the `public` schema, rebuild SCHEMA.md from scratch.
**Implementation approach:**
1. Use Supabase MCP `execute_sql` to query all tables and columns
2. Cross-reference with existing SCHEMA.md format for documentation structure
3. Tag each of the 18 deferred tables with `[KEEP]` or `[DEFER]` based on Phase 28 triage
4. Include Phase 29-30 tables: `performance_impact_scores`, `funnel_snapshots_daily`, `search_query_snapshots`

### Anti-Patterns to Avoid
- **Modifying Shopping Funnel page in ANY way:** Zero-risk requirement. The page is used daily in production. Even "harmless" changes could break something.
- **Deleting DEFER'd table consumer files:** These files (profit-forecast.ts, value-signal.ts, bid-policy/route.ts) handle empty data gracefully and will activate in v1.3c.
- **Adding orphaned components to magazine/original SKU Review variants:** Decision is main variant only.
- **Running destructive schema operations (DROP TABLE, ALTER TABLE DROP COLUMN):** All 18 tables are KEEP or DEFER, none PRUNE'd.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema introspection | Manual table-by-table queries | `information_schema.columns` aggregate query | Single query gets all tables/columns/types/constraints |
| GMC status data | New API endpoint | Existing `/api/gmc/status?master_sku=X` | Already built, reads from `gmc_product_status` cache table |
| Prompt lineage data | New data fetch logic | Existing PromptLineagePanel self-fetching | Component already fetches from `/api/prompt-lineage` on expand |
| Intent classification seed | Complex ML classification | Simple rule-based Python script | Seed data for validation only, not production classification |

**Key insight:** Phase 31 is about wiring existing pieces together, not building new ones. Almost every API route, component, and table already exists. The work is verification and connection.

## Common Pitfalls

### Pitfall 1: Breaking Shopping Funnel
**What goes wrong:** Any change to the Shopping Funnel page, its API routes, or its data sources causes production disruption.
**Why it happens:** Tier movement features seem related to Shopping Funnel, tempting developers to add features there.
**How to avoid:** Create an entirely separate page. Do not import from or modify Shopping Funnel files. The new page should have its own API routes if needed.
**Warning signs:** Any diff that touches `dashboard/src/app/(dashboard)/shopping-funnel/` or `dashboard/src/app/api/shopping-funnel/`.

### Pitfall 2: Schema Verification False Positives
**What goes wrong:** Assuming migration SQL matches production because "tables were applied out-of-band." Column types, constraints, or defaults may differ.
**Why it happens:** Out-of-band application may have used modified SQL, or subsequent manual alterations occurred.
**How to avoid:** Run actual `information_schema.columns` queries against production and diff with migration SQL. Don't trust the migration file alone.
**Warning signs:** TypeScript type mismatches after supposedly "verified" schema.

### Pitfall 3: SkuReviewClient Import Bloat
**What goes wrong:** Adding imports to SkuReviewClient.tsx that break other variants (magazine, original) or cause lint failures.
**Why it happens:** CLAUDE.md explicitly warns: "Each SkuReviewClient variant uses DIFFERENT subsets of imports -- always grep for usage before removing."
**How to avoid:** Only modify the main `SkuReviewClient.tsx`. Do NOT touch `.magazine.tsx` or `.original.tsx`. After adding imports, verify with `npm run build` and `npm run lint`.
**Warning signs:** Build errors mentioning unused imports in variant files.

### Pitfall 4: Seed Data Left in Production
**What goes wrong:** Test rows from the seed script remain in production tables after validation.
**Why it happens:** Cleanup step forgotten or fails silently.
**How to avoid:** Seed script should tag all rows with a recognizable marker (e.g., `policy_version = 'SEED_V31'`). Cleanup query: `DELETE FROM term_intent_state WHERE policy_version = 'SEED_V31'`.
**Warning signs:** term_intent_state or other tables showing suspicious data with identical timestamps.

### Pitfall 5: SCHEMA.md Missing New Tables
**What goes wrong:** Full refresh misses tables created in recent migrations (Phase 29-30).
**Why it happens:** Query scope too narrow or tables created in non-standard schemas.
**How to avoid:** Query `information_schema.tables WHERE table_schema = 'public'` first to get complete table list, then detail each table. Cross-check against known migrations.
**Warning signs:** Table count in SCHEMA.md doesn't match table count from `information_schema`.

## Code Examples

### Schema Verification Query
```sql
-- Get all columns for a specific table to verify against migration SQL
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'term_intent_state'
ORDER BY ordinal_position;
```

### Get All Production Tables
```sql
-- Complete table inventory for SCHEMA.md refresh
SELECT table_name,
       (SELECT count(*) FROM information_schema.columns c WHERE c.table_name = t.table_name AND c.table_schema = 'public') as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

### Seed Script Pattern (Python)
```python
# Seed term_intent_state from existing search_queries data
# Tag all seed rows for easy cleanup
import os
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Read top search terms
result = supabase.table("search_queries").select("search_term, custom_label_0, impressions, clicks").order("impressions", desc=True).limit(50).execute()

# Classify with simple rules
for row in result.data:
    term = row["search_term"].lower()
    if "allied brass" in term or "allied" in term:
        intent_class = "BRAND_CORE"
    elif any(kw in term for kw in ["towel bar", "soap dish", "toilet paper"]):
        intent_class = "PRODUCT_HIGH"
    elif any(kw in term for kw in ["bathroom accessories", "bath hardware"]):
        intent_class = "CATEGORY_MID"
    else:
        intent_class = "DISCOVERY_LOW"

    supabase.table("term_intent_state").upsert({
        "search_term": row["search_term"],
        "normalized_search_term": term,
        "custom_label_0": row.get("custom_label_0"),
        "intent_class": intent_class,
        "route_action": "funnel",
        "confidence": 0.5,
        "requires_review": True,
        "policy_version": "SEED_V31",  # Tag for cleanup
    }, on_conflict="normalized_search_term,custom_label_0").execute()
```

### Component Wiring (GmcDisapprovalBadge in SkuReviewClient)
```tsx
// Inside SkuReviewClient main variant
const [gmcStatus, setGmcStatus] = useState<{ issueCount: number; disapprovalCount: number } | null>(null)

useEffect(() => {
  fetch(`/api/gmc/status?master_sku=${encodeURIComponent(masterSku)}`)
    .then(r => r.json())
    .then(data => {
      if (data?.summary) {
        setGmcStatus({
          issueCount: data.summary.disapproved + data.summary.limited,
          disapprovalCount: data.summary.disapproved,
        })
      }
    })
    .catch(() => {}) // Silently fail -- don't block page
}, [masterSku])

// In render, near the SKU title:
{gmcStatus && gmcStatus.issueCount > 0 && (
  <GmcDisapprovalBadge
    issueCount={gmcStatus.issueCount}
    disapprovalCount={gmcStatus.disapprovalCount}
  />
)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SCHEMA.md manually maintained | Full refresh from information_schema | Phase 31 | Eliminates schema drift permanently |
| Orphaned components in codebase | Conditionally rendered on data availability | Phase 31 | No empty component shells visible to users |
| Empty DEFER'd pages with broken queries | "Coming Soon" gates | Phase 31 | Clear user expectations, no confusing empty states |

## Open Questions

1. **Which SKU has the richest data for E2E validation?**
   - What we know: Need a SKU with: generated content, published content (publish_events), performance baselines, performance snapshots, and ideally search query data.
   - What's unclear: Which specific SKU satisfies all criteria. Need to query production.
   - Recommendation: Run a query at validation time to find SKUs that appear in all required tables. Good candidates are SKUs published earliest (most time for snapshot accumulation).

2. **Does `gmc_product_status` have data for any SKU?**
   - What we know: The table exists and the API route reads from it. But no automated sync pipeline populates it.
   - What's unclear: Whether manual syncs have populated any rows.
   - Recommendation: Query the table first. If empty, GmcDisapprovalBadge will simply not render (which is correct behavior). The wiring is still valid.

3. **How many tables currently exist in production vs. what SCHEMA.md documents?**
   - What we know: SCHEMA.md is missing at least `funnel_snapshots_daily` (Phase 30). May be missing other recent additions.
   - What's unclear: Exact gap count.
   - Recommendation: First action in implementation should be a complete `information_schema.tables` query to establish the true production table inventory.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 2.x |
| Config file | `dashboard/vitest.config.ts` |
| Quick run command | `cd dashboard && npx vitest run --reporter=verbose` |
| Full suite command | `cd dashboard && npx vitest run` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MIGR-01 | Schema matches migration SQL for all KEEP'd tables | manual-only | N/A -- requires Supabase MCP queries against production | N/A |
| MIGR-02 | Build passes after any cleanup; DEFER'd files handle empty data | smoke | `cd dashboard && npm run build` | N/A (build check, not test file) |
| MIGR-03 | GmcDisapprovalBadge renders conditionally; PromptLineagePanel renders conditionally | manual-only | N/A -- requires browser rendering verification | N/A |
| MIGR-04 | SCHEMA.md matches information_schema output | manual-only | N/A -- documentation verification | N/A |

**Justification for manual-only tests:** All four MIGR requirements involve either production database verification (cannot unit test against real Supabase), browser rendering verification, or documentation accuracy. These are inherently verification tasks, not automatable behaviors. The E2E validation walkthrough serves as the integration test.

### Sampling Rate
- **Per task commit:** `cd dashboard && npm run build && npm run lint`
- **Per wave merge:** `cd dashboard && npx vitest run && npm run build`
- **Phase gate:** Full build + manual E2E walkthrough before `/gsd:verify-work`

### Wave 0 Gaps
None -- existing test infrastructure covers all automatable aspects (build, lint). The non-automatable aspects (schema verification, component rendering, E2E walkthrough) are manual by design per CONTEXT.md decisions.

## Sources

### Primary (HIGH confidence)
- Phase 28 migration triage (`28-migration-triage.md`) -- KEEP/DEFER decisions, TypeScript consumer file inventory, table schemas
- Phase 29 verification (`29-VERIFICATION.md`) -- content-impact page structure, FEED requirements satisfaction, artifact inventory
- Codebase inspection -- GmcDisapprovalBadge.tsx (43 lines), PromptLineagePanel.tsx (269 lines), SkuReviewClient.tsx props interface, Sidebar.tsx nav structure
- Migration files -- `035b_DEFERRED_unified_intent_execution_system.sql` (14 tables), `034b_DEFERRED_ga4_attribution_forensics.sql` (4 tables)
- SCHEMA.md -- current documentation state, identified gap (missing funnel_snapshots_daily)

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions -- user-locked choices from /gsd:discuss-phase session
- API route inspection -- `/api/gmc/status/route.ts`, `/api/prompt-lineage/route.ts` confirmed functional

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - entirely existing stack, no new dependencies
- Architecture: HIGH - all components, routes, and tables already exist; work is integration
- Pitfalls: HIGH - Shopping Funnel risk is real and well-documented; SkuReviewClient variant import issues documented in CLAUDE.md

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable -- no external dependencies or fast-moving APIs)
