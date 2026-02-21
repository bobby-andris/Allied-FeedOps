# Phase 19: Measurement Infrastructure - Research

**Researched:** 2026-02-21
**Domain:** Instrumentation, GMC Merchant API, prompt lineage tracking, bottleneck classification
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**GMC Disapproval Surfacing**
- Dedicated monitoring page under /monitoring for full disapproval list + inline badges on existing pages (SKU review, overview, performance)
- Inline badges show icon + count (e.g., warning icon with number of issues per SKU)
- Scheduled sync — daily/periodic job stores GMC status in Supabase, enabling fast page loads and trend tracking over time
- Issue detail level: Claude's discretion based on what Merchant API provides

**Bottleneck Classifier Output**
- Both color-coded tags inline on SKU tables + dedicated diagnostic view grouping SKUs by bottleneck type
- Five categories: code-path gap, auction/bid, query relevance, coverage gap, propagation failure
- Manual override supported — user can change classification with a note when they know something the system doesn't
- Auto-run after publish + manual re-run button for reclassifying existing SKUs
- Evidence display: Claude's discretion based on existing dashboard UI patterns

**Flag & Prompt Lineage Visibility**
- UI visibility level: Claude's discretion (likely collapsible technical details to avoid clutter)
- Opt-in side-by-side comparison — ability to compare two generations by prompt version, but NOT default view; user must explicitly request it
- Both hash + named versions — auto-generated hash for accuracy, optional human-readable alias (e.g., v2.1) for important versions
- Filtering by flag state supports both A/B analysis (segment performance by flag ON/OFF) and debugging (find generations with specific flag combos)

**Data Capture Granularity**
- Full prompt text vs hash-only: Claude's discretion (assess storage vs debugging value)
- Raw model response storage: Claude's discretion (assess debugging value vs storage)
- Retention policy: Claude's discretion (expected volume ~2,784 SKUs with occasional regeneration — likely keep everything)
- Track generation costs — record tokens used, model name, and latency per generation for cost analysis and model comparison

### Claude's Discretion
- GMC issue detail level (based on Merchant API data available)
- Bottleneck evidence display format (expandable row vs detail panel — match existing patterns)
- Flag/prompt lineage UI placement (likely collapsible section)
- Full prompt text vs hash-only storage
- Raw model response storage
- Data retention policy

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MEAS-01 | Each content generation records which feature flags were active at generation time (feature_flags_active field in regeneration_history) | Schema extension to regeneration_history; flag snapshot captured in Python pipeline at generation time |
| MEAS-02 | GMC disapproval visibility — system can query Merchant API to identify disapproved/not-serving products and surface issues | Merchant API product_view + item_issues via Reports API; scheduled sync to new gmc_product_status table; badges on existing pages |
| MEAS-03 | Prompt hash lineage tracking connects generated content to the exact prompt version that produced it | prompt_hash already exists in regeneration_history and publish_events; need prompt_version_aliases table + UI display in SKU review |
| MEAS-04 | Bottleneck classifier categorizes impact issues as code-path, auction/bid, query relevance, coverage gap, or propagation failure — with evidence | New classification logic (TypeScript API route or Python endpoint) reads existing signals; new sku_bottleneck_classifications table; inline tags + grouped diagnostic view |
</phase_requirements>

---

## Summary

Phase 19 is an instrumentation and UI phase that adds four measurement layers to the existing system. All four requirements have clear implementation paths because the data signals already exist in Supabase — the phase is primarily about capturing snapshots at the right time, surfacing GMC status from an external API, and building UI to make the data queryable and visible.

**MEAS-01 (Feature flag capture)** is the simplest work item. The Python pipeline already has `feature_flags.py` with three flag functions, and `_persist_generated_content_and_history()` in `main.py` already writes to `regeneration_history`. Adding a `feature_flags_active` JSONB column and populating it during that same write path requires a migration, two lines of Python, and no schema redesign.

**MEAS-02 (GMC disapproval)** requires the most new code: a Python script/endpoint to call the Merchant API `product_view` Reports query, a new `gmc_product_status` Supabase table to cache results, a GCP Cloud Scheduler trigger for daily sync, and badge components on three existing pages. The Merchant API query pattern is well-documented and straightforward. The critical unknown is the GMC Merchant Center account ID (confirmed in STATE.md as a blocker — not the same as Google Ads ID 6253381786).

**MEAS-03 (Prompt lineage)** is mostly done. `regeneration_history.prompt_hash` already exists. `publish_events.prompt_hash` was added in migration `034_add_publish_lineage_hashes.sql`. The gap is: (1) a `prompt_version_aliases` table to map hash → human-readable alias, and (2) UI in the SKU review page showing which prompt version produced live content, with an opt-in comparison view.

