# Phase 18: Diagnosis — Establish Ground Truth - Research

**Researched:** 2026-02-20
**Domain:** System diagnostics — code path tracing, feature flag auditing, data funnel analysis, content propagation verification
**Confidence:** HIGH (all findings based on direct codebase inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Coverage Funnel Output**
- Dashboard page: visual funnel on the **overview page** (not a new page)
- Clickable stages: clicking a funnel stage shows an **expandable SKU list** inline (not navigation to another page)
- Drop-off display: Claude's discretion on whether to show percentages between stages or just raw counts

**Code Path Tracing**
- Side-by-side comparison: trace both single-SKU UI regeneration path AND batch path, highlighting where they diverge
- Format: Claude's discretion (flowchart, markdown call graph, or hybrid)
- Documentation lives in BOTH places: `docs/architecture/` for long-term reference + `.planning/phases/18-*/` diagnostic report
- Feature flag audit (DIAG-03): Claude's discretion on whether to integrate into the path trace or keep as a separate deliverable

**Propagation Spot-Check**
- SKU selection: mix of criteria — some recently published, some older, some high-value, some random
- Comparison scope: Supabase `approved_content` vs Google Sheets rows ONLY (not full chain to GMC)
- Automation: Claude's discretion (reusable script vs one-time investigation)
- Discrepancy threshold: Claude's discretion

**Results Format & Consumers**
- Dual audience: Bobby via dashboard + downstream agents (Phase 19-20) via structured files
- Dashboard presentation: Claude's discretion on whether detailed findings go on overview page alongside funnel or on a separate /diagnosis page
- Agent-consumable format: BOTH database tables AND markdown reports in `.planning/`
- Freshness indicators: all diagnostic data shows timestamps ("Last run: X")

### Claude's Discretion
- Funnel drop-off presentation (percentages vs raw counts)
- Code path trace format (flowchart vs markdown vs hybrid)
- Feature flag audit placement (inline on trace vs separate)
- Spot-check automation level (reusable script vs one-time)
- Discrepancy threshold definition
- Dashboard layout for detailed findings (overview vs dedicated page)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DIAG-01 | System can report SKU coverage funnel (total catalog → generated → approved → published → confirmed in GMC) via SQL queries against existing Supabase data | All tables are confirmed in SCHEMA.md. SQL is constructable from `variant_index` (catalog count), `generated_content` (generated), `sku_approvals` (approved), `publish_events` (published), and Google Sheets comparison (confirmed). |
| DIAG-02 | Execution path for single-SKU UI regeneration is traced and documented, confirming which Python functions are invoked and which are bypassed (Path A vs Path B) | Path fully traced via `dashboard/src/app/api/regenerate/route.ts` → Cloud Run `/regenerate` → `main.py::regenerate_content()`. Generator.py's `build_prompt()` IS bypassed. Evidence/feature flags ARE called. |
| DIAG-03 | Feature flag call-site audit confirms which flags (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1) have active call sites in production code paths | All three flags confirmed in `feature_flags.py`. PROMPT_CONTRACT_V2 called from `prompt_loader.py`. INTENT_CURATOR_V1 and SEGMENT_STRATEGY_V1 called from `evidence.py`. All default to `True` (enabled). CRITICAL: None are called from `main.py::regenerate_content()`. |
| DIAG-04 | Propagation spot-check verifies whether published content actually reached Google Sheets rows and GMC feed (read-back verification) | Google Sheets Sheet ID confirmed. `publish_events.published_title` / `published_description` stored as snapshots. Comparison approach: fetch `approved_content` from Supabase, fetch matching Google Sheets rows by `gmc_offer_id`, diff. |
</phase_requirements>

---

## Summary

Phase 18 is a pure diagnostics phase — it produces findings and visualizations, not fixes. Research shows the codebase is well-instrumented and all four diagnostic questions can be answered via existing data and code inspection without writing new infrastructure. The largest risk is the code path divergence finding: the UI regeneration path (`/regenerate` endpoint in `main.py`) does NOT call the full pipeline (generator.py, keyword_placement.py, optimize.py), but the batch path also uses a simplified version of `main.py`. Both paths are simplified relative to the old CLI/optimize.py stack.

The coverage funnel is fully queryable from Supabase using existing tables. The feature flag audit reveals all three flags default to `True` but INTENT_CURATOR_V1 and SEGMENT_STRATEGY_V1 are only wired into `build_evidence_table()` — which IS called from both regeneration paths. PROMPT_CONTRACT_V2 controls which system prompt is used and IS wired in. The propagation spot-check requires a Google Sheets API read-back, which is a new capability but the credential infrastructure already exists.

**Primary recommendation:** Build DIAG-01 funnel as a new React component added to the existing overview page (`dashboard/src/app/(dashboard)/page.tsx`). Document DIAG-02 path trace as a markdown call graph in `docs/architecture/`. Store DIAG-04 spot-check results in a structured JSON file in `.planning/phases/18-*/`. Use a one-shot Python script for the spot-check (reusable enough to re-run, but no new DB table needed).

---

## Standard Stack

### Core (already in codebase — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js App Router | Current (Vercel) | Dashboard overview page modifications | Already deployed |
| React | 18+ | Funnel visualization component | Already in use |
| Supabase JS client | Current | SQL queries for funnel stages | Already configured |
| Google Sheets API | v4 (via existing `google-sheets.ts`) | Spot-check read-back of published content | Already authenticated |
| Python (supabase-py) | Current | One-shot spot-check script | Already in `.venv` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Tailwind CSS | Current | Funnel stage styling | Already in dashboard |
| shadcn/ui components | Current | Card, Badge, Collapsible for SKU lists | Already available |
| lucide-react | Current | Funnel/chevron icons | Already installed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline SKU list (collapsible) | Navigate to /review filtered | Locked decision — inline required |
| Python script for spot-check | New API route | Python has direct Sheets creds, simpler for one-time |
| New /diagnosis page | Overview page funnel | Locked decision — overview page required |

---

## Architecture Patterns

### DIAG-01: Coverage Funnel SQL Pattern

The funnel has five stages. All data is in Supabase. Key findings:

**Stage 1 — Total Catalog:**
```sql
-- Count distinct master_skus in variant_index (source of truth)
SELECT COUNT(DISTINCT master_sku) AS total_catalog FROM variant_index;
-- Expected: ~2,784 based on STATE.md
```

**Stage 2 — Generated Content:**
```sql
-- SKUs with at least one generated_content row (any platform, any content_type)
SELECT COUNT(DISTINCT master_sku) AS has_generated FROM generated_content;
```

**Stage 3 — Approved:**
```sql
-- SKUs with approval_status = 'approved' in sku_approvals
SELECT COUNT(*) AS approved FROM sku_approvals WHERE approval_status = 'approved';
```

**Stage 4 — Published:**
```sql
-- Distinct SKUs with at least one successful publish event
SELECT COUNT(DISTINCT master_sku) AS published
FROM publish_events
WHERE status = 'success' AND action = 'publish';
```

**Stage 5 — Confirmed in Google Sheets:**
This stage cannot be answered from Supabase alone. It requires the DIAG-04 spot-check. For the funnel display, this stage shows the spot-check sample result (e.g., "10/15 spot-checked confirmed matching") with a timestamp. It is NOT a live count — it is a diagnostic sample.

**Important nuance:** The `/api/stats` route already queries `sku_approvals` and `publish_events` for the overview page. The funnel can reuse these queries or augment the existing `/api/stats` endpoint with a `funnel` key.

### DIAG-01: Funnel React Component Pattern

The funnel must live on the overview page (`dashboard/src/app/(dashboard)/page.tsx`). Current overview page already has stat cards for "Total SKUs", "Approved", and "Published". The funnel should be a NEW component that presents the five stages in a visual flow with expandable SKU lists.

**Recommended: Augment `/api/stats` with funnel data.** The stats API already queries most of the needed tables. Add a `funnel` key to its response:

```typescript
// In /api/stats/route.ts — add to response
funnel: {
  total_catalog: number,    // COUNT(DISTINCT master_sku) FROM variant_index
  has_generated: number,    // COUNT(DISTINCT master_sku) FROM generated_content
  approved: number,         // COUNT(*) WHERE approval_status = 'approved'
  published: number,        // COUNT(DISTINCT) FROM publish_events WHERE success
  confirmed_sample: {       // From DIAG-04 spot-check (static, timestamped)
    checked: number,
    matched: number,
    last_run: string | null
  }
}
```

**Expandable SKU lists:** Each funnel stage needs a separate API endpoint (or parameterized query) to return the list of SKUs at that stage. These are fetched on-demand when user clicks a stage. Recommend a single endpoint `/api/funnel/skus?stage=generated&limit=100`.

**Drop-off recommendation (Claude's discretion):** Show BOTH percentages AND raw counts. At scale (2,784 SKUs), percentages communicate severity better than raw counts. Format: `N SKUs (X%)` between each stage with a down-arrow indicator for drop-off magnitude.

### DIAG-02: Code Path Call Graph

#### Single-SKU UI Regeneration (Path A)

```
User clicks "Regenerate" in dashboard UI
  └─→ POST /api/regenerate (Next.js route.ts)
        ├─→ resolveCanonicalMasterSku(supabase, master_sku)
        ├─→ ensureSkuData(canonicalMasterSku) [background, non-blocking]
        ├─→ Schema check on generated_content
        ├─→ Fetch variant_index data for finish_code
        ├─→ Fetch current generated_content for version tracking
        ├─→ Build feedbackText (combines preset + user feedback)
        └─→ POST {PIPELINE_URL}/regenerate [Python Cloud Run]
              └─→ main.py::regenerate_content()
                    ├─→ ensure_generation_enabled() [kill switch check]
                    ├─→ resolve_canonical_master_sku()
                    ├─→ load_parent_sku_from_supabase()  [supabase_loader.py]
                    ├─→ build_evidence_table()            [evidence.py]
                    │     ├─→ is_intent_curator_v1_enabled() [feature_flags.py]
                    │     └─→ is_segment_strategy_v1_enabled() [feature_flags.py]
                    ├─→ format_evidence_markdown()
                    ├─→ get_provider()                   [providers/__init__.py]
                    ├─→ get_system_prompt_hash()         [prompt_loader.py]
                    │     └─→ is_prompt_contract_v2_enabled() [feature_flags.py]
                    ├─→ _build_generation_user_prompt()  [main.py helper]
                    │     ├─→ get_category_guidance()
                    │     └─→ format_gold_standard_examples()
                    ├─→ _generate_with_metrics()         [main.py helper]
                    ├─→ _enforce_finish_sentence_parity() [if description + google/bing]
                    ├─→ generated_content upsert         [direct Supabase write]
                    └─→ regeneration_history insert      [direct Supabase write]
      └─→ Back in route.ts:
            ├─→ validateGeneratedContent() [prompts.ts — validation only]
            ├─→ Update generated_content version
            └─→ Upsert variant_finish_sentences
```

**BYPASSED in Path A (vs legacy CLI):**
- `optimize.py::run_optimization()` — NOT called
- `generator.py::build_prompt()` — NOT called
- `generator.py::generate_candidates()` — NOT called
- `pipeline/keyword_placement.py::build_keyword_placement_plan()` — NOT called (evidence.py fetches queries, but keyword placement plan is NOT built for regenerate)
- `pipeline/verifier.py::verify_claims()` — NOT called
- `pipeline/selection.py::select_best_candidate()` — NOT called (no multi-candidate selection)
- `pipeline/reporter.py` — NOT called

**INCLUDED in Path A:**
- `evidence.py::build_evidence_table()` with all feature flags — YES
- `prompt_loader.py::get_system_prompt()` with PROMPT_CONTRACT_V2 check — YES
- Gold standard examples from Supabase prompt_templates — YES
- Finish sentence generation — YES (for google/bing descriptions)

#### Batch Path (Path B)

```
POST /api/batch-optimize or /api/hybrid-generate (Next.js)
  └─→ POST {PIPELINE_URL}/batch-optimize or /hybrid-generate [Python Cloud Run]
        └─→ main.py::process_batch_job() or process_hybrid_batch_job()
              └─→ For each SKU: same core sequence as Path A
                    ├─→ load_parent_sku_from_supabase()
                    ├─→ build_evidence_table()           [same feature flags]
                    ├─→ _build_generation_user_prompt()  [same helper]
                    ├─→ _generate_with_metrics()
                    ├─→ _enforce_finish_sentence_parity()
                    └─→ _persist_generated_content_and_history()
```

**Key divergence between Path A and Path B:**
- Both paths call the SAME core functions in `main.py`
- Path A is synchronous (HTTP request waits for response)
- Path B is async (thread-based, `run_async_in_thread()`)
- Path B does NOT call `route.ts` validation (`validateGeneratedContent`)
- Path B uses `_persist_generated_content_and_history()` helper; Path A writes directly

**The legacy CLI path (optimize.py) is NOT used by either UI path.** The 6-agent pipeline is also a separate manual path not in the UI.

### DIAG-03: Feature Flag Audit

#### Flag Definitions

File: `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/feature_flags.py`

```python
def is_prompt_contract_v2_enabled() -> bool:
    return _is_enabled("PROMPT_CONTRACT_V2", True)   # Default: ENABLED

def is_intent_curator_v1_enabled() -> bool:
    return _is_enabled("INTENT_CURATOR_V1", True)    # Default: ENABLED

def is_segment_strategy_v1_enabled() -> bool:
    return _is_enabled("SEGMENT_STRATEGY_V1", True)  # Default: ENABLED
```

All three flags default to `True`. If the env var is not set in Cloud Run, all flags are **active**.

#### Call Sites in Production Paths

| Flag | Call Site | File | Called From Path A? | Called From Path B? |
|------|-----------|------|---------------------|---------------------|
| PROMPT_CONTRACT_V2 | `get_system_prompt()` | `prompt_loader.py:149` | YES (via `get_system_prompt_hash()`) | YES (same) |
| INTENT_CURATOR_V1 | `build_evidence_table()` | `evidence.py:371` | YES (evidence built in both paths) | YES |
| SEGMENT_STRATEGY_V1 | `build_evidence_table()` | `evidence.py:348` | YES | YES |
| SEGMENT_STRATEGY_V1 | `_resolve_segment_strategy()` | `generator.py:100` | NO (generator.py not called) | NO |

**Critical findings:**
1. PROMPT_CONTRACT_V2: When `True` (default), uses `CANONICAL_SYSTEM_PROMPT` from `prompts.py`. When `False`, falls back to Supabase `prompt_templates.system_prompt`. Since the env var is not set in Cloud Run (confirmed by absence in GCP secrets list), the flag defaults to `True` → canonical Python prompt IS active.

2. INTENT_CURATOR_V1: When `True`, uses `curate_search_queries_by_relevance()` (smarter relevance filtering). When `False`, uses `filter_search_queries_by_relevance()` (legacy simpler filter). Flag defaults to `True` → smart curator IS active.

3. SEGMENT_STRATEGY_V1: When `True` in evidence.py, uses `resolve_segment_strategy()` with data. When `False`, the strategy is disabled. Also called in `generator.py::_resolve_segment_strategy()` but that function is ONLY used by `build_prompt()` in the legacy CLI path — NOT by either UI path. So in both Path A and Path B, SEGMENT_STRATEGY_V1 affects only the evidence table, not a separate prompt section.

**Verification needed:** Confirm actual env var values in Cloud Run at runtime (GCP Secret Manager or Cloud Run service config). The flags may have been explicitly set to override the defaults.

### DIAG-04: Propagation Spot-Check

#### What to Compare

- **Source of truth:** `generated_content.approved_content` in Supabase (for `platform='google'`, `content_type='title'` and `content_type='description'`)
- **Target:** Google Sheets row in `SupplementalFeedData` sheet (Sheet ID: `1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg`)
- **Join key:** `variant_index.gmc_offer_id` (must uppercase for Sheets: `shopify_US_` not `shopify_us_`)
- **Columns in sheet:** H = `title`, J = `description`

#### SKU Selection Strategy (mix of criteria)

- 3-5 recently published (last 30 days) — highest probability of content present
- 3-5 older published (30-90 days ago) — check for drift
- 3-5 high-value (high impression volume from `search_queries`) — diagnostic priority
- 2-3 random from `publish_events` — breadth coverage

SQL to select the spot-check sample:
```sql
-- Recently published (last 30 days)
SELECT DISTINCT master_sku, MAX(published_at) as last_published
FROM publish_events
WHERE status = 'success' AND action = 'publish'
  AND published_at > NOW() - INTERVAL '30 days'
GROUP BY master_sku
ORDER BY last_published DESC
LIMIT 5;

-- Older published (30-90 days)
SELECT DISTINCT master_sku, MAX(published_at) as last_published
FROM publish_events
WHERE status = 'success' AND action = 'publish'
  AND published_at BETWEEN NOW() - INTERVAL '90 days' AND NOW() - INTERVAL '30 days'
GROUP BY master_sku
ORDER BY last_published DESC
LIMIT 5;
```

#### Discrepancy Threshold (Claude's discretion)

**Definition:** A discrepancy is MEANINGFUL if:
- Title differs by more than whitespace normalization (leading/trailing spaces, line breaks)
- Description differs after stripping `{FINISH_NAME}` placeholders and whitespace

A discrepancy is NOT meaningful (formatting artifact) if:
- Only difference is trailing whitespace or newline normalization
- HTML entity encoding differences (e.g., `&amp;` vs `&`)

**Automation recommendation:** Build a reusable Python script at `scripts/spot_check_propagation.py`. It can be re-run before Phase 20 to verify fixes took effect. The script outputs a JSON report to `.planning/phases/18-diagnosis-establish-ground-truth/spot-check-results.json`.

#### Spot-Check Script Structure

```python
# scripts/spot_check_propagation.py
# Inputs: list of master_skus, google_sheets_creds
# Outputs: JSON report with per-SKU match/mismatch

for master_sku in sample_skus:
    # 1. Fetch approved_content from Supabase
    supabase_title = fetch_approved_content(master_sku, 'google', 'title')
    supabase_desc = fetch_approved_content(master_sku, 'google', 'description')

    # 2. Get gmc_offer_ids for this master_sku
    offer_ids = fetch_offer_ids(master_sku)  # from variant_index

    # 3. Fetch Google Sheets rows by offer_id (uppercase)
    for offer_id in offer_ids:
        sheet_row = fetch_sheet_row(offer_id.upper())  # shopify_US_ format

    # 4. Compare (normalize whitespace)
    title_match = normalize(supabase_title) == normalize(sheet_row['title'])
    desc_match = normalize(supabase_desc) == normalize(sheet_row['description'])

    # 5. Record result
    results.append({...})
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Funnel stage counts | Custom aggregation service | Single SQL queries per stage | All data is in Supabase, one query per stage |
| Google Sheets auth | New OAuth flow | Existing `GOOGLE_SHEETS_*` env vars from `.env.vercel` | Already configured in `dashboard/src/lib/publishing/google-sheets.ts` |
| Feature flag documentation | Introspection endpoint | Direct code inspection (already done) | Flags are in 1 file, 25 lines total |
| Funnel visualization | D3.js or chart library | Tailwind + shadcn CSS | Simple 5-stage linear funnel, no interactivity needed beyond expand/collapse |

**Key insight:** This phase is pure investigation + lightweight UI. All the hard infrastructure (Supabase connection, Google Sheets auth, Python pipeline) already exists. The primary deliverables are SQL queries, a React component, architecture documentation, and a Python script.

---

## Common Pitfalls

### Pitfall 1: Stats API Counting Mismatch

**What goes wrong:** The `/api/stats` route counts `generated_content` rows (not distinct SKUs). A SKU with title+description×3 platforms = 6 rows. `totalSkus` in the current stats API is `Math.max(approvals.length, totalGenerated)` which could be very wrong for the funnel.

**Why it happens:** The stats API was not designed for per-SKU funnel counting.

**How to avoid:** The funnel SQL must use `COUNT(DISTINCT master_sku)`, not COUNT(*). The existing stats API totalSkus is unreliable as a funnel stage count.

**Warning signs:** If funnel "has_generated" shows 6x the expected SKU count, the query is counting rows not SKUs.

### Pitfall 2: Offer ID Case Mismatch in Spot-Check

**What goes wrong:** Google Sheets rows use `shopify_US_` (uppercase) but `variant_index` stores `shopify_us_` (lowercase). Looking up by the database value will find no rows.

**Why it happens:** Documented in CLAUDE.md and MEMORY.md — critical known issue.

**How to avoid:** Always uppercase when reading from Sheets: `offer_id.replace('shopify_us_', 'shopify_US_')`. Do case-insensitive lookup when writing.

### Pitfall 3: Feature Flag "Enabled" Does Not Mean "Wired Into Path"

**What goes wrong:** Reporting flags as "active" when they are defined as enabled but their call sites are in functions not executed by the production paths.

**Why it happens:** SEGMENT_STRATEGY_V1 is imported in `generator.py::_resolve_segment_strategy()` but that function is only called by the legacy CLI path (optimize.py), not by main.py's regenerate/batch endpoints.

**How to avoid:** Audit call sites, not just flag definitions. The research has already done this — document findings clearly in the architecture doc.

### Pitfall 4: Dashboard Overview Page Modification Breaking Existing Stats

**What goes wrong:** Adding funnel queries to `/api/stats` introduces new slow queries that break the page load time.

**Why it happens:** The funnel requires `COUNT(DISTINCT master_sku) FROM variant_index` — a full table scan on 72K rows.

**How to avoid:** Add funnel data as a separate API endpoint (`/api/funnel/summary`) loaded asynchronously, OR add it as a lightweight addition to `/api/stats` that uses indexed columns only. Since `variant_index` has `idx_variant_master_sku`, COUNT(DISTINCT) should be fast. Test query performance before deploying.

### Pitfall 5: Published Count Ambiguity

**What goes wrong:** "Published" means different things — a SKU in a completed publish batch vs a SKU with a successful `publish_events` record.

**Why it happens:** `publish_batches` has status `published`/`partial`/`failed`. `publish_events` has per-SKU records with `status = 'success'`. These can diverge if a batch partially failed.

**How to avoid:** Use `publish_events` for the funnel (per-SKU audit log), not `publish_batches` (batch-level aggregate). This is more accurate.

---

## Code Examples

### Funnel Stage Queries (verified against SCHEMA.md)

```sql
-- Stage 1: Total unique master_skus in catalog
SELECT COUNT(DISTINCT master_sku) AS total_catalog
FROM variant_index;

-- Stage 2: SKUs with any generated content (title or description, any platform)
SELECT COUNT(DISTINCT master_sku) AS has_generated
FROM generated_content;

-- Stage 3: SKUs with master-level approval
SELECT COUNT(*) AS approved
FROM sku_approvals
WHERE approval_status = 'approved';

-- Stage 4: SKUs with at least one successful publish event
SELECT COUNT(DISTINCT master_sku) AS published
FROM publish_events
WHERE status = 'success' AND action = 'publish';

-- Stage 5 (diagnostic sample — not a live count)
-- Requires Google Sheets read-back via DIAG-04

-- Bonus: SKUs at each stage for expandable lists
-- Stage 2 expandable list:
SELECT DISTINCT master_sku
FROM generated_content
ORDER BY master_sku
LIMIT 100;

-- Stage 3 expandable list:
SELECT master_sku
FROM sku_approvals
WHERE approval_status = 'approved'
ORDER BY approved_at DESC
LIMIT 100;

-- Stage 4 expandable list:
SELECT DISTINCT master_sku
FROM publish_events
WHERE status = 'success' AND action = 'publish'
ORDER BY master_sku
LIMIT 100;
```

### Feature Flag Runtime Status Check

```bash
# Check what env vars are set in Cloud Run
gcloud run services describe feedops-pipeline \
  --project=bobbys-project-346400 \
  --region=us-east1 \
  --format='json' | jq '.spec.template.spec.containers[0].env'
```

This reveals whether PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, or SEGMENT_STRATEGY_V1 are explicitly set or relying on defaults (True).

### Google Sheets Read-Back (spot-check)

```python
# Pattern from existing google-sheets.ts, ported to Python
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = '1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg'
SHEET_NAME = 'SupplementalFeedData'

# Column positions (1-indexed, from CLAUDE.md):
# A=1: id (gmc_offer_id)
# H=8: title
# J=10: description

def fetch_sheet_row_by_offer_id(sheet, offer_id_uppercase: str) -> dict | None:
    """Find row by GMC offer ID (case-insensitive search in column A)."""
    all_values = sheet.get_all_values()
    for row in all_values[1:]:  # skip header
        if row[0].lower() == offer_id_uppercase.lower():
            return {
                'offer_id': row[0],
                'title': row[7] if len(row) > 7 else '',      # Column H
                'description': row[9] if len(row) > 9 else ''  # Column J
            }
    return None
```

### Funnel React Component Skeleton

```typescript
// New component: dashboard/src/components/dashboard/CoverageFunnel.tsx
interface FunnelData {
  total_catalog: number
  has_generated: number
  approved: number
  published: number
  confirmed_sample: { checked: number; matched: number; last_run: string | null }
}

interface FunnelStage {
  label: string
  count: number
  key: 'total_catalog' | 'has_generated' | 'approved' | 'published' | 'confirmed'
}

// Component renders stages with drop-off percentages between them
// Each stage is clickable → fetches SKU list from /api/funnel/skus?stage=X
// SKU list renders as a collapsible below the funnel bar
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Legacy CLI `optimize.py` | FastAPI `main.py` endpoints for all UI paths | generator.py / keyword_placement.py / verifier.py bypassed in UI paths |
| TypeScript-side prompt construction (`core.ts`) | Dead code — Python pipeline is the authority | TypeScript prompts in `regeneration/prompts.ts` are validation-only |
| Separate content generation for each path | Unified `_build_generation_user_prompt()` in `main.py` | Both single-SKU and batch use identical prompt construction |
| `BackgroundTasks` for batch | `run_async_in_thread()` | Survives Cloud Run container lifecycle |

**Deprecated/outdated:**
- `dashboard/src/lib/regeneration/core.ts`: Dead code, NOT called for content generation. CLAUDE.md confirms this explicitly.
- `generator.py::build_prompt()`: Only used by legacy CLI (`optimize.py`) and the 6-agent pipeline. Not in UI paths.

---

## Open Questions

1. **Cloud Run env var values for feature flags**
   - What we know: Flags default to `True` if env vars are not set. GCP secrets list shows 9 secrets (none are the feature flag names).
   - What's unclear: Whether these env vars are set directly in the Cloud Run service config (not as secrets). They might be hardcoded in the Cloud Run service definition.
   - Recommendation: Run `gcloud run services describe feedops-pipeline --format=json` to inspect env vars during Phase 18 execution.

2. **Volume of published SKUs for spot-check**
   - What we know: `publish_events` table exists, `status = 'success'` filter works.
   - What's unclear: How many distinct SKUs have been successfully published (the actual count). STATE.md mentions 79/2,784 had content as of 17-01.
   - Recommendation: Run the Stage 4 funnel query first to establish the baseline count before selecting spot-check sample.

3. **keyword_bank.json in Cloud Run container**
   - What we know: STATE.md flags this as a concern. The file may be gitignored.
   - What's unclear: Whether evidence.py's keyword functions degrade gracefully if the file is missing.
   - Recommendation: Check gitignore and Cloud Run container during Phase 18 execution.

4. **The `{FINISH_NAME}` placeholder bug**
   - What we know: STATE.md documents a confirmed bug in `expand-variants.ts` where `{FINISH_NAME}` appears in approved content for SKU 102.
   - What's unclear: How many SKUs are affected. This should be checked during DIAG-04 spot-check.
   - Recommendation: Add a SQL check for `{FINISH_NAME}` in `generated_content.approved_content` as part of DIAG-04.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/main.py` — Full `/regenerate` and batch endpoint implementation
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/feature_flags.py` — All three flag definitions and defaults
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/prompt_loader.py` — PROMPT_CONTRACT_V2 call site
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/evidence.py` — INTENT_CURATOR_V1 and SEGMENT_STRATEGY_V1 call sites (lines 348, 371)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/generator.py` — Confirms generator.py NOT called from main.py paths
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/regenerate/route.ts` — Full TypeScript proxy implementation
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/(dashboard)/page.tsx` — Current overview page structure
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/stats/route.ts` — Current stats API queries
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` — All table definitions verified
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/runtime_controls.py` — Kill switch definitions

### Secondary (MEDIUM confidence — project documentation)

- `CLAUDE.md` — Google Sheets column layout, offer ID case requirements, Stack rules
- `.planning/STATE.md` — Known issues, deployment state, key context
- `.planning/REQUIREMENTS.md` — Requirement IDs and descriptions

---

## Metadata

**Confidence breakdown:**
- DIAG-01 SQL queries: HIGH — all tables confirmed in SCHEMA.md, queries are straightforward
- DIAG-02 path trace: HIGH — full call graph reconstructed from direct code inspection
- DIAG-03 feature flag audit: HIGH — all call sites found via grep, defaults confirmed in code
- DIAG-04 spot-check approach: HIGH for design, MEDIUM for execution (depends on actual published SKU count and Google Sheets API auth working as expected)
- Funnel React component: HIGH — uses existing patterns from overview page
- Generator.py bypass finding: HIGH — confirmed by grep showing `optimize.py` is the ONLY importer of `generator.py`

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (30 days — code paths are stable)

---

## Appendix: Key File Paths for Implementer

| Concern | File |
|---------|------|
| Feature flag definitions | `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/feature_flags.py` |
| PROMPT_CONTRACT_V2 call site | `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/prompt_loader.py:149` |
| INTENT_CURATOR_V1 call site | `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/evidence.py:371` |
| SEGMENT_STRATEGY_V1 call site (evidence) | `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/evidence.py:348` |
| SEGMENT_STRATEGY_V1 call site (generator — legacy only) | `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/generator.py:100` |
| Single-SKU regeneration Python handler | `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/main.py:942` (regenerate_content) |
| Batch Python handler | `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/main.py:1418` (process_batch_job) |
| TypeScript regeneration proxy | `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/regenerate/route.ts` |
| Dashboard overview page | `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/(dashboard)/page.tsx` |
| Stats API | `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/stats/route.ts` |
| Google Sheets lib | `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/publishing/google-sheets.ts` |
| Google Sheets Sheet ID | `1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg` |
