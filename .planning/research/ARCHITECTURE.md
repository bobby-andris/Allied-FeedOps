# Architecture Research

**Domain:** Feed optimization diagnostic layer — impact debugging and tracing for existing content generation/publishing pipeline
**Researched:** 2026-02-20
**Confidence:** HIGH (based on direct code inspection, not inferred)

---

## Standard Architecture

### System Overview (Existing)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Dashboard (Next.js / Vercel)                 │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ SKU Review   │  │  Batches     │  │  Monitoring / Perf   │   │
│  │   Pages      │  │   Pages      │  │      Pages           │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │               │
│  ┌──────▼─────────────────▼──────────────────────▼───────────┐  │
│  │              Next.js API Routes (/api/*)                   │  │
│  │  /regenerate  /publish/google  /monitoring/performance-    │  │
│  │  /batches     /publish/bing    delta  /stats  /approvals   │  │
│  └──────┬─────────────────────────────────────────────────────┘  │
└─────────┼───────────────────────────────────────────────────────-┘
          │ HTTP POST (FEEDOPS_PIPELINE_URL)
          ▼
┌─────────────────────────────────────────────────────────────────┐
│              Python Pipeline (Cloud Run / FastAPI)               │
│                                                                   │
│  Endpoints:                                                       │
│  /regenerate  /optimize-sku  /batch-optimize  /hybrid-generate   │
│  /performance/*  /search-insights/sync  /backfill/*              │
│                                                                   │
│  ┌──────────────┐  ┌────────────────┐  ┌───────────────────┐    │
│  │  generator   │  │ segment_strat  │  │  observability    │    │
│  │  evidence    │  │ feature_flags  │  │  metrics_registry │    │
│  │  prompts     │  │ runtime_ctrl   │  │  log_event()      │    │
│  └──────────────┘  └────────────────┘  └───────────────────┘    │
└──────────────────────────────┬──────────────────────────────────-┘
                               │
          ┌────────────────────┼────────────────────────┐
          │                    │                        │
          ▼                    ▼                        ▼
┌──────────────┐   ┌─────────────────────┐  ┌──────────────────────┐
│   Supabase   │   │    Google Sheets     │  │  Google Ads API /    │
│              │   │ Supplemental Feed    │  │  GMC Merchant API    │
│  Tables:     │   │                     │  │                      │
│  generated_  │   │  Rows updated by    │  │  Source of search    │
│  content     │   │  gmc_offer_id (28   │  │  terms, performance  │
│  publish_    │   │  variants per SKU)  │  │  baselines,          │
│  events      │   │                     │  │  snapshots           │
│  performance_│   └──────────┬──────────┘  └──────────────────────┘
│  baselines   │              │
│  perf_       │              ▼
│  snapshots   │   ┌─────────────────────┐
│  regen_hist  │   │   Google Merchant   │
│  ...32 tables│   │      Center (GMC)   │
└──────────────┘   └─────────────────────┘
```

---

### The Two Generation Paths (Critical Distinction)

There are **two separate code paths** that generate content. This is the primary diagnostic complexity and the most important finding in this research.

```
Path A: Single-SKU regeneration (ACTIVE — used by SKU review UI)
──────────────────────────────────────────────────────────────────
UI click → /api/regenerate (route.ts, thin proxy)
         → Python Cloud Run /regenerate
         → _build_generation_user_prompt() in main.py
           [NOT generator.py — segment_strategy NOT used here]
         → _enforce_finish_sentence_parity()
         → Supabase: generated_content upsert + regeneration_history insert

Path B: Batch/optimize generation (used by /batch-optimize, /hybrid-generate)
──────────────────────────────────────────────────────────────────────────────
/api/regenerate/batch or /api/sku-selection/generate-hybrid
         → Python /batch-optimize or /hybrid-generate
         → generator.py: build_split_prompt()
           [Includes: segment_strategy, keyword_plan, evidence_table, gold_examples]
         → generate_candidates() → parse_candidate_response()
         → Saves Candidate model (multi-field: google_title, bing_title, etc.)

Path C: Legacy TypeScript batch regeneration (NOT for single-SKU)
──────────────────────────────────────────────────────────────────
Called ONLY by: /api/regenerate/batch/route.ts
Calls OpenAI directly, has own evidence builder, own prompt templates
This path bypasses the Python pipeline entirely
```

**Diagnostic implication:** Feature flags PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1 are only evaluated in Path B (generator.py). Single-SKU regeneration (Path A, the most-used path) does NOT invoke generator.py at all. It uses `_build_generation_user_prompt()` in main.py which calls neither feature flags nor segment strategy.

---

### Feature Flag Observability Gap (Confirmed by Code Inspection)

```
Flag                   | Defined In          | Default | Active Call Sites in Live Paths
-----------------------|---------------------|---------|--------------------------------
SEGMENT_STRATEGY_V1    | feature_flags.py    | True    | generator.py only (Path B)
                       |                     |         | NOT in main.py /regenerate (Path A)
PROMPT_CONTRACT_V2     | feature_flags.py    | True    | NONE FOUND in main.py or generator.py
                       |                     |         | Flag exists, no active call sites
INTENT_CURATOR_V1      | feature_flags.py    | True    | NONE FOUND in main.py or generator.py
                       |                     |         | Flag exists, no active call sites
FEEDOPS_DISABLE_       | runtime_controls.py | False   | main.py /regenerate (kill switch)
  GENERATION           |                     |         | Separate from feature_flags.py
```

**Key finding:** PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 appear to be defined but never called in any production code path. This needs static verification (grep) before drawing final conclusions.

---

### Content Propagation Chain

```
1. generation_timestamp set → candidate_content saved to generated_content
2. User approves → approved_content set (immutable copy in same row)
3. Batch created → batch_sku_assignments links master_sku to publish_batch
4. Publish triggered → /api/publish/google reads approved_content
5. Variant expansion → 28 gmc_offer_ids per master_sku (from variant_index)
6. Google Sheets update → rows matched by gmc_offer_id
7. GMC feed sync → Google Sheets → GMC (NOT Shopify auto-sync; manual feed)
8. Auction signals reflect new content (2-4 week lag in Google Ads performance)

Known breakpoints where content silently stops propagating:
- Step 2: No approved_content → publish reads nothing
- Step 5: variant_index gaps → some gmc_offer_ids missing → partial expansion
- Step 6: Case mismatch (lowercase shopify_us_ vs required uppercase shopify_US_)
           → rows append as duplicates instead of updating existing rows
- Step 7: GMC feed sync delay — can be 24-72 hours after Sheets update
- Step 8: Content relevance signal takes 2-4 weeks to show in auction metrics
```

---

## Component Responsibilities

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `main.py /regenerate` | Single-SKU content generation (Path A) | ACTIVE |
| `generator.py` | Multi-SKU batch content generation (Path B) | ACTIVE for batch only |
| `feature_flags.py` | Runtime flag definitions (SEGMENT_STRATEGY, etc.) | Defined; partial wiring |
| `runtime_controls.py` | Kill switches (FEEDOPS_DISABLE_GENERATION) | ACTIVE |
| `observability/__init__.py` | Structured log events with request_id | ACTIVE |
| `observability/metrics.py` | In-memory Prometheus metrics | ACTIVE |
| `core.ts` | Legacy TypeScript generation (Path C) | ACTIVE for batch regen only |
| `route.ts /api/regenerate` | Thin proxy to Python pipeline | ACTIVE |
| `google-sheets.ts` | Publish approved_content to supplemental feed | ACTIVE |
| `publish_events` table | Audit log with content snapshots | ACTIVE |
| `performance_impact_scores` table | Diff-in-diff impact calculations | ACTIVE (pipeline fills it) |

---

## Recommended Project Structure (Diagnostic Layer — Additive Only)

The diagnostic layer is additive. No changes to existing generation paths until root cause is confirmed.

```
src/feedops/
├── diagnostics/                  # NEW — diagnostic utilities
│   ├── __init__.py
│   ├── coverage_queries.py       # NEW — coverage funnel SQL queries (read-only)
│   └── flag_inspector.py         # NEW — call-site audit + runtime flag state
│
├── api/
│   ├── diagnostics.py            # NEW — /diagnostics/* FastAPI router
│   └── main.py                   # EXISTING — minor: add generation_path to log_event calls
│
└── pipeline/
    └── feature_flags.py          # EXISTING — no changes in diagnostic phase

dashboard/src/app/api/
└── diagnostics/
    ├── coverage/route.ts         # NEW — SKU coverage funnel endpoint
    └── flag-status/route.ts      # NEW — live feature flag state (calls Cloud Run)
```

---

## Architectural Patterns

### Pattern 1: Coverage Query (Zero-Risk Diagnostic)

**What:** All coverage data already exists in Supabase. Write diagnostic SQL queries joining existing tables to answer "of 2,784 SKUs, how many have content at each funnel stage?" No new data collection.

**When to use:** Phase 1 of diagnostics — before any code changes, answer coverage question.

**Trade-offs:** Read-only, zero risk. Immediate answer. No deployment needed.

**Example:**
```sql
-- Coverage funnel (all data exists today, no new tables needed)
SELECT
  (SELECT COUNT(DISTINCT master_sku) FROM variant_index)
    AS total_skus,
  (SELECT COUNT(DISTINCT master_sku) FROM generated_content
   WHERE candidate_content IS NOT NULL)
    AS skus_with_generated_content,
  (SELECT COUNT(DISTINCT master_sku) FROM generated_content
   WHERE approved_content IS NOT NULL)
    AS skus_with_approved_content,
  (SELECT COUNT(DISTINCT master_sku) FROM publish_events
   WHERE platform = 'google')
    AS skus_published_to_google,
  (SELECT COUNT(DISTINCT master_sku) FROM publish_events
   WHERE platform = 'google'
     AND published_at > NOW() - INTERVAL '90 days')
    AS skus_published_google_last_90d;
```

### Pattern 2: Trace-Passthrough (Non-Breaking Path Tracing)

**What:** Add a `x-diagnostic-trace: true` request header. When present, generation paths emit extra structured log fields identifying which code path executed, which flags were evaluated, and what evidence was assembled. Generation logic is unchanged.

**When to use:** Phase 3 — confirming which code path executed for a specific SKU request.

**Trade-offs:** Slight overhead only on traced requests. No persistent storage needed for one-off checks.

**Example:**
```python
# In main.py /regenerate endpoint — minimal addition
trace_enabled = request.headers.get("x-diagnostic-trace") == "true"

if trace_enabled:
    log_event(
        logger,
        logging.INFO,
        "diagnostic.path_entry",
        endpoint="regenerate",
        generation_path="main.py/_build_generation_user_prompt",
        # This is NOT generator.py — segment_strategy is not called here
        segment_strategy_called=False,
        feature_flags_evaluated=[],  # Empty — none called in this path
        evidence_builder="main.py/build_evidence_table",
    )
```

### Pattern 3: Static Flag Call-Site Audit

**What:** Grep Python source files to find every location where each feature flag function is called. Establish ground truth for which flags affect which generation paths.

**When to use:** Phase 2 — before changing any code, confirm which flags are actually wired.

**Trade-offs:** Zero risk. 30 minutes. Answers the flag question definitively.

**Example:**
```bash
# Audit all flag call sites
grep -rn \
  "is_prompt_contract_v2_enabled\|is_intent_curator_v1_enabled\|is_segment_strategy_v1_enabled" \
  src/feedops/ --include="*.py"

# Expected output (based on code inspection):
# src/feedops/pipeline/generator.py:36: from feedops.pipeline.feature_flags import is_segment_strategy_v1_enabled
# src/feedops/pipeline/generator.py:101: enabled=is_segment_strategy_v1_enabled()
# (No results for PROMPT_CONTRACT_V2 or INTENT_CURATOR_V1 in live paths)
```

### Pattern 4: Propagation Diff (DB Content vs Live Sheet)

**What:** Compare `approved_content` in Supabase against content currently in Google Sheets for a sample of recently published SKUs.

**When to use:** Phase 4 — after confirming content is approved and published_events exists, verify it actually reached Google Sheets.

**Trade-offs:** Requires Google Sheets API read (already available). Run as one-off diagnostic, not continuous. 10-20 SKU sample is sufficient.

**Implementation:** Use existing `buildColumnMap()` + read path from `google-sheets.ts` to fetch rows by gmc_offer_id, compare titles/descriptions vs Supabase `approved_content`.

---

## Data Flow

### Request Flow: Single-SKU Regeneration (Path A)

```
Dashboard UI (SKU review page)
    ↓ POST /api/regenerate {master_sku, content_type, platform, mode}
Next.js route.ts (validates, calls ensureSkuData() non-blocking)
    ↓ POST {PIPELINE_URL}/regenerate {master_sku, content_type, platform, feedback, finish_code}
Python main.py /regenerate endpoint
    ↓ ensure_generation_enabled() [checks FEEDOPS_DISABLE_GENERATION kill switch]
    ↓ resolve_canonical_master_sku()
    ↓ load_parent_sku_from_supabase()
    ↓ build_evidence_table() → format_evidence_markdown()
    ↓ _build_generation_user_prompt()  [NOT generator.py; segment_strategy NOT called]
    ↓ get_provider().generate()        [OpenAI via provider abstraction]
    ↓ _enforce_finish_sentence_parity() [for google/bing descriptions]
    ↓ supabase.generated_content.upsert()
    ↓ supabase.regeneration_history.insert()
    ↓ Returns {content, prompt_hash, model, finish_sentences}
route.ts saves candidate_content + generation metadata
    ↓ Returns {success, content, version, pipeline: "python"}
```

### Coverage Funnel (All Data in Supabase Today)

```
variant_index: 2,784 master_skus (total catalog)
    ↓ (unknown without query)
generated_content: ? master_skus with candidate_content
    ↓ (requires user approval action)
generated_content: ? master_skus with approved_content
    ↓ (requires batch publish action)
publish_events: ? master_skus with at least one google publish event
    ↓ (variant expansion: 28 gmc_offer_ids per master_sku)
Google Sheets: ? rows with updated content (not tracked in Supabase)
    ↓ (24-72hr GMC sync lag)
Google Ads: performance metrics reflect new content (2-4 week signal lag)
```

### Performance Impact Signal Flow

```
publish_events.published_at (Supabase)
    → performance_baselines (30d pre-publish metrics, captured before publish)
    → performance_snapshots (post-publish tracking, days_since_publish calculated)
    → performance_impact_scores (diff-in-diff, computed by /performance/compute-impact)
    → Dashboard /api/monitoring/performance-delta reads scorecards
    → Labels each publish_event as positive/negative/neutral
```

---

## Diagnostic Data Availability Assessment

### What Already Exists in Supabase (No New Collection Needed)

| Diagnostic Question | Table / Column | Available |
|--------------------|----------------|-----------|
| How many SKUs have generated content? | `generated_content.candidate_content IS NOT NULL` | YES |
| How many SKUs have approved content? | `generated_content.approved_content IS NOT NULL` | YES |
| When was content last generated per SKU? | `generated_content.generation_timestamp` | YES |
| What model generated each piece of content? | `generated_content.generation_model` | YES |
| What prompt hash was used? | `generated_content.generation_prompt_hash` | YES |
| How many SKUs have been published to Google? | `publish_events WHERE platform = 'google'` | YES |
| When was each SKU last published? | `publish_events.published_at` | YES |
| Performance before publish? | `performance_baselines` | YES |
| Performance after publish? | `performance_snapshots`, `performance_impact_scores` | YES |
| Which mode was used per generation? | `regeneration_history.mode` | YES (partial) |
| What segment strategy was applied? | `regeneration_history` | NO — strategy_id not stored |
| Which feature flags were active? | Anywhere | NO — not stored |
| Which generation path (A/B/C) was taken? | Anywhere | NO — not stored |
| Is content in Google Sheets matching Supabase? | Not in Supabase | NO — requires Sheets API |

### What Needs New Instrumentation (Add Only After Root Cause Confirmed)

| Diagnostic Need | Where to Add | Complexity |
|----------------|--------------|------------|
| Flag snapshot per generation | `regeneration_history` — add `flag_snapshot JSONB` column | LOW — 1 migration + ~3 lines per path |
| Generation path identifier | `regeneration_history` — add `generation_path TEXT` column | LOW — 1 migration + label in each endpoint |
| Sheets content verification | One-off script using existing `google-sheets.ts` read path | LOW — ~50 lines |
| Live flag state endpoint | `/diagnostics/flags` Cloud Run route | LOW — reads env vars, returns JSON |
| Coverage dashboard UI | SQL query exposed via `/api/diagnostics/coverage` route | LOW — ~30 lines TS + SQL |

---

## Build Order for Diagnostics (Diagnose First, Fix Second)

The order prioritizes proving root cause with zero code changes before touching any generation logic.

### Step 1 — Coverage Query (Zero code, 1 hour, immediate answer)

Answer: "How many of 2,784 SKUs have content at each funnel stage?"

- Run SQL directly via `mcp__supabase__execute_sql`
- Read-only queries against `variant_index`, `generated_content`, `publish_events`
- **Decision gate:** If <10% of SKUs are published to Google, coverage is the bottleneck — proceed to fix coverage before changing anything else

### Step 2 — Flag Call-Site Audit (Zero code, 30 minutes)

Answer: "Are PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 called anywhere in live paths?"

- Static grep on `src/feedops/` Python files
- **Expected finding:** SEGMENT_STRATEGY_V1 called in generator.py only (Path B). PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 likely have no active call sites.
- **Decision gate:** Confirms which flags are dead vs active — determines whether flag wiring is a fix candidate

### Step 3 — Path Trace for Single SKU (Minimal code change, 2 hours)

Answer: "When we regenerate SKU X from the UI, which code path executes?"

- Add one `log_event()` call to main.py /regenerate with `generation_path` field
- Trigger a real regeneration (low-traffic SKU)
- Read Cloud Run logs filtered by request_id
- **Expected finding:** Confirms Path A (main.py, not generator.py, no segment strategy)
- **Decision gate:** Confirms whether wiring segment_strategy into Path A is a meaningful fix candidate

### Step 4 — Propagation Check (Read-only Sheets API call)

Answer: "For SKUs with recent publish_events, does Google Sheets have the updated content?"

- Query `publish_events` for 10 most recent Google publishes
- Read those gmc_offer_ids from Google Sheets
- Compare vs `approved_content` in Supabase
- **Decision gate:** If Sheets content is stale or missing, propagation failure is a root cause

### Step 5 — Apply Minimal Fixes (Only after steps 1-4 complete)

Fixes are selected based on what steps 1-4 reveal:

| Finding | Fix |
|---------|-----|
| Coverage <10% published | Run batch generation + approval for top N SKUs by impressions |
| PROMPT_CONTRACT_V2 has no call sites | Either wire it or remove the dead flag (depends on intent) |
| Path A missing segment_strategy | Add `_resolve_segment_strategy()` to `_build_generation_user_prompt()` in main.py |
| Propagation gap (Sheets stale) | Fix case normalization or row-matching in `google-sheets.ts` |
| Performance data is stale | Run `/api/performance/capture-snapshot` to refresh `performance_impact_scores` |

---

## Anti-Patterns

### Anti-Pattern 1: Fix Before Diagnosing

**What people do:** Assume the flags aren't wired, wire them to the regeneration path, push, and wait to see if metrics improve.
**Why it's wrong:** You've changed behavior without knowing the root cause. If coverage is the bottleneck, wiring flags adds complexity with no improvement. Any metric change becomes unattributable.
**Do this instead:** Steps 1-4 first. Fix only what the evidence points to.

### Anti-Pattern 2: Treating core.ts as the Active Single-SKU Path

**What people do:** Find `dashboard/src/lib/regeneration/core.ts` and assume it's the primary generation path.
**Why it's wrong:** `core.ts` is called only by `/api/regenerate/batch/route.ts`. The primary `/api/regenerate` route (used by the SKU review UI) is a thin proxy to Python Cloud Run. `core.ts` improvements don't affect single-SKU regeneration from the UI.
**Do this instead:** For single-SKU improvements, modify Python `main.py /regenerate` or `_build_generation_user_prompt()`.

### Anti-Pattern 3: Trusting Performance Dashboard Labels as Root Cause

**What people do:** See "neutral" impact labels on the performance delta page and conclude content isn't working.
**Why it's wrong:** "Neutral" could mean: (a) content never reached GMC (propagation gap), (b) not enough days post-publish for signal, (c) insufficient impressions for statistical significance, (d) diff-in-diff limitations with sparse data. Performance labels don't tell you why.
**Do this instead:** Step 1 (coverage) and Step 4 (propagation) establish whether content reached GMC before interpreting impact labels.

### Anti-Pattern 4: Treating feature_flags.py as Evidence Flags Are Active

**What people do:** Read `feature_flags.py`, see `default=True` for all flags, conclude they're all active in production.
**Why it's wrong:** A flag with `default=True` but no call sites in active code paths has zero effect. The existence of the flag function is not evidence it's invoked.
**Do this instead:** Static audit (Step 2) to find actual call sites.

### Anti-Pattern 5: Interpreting Metrics_Registry as Real Monitoring

**What people do:** Look at `src/feedops/observability/metrics.py` and assume metrics are persisted for analysis.
**Why it's wrong:** `MetricsRegistry` is in-memory only. Metrics reset on container restart. It's used for Prometheus `/metrics` endpoint only, not for historical querying. Cloud Run logs are the durable diagnostic source.
**Do this instead:** For historical diagnostic queries, read Cloud Run logs via GCP Logs Explorer filtered by `jsonPayload.event` and `jsonPayload.request_id`.

---

## Integration Points

### New vs Modified Components

| Component | Type | Action for Diagnostics |
|-----------|------|------------------------|
| `src/feedops/api/main.py` | EXISTING | Minor: add `generation_path` field to existing `log_event()` calls (non-breaking) |
| `src/feedops/pipeline/feature_flags.py` | EXISTING | Read-only audit only; no changes in diagnostic phase |
| `src/feedops/pipeline/generator.py` | EXISTING | No changes for diagnostics |
| `dashboard/src/lib/regeneration/core.ts` | EXISTING | No changes (not on primary path) |
| `dashboard/src/lib/publishing/google-sheets.ts` | EXISTING | Read-only use in Step 4 propagation check |
| `supabase/migrations/` | EXISTING | New migration for `generation_path` + `flag_snapshot` in `regeneration_history` — ONLY after root cause confirmed |
| `src/feedops/diagnostics/coverage_queries.py` | NEW | Phase 1 (optional CLI wrapper if preferred over direct SQL) |
| `dashboard/src/app/api/diagnostics/coverage/route.ts` | NEW | Phase 1 (if dashboard display needed) |
| `src/feedops/api/diagnostics.py` | NEW | Phase 2+ Cloud Run router for live flag state |

### External Service Integration for Diagnostics

| Service | Diagnostic Use | Already Integrated |
|---------|----------------|-------------------|
| Supabase | Coverage queries, regeneration_history reads | YES |
| Cloud Run logs | Path tracing via structured log fields | YES (read via `gcloud run services logs read`) |
| Google Sheets API | Propagation verification (Step 4) | YES (via `google-sheets.ts`) |
| Prometheus `/metrics` | In-process metrics (not for historical analysis) | YES |

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current diagnostic phase | Direct Supabase queries for coverage are fast (<1s). No caching needed for one-off runs. |
| Instrumentation additions | Adding `generation_path` + `flag_snapshot` JSON column to `regeneration_history` — minimal write overhead per regeneration. |
| Propagation checks | 10-50 SKUs via Sheets API. Rate limit: 300 req/min (well within bounds). One-time check. |
| After coverage fix (1,000+ published SKUs) | `performance_impact_scores` query already handles 10,000+ rows via existing index. No changes needed. |

---

## Sources

- Direct code inspection: `src/feedops/api/main.py` (generation paths A and B confirmed, Path A does not invoke generator.py)
- Direct code inspection: `src/feedops/pipeline/generator.py` (Path B; segment_strategy_v1 called here only)
- Direct code inspection: `src/feedops/pipeline/feature_flags.py` (flag definitions, defaults all True, call sites not found for PROMPT_CONTRACT_V2/INTENT_CURATOR_V1)
- Direct code inspection: `src/feedops/api/runtime_controls.py` (kill switches — separate system from feature_flags.py)
- Direct code inspection: `src/feedops/observability/__init__.py` (structured log format, request_id context via contextvars)
- Direct code inspection: `src/feedops/observability/metrics.py` (in-memory only, resets on container restart)
- Direct code inspection: `dashboard/src/app/api/regenerate/route.ts` (thin proxy confirmed; contains validation + DB writes but all generation delegated to Python)
- Direct code inspection: `dashboard/src/lib/regeneration/core.ts` (legacy path; called only from /api/regenerate/batch, NOT from /api/regenerate)
- Direct code inspection: `dashboard/src/app/api/monitoring/performance-delta/route.ts` (reads from `performance_impact_scores` table)
- `.planning/PROJECT.md` (v1.2 milestone goals and current state)
- `docs/database/SCHEMA.md` (32 tables, column names, constraints)

---

*Architecture research for: Allied FeedOps v1.2 — diagnostic layer for impact debugging*
*Researched: 2026-02-20*