**MEAS-04 (Bottleneck classifier)** is the most intellectually complex but structurally straightforward. The classifier reads from signals already in Supabase (performance_baselines, performance_snapshots, keyword_coverage_master, publish_events, search_queries) and applies a decision tree to produce one of five labels. A new `sku_bottleneck_classifications` table stores the result with evidence JSON. The planner should decide whether this lives as a TypeScript API route (simpler, dashboard-only) or a Python endpoint (callable from Cloud Run pipeline as well).

**Primary recommendation:** Implement in dependency order: MEAS-01 (2 hrs) → MEAS-03 migration + UI (4 hrs) → MEAS-04 classifier + schema + UI (8 hrs) → MEAS-02 GMC sync + cache + badges (6 hrs). Total estimated: ~20 development hours. The GMC work should be sequenced last because the account ID blocker must be resolved first.

---

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---|---|---|---|
| Supabase JS client | existing | DB reads/writes from dashboard | Already in use everywhere |
| Python `google.cloud.bigquery` or Merchant API REST | Merchant API v1 | GMC product_view disapproval query | Official Merchant Center API |
| `hashlib.sha256` (Python stdlib) | stdlib | Prompt hashing | Already used in `get_system_prompt_hash()` |
| Next.js API routes | existing | TypeScript endpoints for classifier, lineage API | Established pattern in this project |
| Supabase migrations (.sql) | existing | Schema changes | Established pattern — 034+ already in use |
| `lucide-react` | existing | Icons for warning badges | Already imported in dashboard |
| `shadcn/ui Badge` | existing | Status badges | Already used on monitoring page and review list |

### Supporting
| Library | Version | Purpose | When to Use |
|---|---|---|---|
| GCP Cloud Scheduler | managed | Daily GMC sync trigger | Production automation (calls existing Cloud Run endpoint) |
| Python `google.auth` | existing | Merchant API auth | Same service account used for Google Ads |
| Python `requests` or `httpx` | existing in pipeline | REST calls to Merchant API | If not using Python client library |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|---|---|---|
| New gmc_product_status table | Re-query Merchant API on each page load | On-demand is slow (~2-5s), breaks scheduled trend tracking requirement |
| TypeScript classifier | Python classifier in Cloud Run | TypeScript is simpler (no deployment) but Python has better access to all data signals; TypeScript is fine for Phase 19 |
| Hash + alias table | Timestamp-based versioning | Hash-only is cryptographically sound; aliases add human readability without replacing the hash |

---

## Architecture Patterns

### Recommended Project Structure

```
# Python pipeline additions
src/feedops/
├── api/
│   └── gmc_sync.py          # GMC disapproval sync endpoint + Router
├── pipeline/
│   └── bottleneck.py        # Bottleneck classifier logic (optional - see note)
└── integrations/
    └── merchant_api.py      # Merchant API client wrapper

# Dashboard additions
dashboard/src/app/
├── api/
│   ├── gmc/
│   │   └── sync/route.ts    # POST trigger for GMC sync (calls Cloud Run)
│   │   └── status/route.ts  # GET: read gmc_product_status table
│   └── bottleneck/
│       └── classify/route.ts # POST: run classifier for SKU(s)
│       └── status/route.ts   # GET: read sku_bottleneck_classifications
│   └── prompt-lineage/
│       └── route.ts          # GET: lineage for a SKU's current content
├── (dashboard)/
│   └── monitoring/
│       └── page.tsx          # EXTEND: add GMC Disapprovals tab (currently 2 tabs)
│       └── bottleneck/
│           └── page.tsx      # NEW: grouped bottleneck diagnostic view

# Supabase migrations
supabase/migrations/
├── 035_gmc_product_status.sql           # gmc_product_status cache table
├── 035_feature_flags_active.sql         # Add feature_flags_active to regeneration_history
├── 035_prompt_version_aliases.sql       # prompt_version_aliases lookup table
└── 035_sku_bottleneck_classifications.sql # Bottleneck results table
```

### Pattern 1: Feature Flag Snapshot at Generation Time

**What:** Capture all three flag states as a JSONB snapshot at the exact moment content is generated.
**When to use:** Every call to `_persist_generated_content_and_history()` and the inline `regeneration_history` insert in `regenerate_content()`.

**Schema change:**
```sql
-- Migration 035_feature_flags_active.sql
ALTER TABLE regeneration_history
  ADD COLUMN IF NOT EXISTS feature_flags_active JSONB,
  ADD COLUMN IF NOT EXISTS tokens_used INTEGER,
  ADD COLUMN IF NOT EXISTS latency_ms INTEGER;

-- Optional: add cost tracking requested in context
ALTER TABLE regeneration_history
  ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,6);

CREATE INDEX IF NOT EXISTS idx_regen_history_flags
  ON regeneration_history USING GIN (feature_flags_active);
```

**Python code (in `_persist_generated_content_and_history` and `regenerate_content`):**
```python
# Source: src/feedops/pipeline/feature_flags.py (existing)
from feedops.pipeline.feature_flags import (
    is_prompt_contract_v2_enabled,
    is_intent_curator_v1_enabled,
    is_segment_strategy_v1_enabled,
)

def _capture_flag_snapshot() -> dict:
    return {
        "PROMPT_CONTRACT_V2": is_prompt_contract_v2_enabled(),
        "INTENT_CURATOR_V1": is_intent_curator_v1_enabled(),
        "SEGMENT_STRATEGY_V1": is_segment_strategy_v1_enabled(),
    }

# Add to history_payload dict:
history_payload["feature_flags_active"] = _capture_flag_snapshot()
history_payload["tokens_used"] = usage.get("total_tokens")  # from provider response
history_payload["latency_ms"] = int(latency_seconds * 1000)
```

**Key insight:** All three flags read from env vars with `default=True`. The snapshot must be captured at call time (not at import time) because env vars can theoretically change between requests.

### Pattern 2: GMC Disapproval Sync (Scheduled + Cached)

**What:** Python Cloud Run endpoint queries Merchant API `product_view`, stores disapprovals in Supabase, triggered daily by GCP Cloud Scheduler.
**When to use:** Called on schedule (daily) and manually from dashboard. Dashboard reads the Supabase cache — never calls Merchant API directly.

**Merchant API query (verified from official docs):**
```python
# Source: https://developers.google.com/api/guides/reports/evaluate-products.html
# Query for product_view to get disapproved/not-eligible products with item issues

query = """
SELECT id, offer_id, title, aggregated_reporting_context_status, item_issues
FROM product_view
WHERE aggregated_reporting_context_status = 'NOT_ELIGIBLE_OR_DISAPPROVED'
"""
# Also consider ELIGIBLE_LIMITED for partial disapprovals
query_limited = """
SELECT id, offer_id, title, aggregated_reporting_context_status, item_issues
FROM product_view
WHERE aggregated_reporting_context_status IN ('NOT_ELIGIBLE_OR_DISAPPROVED', 'ELIGIBLE_LIMITED')
"""
```

**Item issue fields available (from Merchant API official docs):**
- `type.code` — error code (e.g., `invalid_gtin`, `apparel_missing_brand`)
- `type.canonicalAttribute` — attribute name (e.g., `n:brand`)
- `severity.aggregatedSeverity` — `DISAPPROVED` or `DEMOTED`
- `severity.severityPerReportingContext[].reportingContext` — `SHOPPING_ADS`, `FREE_LISTINGS`
- `severity.severityPerReportingContext[].disapprovedCountries` — list of ISO 3166-1 alpha-2 codes
- `resolution` — `MERCHANT_ACTION` or `PENDING_PROCESSING`

**gmc_product_status schema:**
```sql
-- Migration 035_gmc_product_status.sql
CREATE TABLE IF NOT EXISTS gmc_product_status (
  id             BIGSERIAL PRIMARY KEY,
  gmc_offer_id   TEXT NOT NULL,           -- matches variant_index.gmc_offer_id (lowercase)
  master_sku     TEXT,                    -- denormalized from variant_index
  offer_title    TEXT,
  status         TEXT NOT NULL,           -- 'NOT_ELIGIBLE_OR_DISAPPROVED' | 'ELIGIBLE_LIMITED' | 'ELIGIBLE' | 'PENDING'
  item_issues    JSONB,                   -- full array of ItemIssue objects
  issue_count    INTEGER DEFAULT 0,       -- count for badge display
  disapproval_count INTEGER DEFAULT 0,   -- count of DISAPPROVED severity issues
  synced_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  sync_job_id    UUID                     -- FK to a new gmc_sync_jobs table
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gmc_product_status_offer_id
  ON gmc_product_status (gmc_offer_id);
CREATE INDEX IF NOT EXISTS idx_gmc_product_status_master_sku
  ON gmc_product_status (master_sku);
CREATE INDEX IF NOT EXISTS idx_gmc_product_status_status
  ON gmc_product_status (status);
CREATE INDEX IF NOT EXISTS idx_gmc_product_status_synced_at
  ON gmc_product_status (synced_at DESC);
```

**Offer ID mapping:** Merchant API returns `offer_id` in the format `shopify_US_{product_id}_{variant_id}` (uppercase US). Database stores lowercase. Join must use `LOWER(gmc_offer_id)`. The sync job should normalize to lowercase when writing to `gmc_product_status`.

**Badge API pattern (TypeScript):**
```typescript
// GET /api/gmc/status?master_sku=WP-2/16-GAL
// Returns: { issue_count, disapproval_count, issues: [...], last_synced }
const { data } = await supabase
  .from('gmc_product_status')
  .select('issue_count, disapproval_count, item_issues, synced_at')
  .eq('master_sku', masterSku)
  .order('synced_at', { ascending: false })
  .limit(1)
```

### Pattern 3: Prompt Version Lineage

**What:** Map prompt_hash → human alias, and show which prompt produced the live content for a SKU.
**When to use:** SKU review page (collapsible section), prompt lineage query for any published SKU.

**Key discovery:** `regeneration_history.prompt_hash` already exists. `publish_events.prompt_hash` already exists (added in migration 034). The gap is only:
1. A table to store optional human-readable aliases
2. UI to surface this data

```sql
-- Migration 035_prompt_version_aliases.sql
CREATE TABLE IF NOT EXISTS prompt_version_aliases (
  id          BIGSERIAL PRIMARY KEY,
  prompt_hash TEXT NOT NULL UNIQUE,     -- SHA-256 hash
  alias       TEXT,                     -- e.g., 'v2.1', 'post-shopping-intelligence'
  notes       TEXT,                     -- description of what changed
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by  TEXT
);

CREATE INDEX IF NOT EXISTS idx_prompt_version_aliases_hash
  ON prompt_version_aliases (prompt_hash);
```

**Lineage query for a published SKU:**
```sql
-- Get prompt lineage for a published SKU's current live content
SELECT
    pe.master_sku,
    pe.platform,
    pe.published_at,
    pe.prompt_hash AS publish_prompt_hash,
    pva.alias AS prompt_version_alias,
    pva.notes AS prompt_version_notes,
    rh.feature_flags_active,
    rh.model_version,
    rh.created_at AS generated_at
FROM publish_events pe
LEFT JOIN prompt_version_aliases pva ON pe.prompt_hash = pva.prompt_hash
LEFT JOIN regeneration_history rh
    ON rh.master_sku = pe.master_sku
    AND rh.platform = pe.platform
    AND rh.prompt_hash = pe.prompt_hash
WHERE pe.master_sku = 'WP-2/16-GAL'
    AND pe.status = 'success'
ORDER BY pe.published_at DESC
LIMIT 1;
```

**Side-by-side comparison query:**
```sql
-- Compare two generations for same SKU by prompt hash
SELECT
    rh.created_at,
    rh.prompt_hash,
    pva.alias,
    rh.new_content,
    rh.model_version,
    rh.feature_flags_active,
    rh.quality_score_after
FROM regeneration_history rh
LEFT JOIN prompt_version_aliases pva ON rh.prompt_hash = pva.prompt_hash
WHERE rh.master_sku = 'WP-2/16-GAL'
    AND rh.platform = 'google'
    AND rh.prompt_hash IN ('hash_a', 'hash_b')
ORDER BY rh.created_at DESC;
```

### Pattern 4: Bottleneck Classifier

**What:** Decision tree reading existing Supabase signals to assign one of five labels per SKU.
**When to use:** After publish (auto-run), manual re-run button in dashboard.

**Five categories and their detection signals (all from existing tables):**

| Category | Label | Key Signal Query |
|---|---|---|
| Code-path gap | `code_path_gap` | `generated_content` has content but `publish_events` has no success row → content never published |
| Auction/bid | `auction_bid` | `performance_baselines.avg_impressions > 0` AND `performance_snapshots` shows IS loss to rank > 30% (from search_queries competition_index) |
| Query relevance | `query_relevance` | `keyword_coverage_master.in_title = false` for queries with `query_volume > 100`; OR high impressions / 0% CTR in search_queries |
| Coverage gap | `coverage_gap` | No `generated_content` row exists OR no `publish_events` success row |
| Propagation failure | `propagation_failure` | `publish_events` success exists BUT baseline/snapshot shows zero impressions post-publish (content not reaching GMC) |

**sku_bottleneck_classifications schema:**
```sql
-- Migration 035_sku_bottleneck_classifications.sql
CREATE TABLE IF NOT EXISTS sku_bottleneck_classifications (
  id                BIGSERIAL PRIMARY KEY,
  master_sku        TEXT NOT NULL,
  classification    TEXT NOT NULL,  -- 'code_path_gap' | 'auction_bid' | 'query_relevance' | 'coverage_gap' | 'propagation_failure'
  confidence        NUMERIC(4,2),   -- 0.0-1.0
  evidence          JSONB,          -- supporting data points used in classification
  override_by       TEXT,           -- user who manually overrode
  override_note     TEXT,           -- reason for manual override
  is_override       BOOLEAN DEFAULT false,
  classified_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  publish_event_id  BIGINT          -- which publish event triggered classification
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sku_bottleneck_master_sku
  ON sku_bottleneck_classifications (master_sku)
  WHERE is_override = false;  -- only one active auto-classification per SKU

CREATE INDEX IF NOT EXISTS idx_sku_bottleneck_classification
  ON sku_bottleneck_classifications (classification);
CREATE INDEX IF NOT EXISTS idx_sku_bottleneck_classified_at
  ON sku_bottleneck_classifications (classified_at DESC);
```

**Decision tree logic (TypeScript, runs as API route):**
```typescript
// POST /api/bottleneck/classify?master_sku=WP-2/16-GAL
// Reads signals → assigns label → upserts to sku_bottleneck_classifications

async function classifySku(masterSku: string, supabase: SupabaseClient) {
  // 1. Check coverage gap first (no content at all)
  const { data: content } = await supabase
    .from('generated_content')
    .select('id')
    .eq('master_sku', masterSku)
    .limit(1)
  if (!content?.length) return { label: 'coverage_gap', confidence: 0.95 }

  // 2. Check code-path gap (content exists, never published)
  const { data: publishEvent } = await supabase
    .from('publish_events')
    .select('id')
    .eq('master_sku', masterSku)
    .eq('status', 'success')
    .limit(1)
  if (!publishEvent?.length) return { label: 'code_path_gap', confidence: 0.90 }

  // 3. Check propagation failure (published, but impressions still zero post-publish)
  const { data: snapshot } = await supabase
    .from('performance_snapshots')
    .select('impressions')
    .eq('master_sku', masterSku)
    .gt('days_since_publish', 7)  // give it a week
    .order('snapshot_date', { ascending: false })
    .limit(1)
  if (snapshot?.length && snapshot[0].impressions === 0) {
    return { label: 'propagation_failure', confidence: 0.85 }
  }

  // 4. Check query relevance (impressions but near-zero CTR)
  const { data: queries } = await supabase
    .from('keyword_coverage_master')
    .select('keyword, in_title, query_volume')
    .eq('master_sku', masterSku)
    .eq('in_title', false)
    .gt('query_volume', 100)
  if (queries?.length > 2) return { label: 'query_relevance', confidence: 0.75 }

  // 5. Default: auction/bid (impressions exist, IS lost to rank)
  return { label: 'auction_bid', confidence: 0.60 }
}
```

**Color coding for badges (Tailwind):**
```typescript
const BOTTLENECK_COLORS = {
  coverage_gap: 'bg-gray-100 text-gray-800',
  code_path_gap: 'bg-purple-100 text-purple-800',
  query_relevance: 'bg-yellow-100 text-yellow-800',
  propagation_failure: 'bg-orange-100 text-orange-800',
  auction_bid: 'bg-blue-100 text-blue-800',
}
```

### Anti-Patterns to Avoid

- **Calling Merchant API on every page load:** Always read from the `gmc_product_status` cache table. Merchant API has rate limits and 30+ minute data delay anyway.
- **Storing full prompt text in regeneration_history by default:** The hash is already sufficient for lineage; full prompt text can optionally be stored but truncated to 5000 chars (already done for system_prompt and user_prompt). The hash is the identity.
- **Calculating bottleneck classification on every review page load:** Classify on-demand (post-publish trigger or manual button) and cache in `sku_bottleneck_classifications`. The review list reads from this table, it does not recalculate.
- **Relying on GCP Cloud Scheduler for mission-critical path:** Scheduler is fine for GMC sync (non-critical, just cache refresh). It is NOT suitable for blocking user-facing flows.
- **Unique constraint on sku_bottleneck_classifications without partial index:** If multiple rows can exist (history of classifications), use a separate "current" flag or `is_override` partial unique index pattern (see schema above).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Prompt hashing | Custom hash function | `hashlib.sha256` + `get_system_prompt_hash()` already in `prompt_loader.py` | Already implemented |
| Merchant API auth | OAuth token management | Reuse `google.auth` credentials already used for Google Ads | Same service account |
| Supabase upsert on GMC sync | Manual INSERT + UPDATE logic | `.upsert()` with `on_conflict='gmc_offer_id'` | Prevents race conditions |
| Badge count API | New endpoint per page | Single `/api/gmc/status?master_sku=X` read from cache | Cache already has `issue_count` |
| Classification UI state | Custom state management | `useState` + Supabase query on mount | Same as other dashboard pages |

**Key insight:** All four requirements have existing data signals. This phase is about connecting existing dots (flag values, prompt hashes, performance signals) and caching the results for fast UI display. Avoid recalculating expensive signals on page load.

---

## Common Pitfalls

### Pitfall 1: GMC Merchant Center Account ID
**What goes wrong:** Merchant API calls fail or return no data because the wrong account ID is used.
**Why it happens:** GMC Merchant Center ID is NOT the same as Google Ads customer ID (6253381786). This was confirmed as a blocker in Phase 17-01. The MC ID must be provided separately.
**How to avoid:** Before implementing GMC sync, confirm the MC account ID. This should be stored as a GCP secret (`feedops-merchant-center-id`) and loaded at runtime.
**Warning signs:** Merchant API returns 404 or empty results despite products existing in GMC.

### Pitfall 2: Offer ID Case Mismatch in GMC Sync
**What goes wrong:** GMC returns `shopify_US_...` (uppercase) but Supabase stores `shopify_us_...` (lowercase). Join fails silently, resulting in `master_sku = NULL` for all synced rows.
**Why it happens:** This is a known project pattern documented in CLAUDE.md and SCHEMA.md.
**How to avoid:** Normalize to lowercase when writing to `gmc_product_status`: `offer_id.lower()`. Join with `LOWER()` on both sides when looking up `master_sku` from `variant_index`.
**Warning signs:** `gmc_product_status.master_sku` is NULL for all rows despite having matching offer IDs.

### Pitfall 3: Feature Flags Captured at Import Time
**What goes wrong:** Flag values are captured once at module import, not at generation time. All history rows show the same values regardless of when generation happened.
**Why it happens:** Easy to write `FLAGS = { "PROMPT_CONTRACT_V2": is_prompt_contract_v2_enabled() }` at module level.
**How to avoid:** Call `_capture_flag_snapshot()` inside `_persist_generated_content_and_history()`, not at module import. This ensures each generation captures the actual runtime state.
**Warning signs:** All `feature_flags_active` rows show identical values across different time periods.

### Pitfall 4: Bottleneck Classification Missing Null Guards
**What goes wrong:** SKUs with no performance_baselines or no keyword_coverage rows cause uncaught exceptions or misclassifications.
**Why it happens:** Coverage is sparse — only 79/2,784 SKUs have generated content. Most SKUs will have empty result sets from multiple queries.
**How to avoid:** Every signal check must handle null/empty results gracefully. Default to `coverage_gap` when data is missing rather than failing.
**Warning signs:** Classification API route returns 500 for most SKUs.

### Pitfall 5: Monitoring Page Tab Collision
**What goes wrong:** Adding GMC Disapprovals as a new tab to `/monitoring/page.tsx` breaks the existing Performance Deltas and Search Query Changes tabs.
**Why it happens:** The existing page uses `Tabs` with `grid-cols-2` for the tab list. Adding a third tab requires changing the grid layout.
**How to avoid:** Change `grid-cols-2` to `grid-cols-3` when adding the GMC tab. Alternatively, create `/monitoring/gmc` as a sub-route to keep the monitoring page clean.
**Warning signs:** Tabs overflow or layout breaks on the monitoring page after adding the new tab.

### Pitfall 6: Prompt Hash Null in Publish Events
**What goes wrong:** `publish_events.prompt_hash` is NULL for most published SKUs because the lineage hash was added retroactively in migration 034.
**Why it happens:** The migration only adds the column schema; historical rows are not backfilled.
**How to avoid:** The lineage UI must handle NULL prompt_hash gracefully (show "hash not recorded" rather than erroring). Document that lineage tracking is complete only for SKUs published after Phase 19 ships.
**Warning signs:** Lineage panel shows blank or errors for all existing published SKUs.

---

## Code Examples

### MEAS-01: Adding Feature Flags to `_persist_generated_content_and_history`

```python
# Source: src/feedops/api/main.py (existing function to extend)
def _persist_generated_content_and_history(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
    content: str,
    generation_model: str,
    prompt_hash: str,
    system_prompt: str,
    user_prompt: str,
    mode: str,
    tokens_used: int | None = None,      # NEW
    latency_ms: int | None = None,        # NEW
):
    # ... existing upsert to generated_content ...

    history_payload = {
        "master_sku": master_sku,
        "content_type": content_type,
        "platform": platform,
        "mode": mode,
        "new_content": content,
        "model_version": generation_model,
        "system_prompt": system_prompt[:5000],
        "user_prompt": user_prompt[:5000],
        "prompt_hash": prompt_hash,
        "generated_content_id": generated_content_id,
        # NEW fields:
        "feature_flags_active": {
            "PROMPT_CONTRACT_V2": is_prompt_contract_v2_enabled(),
            "INTENT_CURATOR_V1": is_intent_curator_v1_enabled(),
            "SEGMENT_STRATEGY_V1": is_segment_strategy_v1_enabled(),
        },
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    supabase.table("regeneration_history").insert(history_payload).execute()
```

### MEAS-02: Merchant API Query for Disapprovals

```python
# Source pattern: https://developers.google.com/api/guides/reports/evaluate-products.html
# To implement in src/feedops/api/gmc_sync.py

async def sync_gmc_disapprovals(merchant_center_id: str, supabase) -> dict:
    """Query Merchant API for disapproved products and cache in Supabase."""
    # Uses Google Merchant Reports API v1
    # Endpoint: POST https://merchantapi.googleapis.com/reports/v1/accounts/{ACCOUNT_ID}/reports:search

    query = """
    SELECT id, offer_id, title, aggregated_reporting_context_status, item_issues
    FROM product_view
    WHERE aggregated_reporting_context_status IN ('NOT_ELIGIBLE_OR_DISAPPROVED', 'ELIGIBLE_LIMITED')
    """

    # Use existing google.auth credentials (same SA as Google Ads)
    # Make REST call or use google-shopping-merchant-reports Python client
    # Parse results and normalize offer_id to lowercase
    # Upsert to gmc_product_status with on_conflict='gmc_offer_id'
    # Return { synced_count, disapproved_count, limited_count }
```

### MEAS-03: Prompt Lineage API Route

```typescript
// dashboard/src/app/api/prompt-lineage/route.ts
// GET /api/prompt-lineage?master_sku=WP-2/16-GAL&platform=google

export async function GET(request: NextRequest) {
  const supabase = await createClient()
  const masterSku = searchParams.get('master_sku')
  const platform = searchParams.get('platform') || 'google'

  // Get latest publish event with prompt hash
  const { data: publishEvent } = await supabase
    .from('publish_events')
    .select('id, published_at, prompt_hash, content_version')
    .eq('master_sku', masterSku)
    .eq('platform', platform)
    .eq('status', 'success')
    .order('published_at', { ascending: false })
    .limit(1)
    .single()

  if (!publishEvent?.prompt_hash) {
    return NextResponse.json({ lineage: null, note: 'Hash not recorded for this publish event' })
  }

  // Get alias if exists
  const { data: alias } = await supabase
    .from('prompt_version_aliases')
    .select('alias, notes')
    .eq('prompt_hash', publishEvent.prompt_hash)
    .single()

  // Get generation history for this prompt hash
  const { data: history } = await supabase
    .from('regeneration_history')
    .select('created_at, model_version, feature_flags_active, quality_score_after, tokens_used')
    .eq('master_sku', masterSku)
    .eq('platform', platform)
    .eq('prompt_hash', publishEvent.prompt_hash)
    .order('created_at', { ascending: false })
    .limit(1)
    .single()

  return NextResponse.json({
    publish_event_id: publishEvent.id,
    published_at: publishEvent.published_at,
    prompt_hash: publishEvent.prompt_hash,
    prompt_alias: alias?.alias ?? null,
    prompt_notes: alias?.notes ?? null,
    generation: history ?? null,
  })
}
```

### MEAS-04: GMC Badge Component

```typescript
// Reusable badge for SKU tables (icon + count pattern from CONTEXT.md)
// dashboard/src/components/gmc/GmcDisapprovalBadge.tsx

import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface Props {
  masterSku: string
  issueCount: number
  disapprovalCount: number
}

export function GmcDisapprovalBadge({ masterSku, issueCount, disapprovalCount }: Props) {
  if (issueCount === 0) return null

  return (
    <Badge
      className={
        disapprovalCount > 0
          ? 'bg-red-100 text-red-800'
          : 'bg-yellow-100 text-yellow-800'
      }
      title={`${disapprovalCount} disapprovals, ${issueCount - disapprovalCount} warnings`}
    >
      <AlertTriangle className="h-3 w-3 mr-1" />
      {issueCount}
    </Badge>
  )
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Merchant Content API (Content API for Shopping) | Merchant API (new Merchant Center REST API) | GA in 2025, Content API deprecated Aug 2026 | Use Merchant API for disapproval queries — Content API still works for product writes until Aug 2026 |
| Manual prompt audit | Hash-based lineage with `prompt_hash` in regeneration_history | Already in schema | Phase 19 just adds aliases and UI surface |
| No flag tracking | Feature flags default-True in feature_flags.py | Phase 18 confirmed | Phase 19 adds recording at generation time |

**Deprecated/outdated:**
- Content API for Shopping (legacy): Still works until Aug 2026 for product data writes, but use Merchant API for diagnostic/read queries (disapprovals, product status). This aligns with the project's stated approach in REQUIREMENTS.md.

---

## Open Questions

1. **GMC Merchant Center Account ID**
   - What we know: Confirmed in Phase 17-01 that MC ID != Google Ads ID (6253381786). The MC ID is required for all Merchant API calls.
   - What's unclear: The actual MC account ID value. It may be visible in the Merchant Center UI or already stored somewhere.
   - Recommendation: User must provide MC account ID before MEAS-02 can be implemented. Store as `FEEDOPS_MERCHANT_CENTER_ID` env var in Cloud Run secrets. This is a prerequisite for any GMC sync work — plan accordingly by implementing MEAS-01, MEAS-03, MEAS-04 first.

2. **Provider token/cost data availability**
   - What we know: CONTEXT.md says track tokens + model + latency. Python provider's `generate()` returns content.
   - What's unclear: Does the current `LLMProvider.generate()` return usage metadata (token counts) from the OpenAI response?
   - Recommendation: Check `src/feedops/providers/base.py` and the OpenAI provider implementation. If usage is available in the response object, capture it. If not, add a `usage` field to the provider return type. This is low-risk but needs to be verified before coding the MEAS-01 tokens_used field.

3. **Bottleneck classifier: TypeScript vs Python**
   - What we know: Context says "bottleneck classifier categorizes each SKU with published content." Phase 20 (FIX-01, FIX-02) will need to re-run the classifier as fixes are applied.
   - What's unclear: Should the classifier be callable from Cloud Run (Python) for auto-run after batch publishes, or is TypeScript (dashboard-only) sufficient for Phase 19?
   - Recommendation: Implement in TypeScript for Phase 19 (faster, no deployment). Design the logic as a pure function with clear inputs so it can be ported to Python in Phase 20 if needed. Auto-run on publish can call the TypeScript API route from the publish flow.

4. **Monitoring page layout: extend vs separate route**
   - What we know: `/monitoring/page.tsx` currently has 2 tabs (Performance Deltas, Search Query Changes). CONTEXT.md says "dedicated monitoring page under /monitoring for full disapproval list."
   - What's unclear: Should GMC disapprovals be a third tab on the existing `/monitoring` page, or a separate sub-route `/monitoring/gmc`?
   - Recommendation: Add as a third tab on the existing `/monitoring` page (change grid-cols-2 to grid-cols-3). The bottleneck diagnostic view should be a separate sub-page `/monitoring/bottleneck` to keep each view focused.

---

## Sources

### Primary (HIGH confidence)
- `src/feedops/pipeline/feature_flags.py` — verified three flag functions, all default True
- `src/feedops/api/main.py` lines 578-623 — verified `_persist_generated_content_and_history()` writes to `regeneration_history`; exact payload structure confirmed
- `docs/database/SCHEMA.md` — verified `regeneration_history` columns including `prompt_hash`, `model_version`, `system_prompt`, `user_prompt`
- `supabase/migrations/034_add_publish_lineage_hashes.sql` — verified `publish_events.prompt_hash` exists already
- Merchant API official docs (via mcp__merchant-api-devdocs): `product_view` table, `item_issues` structure, `aggregated_reporting_context_status` filter, `accounts.reports.search` endpoint — HIGH confidence, official source
- `dashboard/src/app/(dashboard)/monitoring/page.tsx` — verified existing tab structure, component patterns, Badge/Alert usage

### Secondary (MEDIUM confidence)
- Merchant API `product_view` fields: `offer_id`, `id`, `title`, `aggregated_reporting_context_status`, `item_issues` — verified via mcp__merchant-api-devdocs query results showing official doc content
- Offer ID normalization pattern (lowercase in DB, uppercase from GMC) — documented in CLAUDE.md and SCHEMA.md, HIGH confidence

### Tertiary (LOW confidence)
- Provider token/usage metadata availability — not verified; requires reading `src/feedops/providers/base.py` and `src/feedops/providers/openai.py`

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use; Merchant API verified via official docs
- Architecture patterns: HIGH — builds directly on verified existing code paths
- GMC sync: HIGH for query pattern, MEDIUM for auth (same SA pattern, not explicitly tested for Merchant API)
- Pitfalls: HIGH — offer ID case mismatch and MC account ID confirmed from Phase 17-01 findings

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (30 days — stable APIs, no fast-moving dependencies)
