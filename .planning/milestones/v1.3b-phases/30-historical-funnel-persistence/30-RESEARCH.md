# Phase 30: Historical Funnel Persistence - Research

**Researched:** 2026-02-25
**Domain:** Supabase persistence + Cloud Scheduler + Dashboard UI (trend cards)
**Confidence:** HIGH

## Summary

Phase 30 persists the ephemeral Google Ads shopping funnel data (currently live-queried with a 2-minute in-memory cache in `service.ts`) into daily Supabase snapshots. The existing `getLabelTierPerformance()` function in `service.ts` already aggregates search term data into `custom_label_0 + tier (HIGH/MEDIUM/LOW)` rows with 6 metrics (impressions, clicks, cost_micros, conversions, conversions_value, ROAS). The phase creates a `funnel_snapshots_daily` table, a Next.js API capture endpoint, a Cloud Scheduler job to trigger daily capture, and 6 trend summary cards on the Shopping Funnel page.

The technical scope is straightforward: one new Supabase table, one new API route, one new Cloud Scheduler job (following the established pattern from Phase 8), and a UI addition above existing tabs. The GAQL query is already written and proven in production -- the capture endpoint just calls `getLabelTierPerformance()` with `startDate=endDate=yesterday` and writes results to Supabase.

**Primary recommendation:** Reuse `getLabelTierPerformance()` exactly as-is for the capture path. Do NOT duplicate or modify the GAQL query logic. The capture endpoint is a thin write-behind layer on top of existing proven code.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Label-tier aggregates only -- one row per custom_label_0 + tier (HIGH/MEDIUM/LOW) per day
- ~60 rows/day x 90 days retention = ~5,400 rows max
- Store daily totals (single day's metrics), not rolling period sums -- rolling windows computed at query time
- Reuse the same GAQL query from service.ts with startDate=endDate=yesterday -- guarantees parity with live dashboard data
- Tier performance metrics only: impressions, clicks, cost_micros, conversions, conversions_value, ROAS
- No search-term-level snapshots, no needs-decision counts
- All 6 funnel metrics get trend indicators: Impressions, Clicks, CTR, Ad Spend, Conversions, ROAS
- 5% threshold: changes under 5% show as flat, over 5% shows arrow up or down
- Summary cards placed above existing tabs (Needs Decision / Existing Funnel)
- Account-wide totals across all labels and tiers -- no label filter dropdown
- 6 cards in 2 rows of 3: Row 1 = Impressions, Clicks, CTR; Row 2 = Ad Spend, Conversions, ROAS
- Trend arrows only -- no sparklines, no time-series charts, no separate history tab
- Fixed 7-day comparison window (last 7 days vs previous 7 days) -- no user-selectable window
- When insufficient historical data: show current 7-day value with muted "No prior data" instead of trend arrow
- Cards hidden entirely only if zero snapshot data exists
- New dashboard API route: /api/funnel-snapshots/capture (Next.js, leverages existing service.ts GAQL)
- Cloud Scheduler triggers at 5 AM ET daily (Google Ads data for yesterday settled by then)
- Retry 3x with backoff on failure, then skip that day -- dashboard handles gaps gracefully
- 90-day retention cleanup runs inline with each capture (DELETE WHERE snapshot_date < NOW() - 90 days)

### Claude's Discretion
- Exact table schema (column types, indexes, constraints)
- Cloud Scheduler configuration details (cron expression, HTTP target auth)
- API route authentication (service account key vs shared secret)
- Error logging format and destination
- Exact card component styling (shadows, spacing, responsive breakpoints)

### Deferred Ideas (OUT OF SCOPE)
- Per-label-tier trend breakdown (inline trends in existing funnel tables)
- Selectable comparison windows (14d, 30d)
- Sparkline charts in summary cards
- Search-term-level daily snapshots
- Alerting on significant metric changes (e.g., ROAS drops >20%)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HIST-01 | funnel_snapshots_daily table persists daily search term tier data from service.ts GAQL queries with 90-day retention policy | Table schema designed below; `getLabelTierPerformance()` in service.ts (line 1042) already produces the exact data shape. Retention via inline DELETE during capture. |
| HIST-02 | Daily capture endpoint (write-behind, non-blocking to service.ts live queries) triggered by Cloud Scheduler | New `/api/funnel-snapshots/capture` API route calls `getLabelTierPerformance({startDate: yesterday, endDate: yesterday})`, writes to Supabase. Cloud Scheduler triggers at 5 AM ET using existing OIDC pattern (but targeting Vercel, so needs shared secret auth instead). |
| HIST-03 | 7-day vs previous-7-day trend indicators displayed on Shopping Funnel dashboard page | 6 summary cards above tabs. Query aggregates last 7 days and previous 7 days from `funnel_snapshots_daily`, computes deltas, applies 5% threshold for trend arrows. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @supabase/supabase-js | existing | Database reads/writes for snapshots | Already used throughout project |
| Next.js API routes | existing | Capture endpoint | Project standard for dashboard APIs |
| google-ads-api | existing | GAQL queries (via service.ts) | Already wired and proven |
| lucide-react | existing | Trend arrow icons (TrendingUp, TrendingDown, Minus) | Already used in performance/page.tsx |
| shadcn/ui Card | existing | Summary card components | Project UI standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| GCP Cloud Scheduler | N/A | Daily cron trigger | Human-applied infrastructure, script provided |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vercel API route for capture | Cloud Run endpoint | Cloud Run would use OIDC auth (cleaner), but CONTEXT.md locks capture to Next.js API route leveraging existing service.ts |
| pg_cron for retention cleanup | Inline DELETE in capture | pg_cron requires Supabase Pro add-on; inline DELETE is simpler for ~5,400 rows |

## Architecture Patterns

### Recommended Project Structure
```
dashboard/src/
  app/
    api/
      funnel-snapshots/
        capture/route.ts     # POST - capture yesterday's data, write to Supabase
        trends/route.ts      # GET - return 7d vs prev-7d aggregated trends
    (dashboard)/
      shopping-funnel/
        FunnelTrendCards.tsx  # New component: 6 trend summary cards
        page.tsx             # Modified: add FunnelTrendCards above tabs
  lib/
    shopping-funnel/
      service.ts             # UNCHANGED - existing getLabelTierPerformance() reused
scripts/
  setup-funnel-scheduler.sh  # Cloud Scheduler setup script (human runs)
```

### Pattern 1: Write-Behind Capture
**What:** The capture endpoint calls the existing `getLabelTierPerformance()` function with yesterday's date, then writes results to Supabase. It does NOT modify the live query path.
**When to use:** Always -- the capture is a completely separate code path from live dashboard queries.
**Example:**
```typescript
// Source: service.ts line 1042-1101 (existing, unchanged)
const result = await getLabelTierPerformance({
  startDate: yesterday,
  endDate: yesterday,
})

// New: write to Supabase
const rows = result.rows.map(row => ({
  snapshot_date: yesterday,
  custom_label_0: row.custom_label_0,
  tier: row.tier,
  impressions: row.impressions,
  clicks: row.clicks,
  cost_micros: row.cost_micros,
  conversions: row.conversions,
  conversions_value: row.conversions_value,
  roas: row.roas,
}))

await supabase.from('funnel_snapshots_daily').upsert(rows, {
  onConflict: 'snapshot_date,custom_label_0,tier',
})
```

### Pattern 2: Shared Secret Authentication for Vercel Endpoints
**What:** Since Cloud Scheduler targets a Vercel endpoint (not Cloud Run), OIDC authentication is not available. Use a shared secret in an environment variable.
**When to use:** For the `/api/funnel-snapshots/capture` endpoint, which is triggered by Cloud Scheduler.
**Example:**
```typescript
// In capture/route.ts
const authHeader = request.headers.get('authorization')
const expectedToken = process.env.CRON_SECRET
if (!expectedToken || authHeader !== `Bearer ${expectedToken}`) {
  return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
}
```
**Cloud Scheduler passes the secret as a header:**
```bash
--headers="Content-Type=application/json,Authorization=Bearer ${CRON_SECRET}"
```

### Pattern 3: SQL Aggregation for Trend Queries
**What:** Use a single Supabase SQL query to compute 7-day and previous-7-day sums.
**When to use:** For the `/api/funnel-snapshots/trends` endpoint.
**Example:**
```sql
SELECT
  CASE
    WHEN snapshot_date >= CURRENT_DATE - INTERVAL '7 days' THEN 'current'
    ELSE 'previous'
  END AS period,
  SUM(impressions) AS impressions,
  SUM(clicks) AS clicks,
  SUM(cost_micros) AS cost_micros,
  SUM(conversions) AS conversions,
  SUM(conversions_value) AS conversions_value
FROM funnel_snapshots_daily
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '14 days'
GROUP BY period;
```
CTR and ROAS are computed client-side from the sums (CTR = clicks/impressions, ROAS = conversions_value / (cost_micros/1e6)).

### Anti-Patterns to Avoid
- **Modifying service.ts live path:** NEVER add Supabase writes inside `getLabelTierPerformance()` or `fetchAdsContext()`. The capture is a separate endpoint.
- **Storing pre-computed rolling averages:** Store daily totals only. Rolling windows computed at query time. This avoids data inconsistency when days are missing.
- **Using Vercel Cron (vercel.json cron):** Vercel Pro cron has limitations (1/day on free, unreliable timing). Use GCP Cloud Scheduler which already runs the daily backfill job.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date math for "yesterday" | Custom date parsing | `new Date(); d.setDate(d.getDate()-1); d.toISOString().split('T')[0]` | Edge cases with timezones |
| GAQL query for tier data | Duplicate query logic | `getLabelTierPerformance()` from service.ts | Already proven, guarantees parity |
| Upsert with conflict handling | Manual INSERT/UPDATE | Supabase `.upsert()` with `onConflict` | Handles re-runs safely |
| Trend percentage calculation | Complex math utilities | Simple `((current - previous) / previous) * 100` | Straightforward for 6 metrics |

## Common Pitfalls

### Pitfall 1: Timezone Mismatch for "Yesterday"
**What goes wrong:** Cloud Scheduler fires at 5 AM ET, but server-side `new Date()` uses UTC. "Yesterday" in ET vs UTC can differ.
**Why it happens:** Vercel serverless runs in UTC. 5 AM ET = 10 AM UTC. At 10 AM UTC, "yesterday" in UTC is correct (same calendar day as "yesterday" in ET since it's past midnight UTC).
**How to avoid:** Compute yesterday explicitly: `const d = new Date(); d.setUTCDate(d.getUTCDate() - 1); const yesterday = d.toISOString().split('T')[0]`. This always gives the correct calendar date regardless of when the function runs.
**Warning signs:** Missing data for specific days, or duplicate rows with off-by-one dates.

### Pitfall 2: Capture Endpoint Re-Runs Causing Duplicates
**What goes wrong:** If Cloud Scheduler retries (3x configured), the same day's data could be inserted multiple times.
**Why it happens:** No idempotency protection on plain INSERT.
**How to avoid:** Use UPSERT with `ON CONFLICT (snapshot_date, custom_label_0, tier) DO UPDATE`. This makes re-runs safe.
**Warning signs:** Row counts exceeding expected ~60/day.

### Pitfall 3: Google Ads Data Not Settled
**What goes wrong:** Querying "yesterday" too early returns incomplete data.
**Why it happens:** Google Ads finalizes metrics 3-4 hours after midnight PT (8 AM PT typically). 5 AM ET = 2 AM PT, which is before data settles.
**How to avoid:** Change Cloud Scheduler to fire at 8 AM ET (5 AM PT) or later. Google Ads documentation says data for the previous day is fully available by ~3-4 AM PT, so 5 AM PT provides a safe margin.
**Warning signs:** Impression/click counts for the same day are lower than live dashboard shows for the same period.

### Pitfall 4: Division by Zero in Trend Calculations
**What goes wrong:** CTR or ROAS calculation divides by zero when impressions or spend is zero.
**Why it happens:** A 7-day window with zero impressions (possible for new labels) produces NaN.
**How to avoid:** Guard with: `const ctr = impressions > 0 ? clicks / impressions : 0`. Same for ROAS.
**Warning signs:** NaN or Infinity rendering in UI cards.

### Pitfall 5: Vercel Function Timeout
**What goes wrong:** The capture endpoint times out before completing.
**Why it happens:** `getLabelTierPerformance()` calls `fetchAdsContext()` which fires 6+ GAQL queries in parallel. This typically takes 5-15 seconds. Vercel Pro has a 60-second timeout.
**How to avoid:** The 60-second timeout is sufficient. But add logging to track execution time. If it becomes an issue, consider having the capture endpoint call yesterday-only queries (lighter than the default 30-day window).
**Warning signs:** 504 errors in Cloud Scheduler job history.

## Code Examples

### Table Schema (CREATE TABLE via Supabase MCP)
```sql
-- Source: designed from service.ts LabelTierPerformance type + CONTEXT.md decisions
CREATE TABLE IF NOT EXISTS funnel_snapshots_daily (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  custom_label_0 TEXT NOT NULL,
  tier TEXT NOT NULL CHECK (tier IN ('HIGH', 'MEDIUM', 'LOW')),
  impressions BIGINT NOT NULL DEFAULT 0,
  clicks BIGINT NOT NULL DEFAULT 0,
  cost_micros BIGINT NOT NULL DEFAULT 0,
  conversions DOUBLE PRECISION NOT NULL DEFAULT 0,
  conversions_value DOUBLE PRECISION NOT NULL DEFAULT 0,
  roas DOUBLE PRECISION NOT NULL DEFAULT 0,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (snapshot_date, custom_label_0, tier)
);

-- Index for trend queries (WHERE snapshot_date >= X)
CREATE INDEX idx_funnel_snapshots_date ON funnel_snapshots_daily (snapshot_date DESC);

-- Enable RLS (required by Supabase, but service role bypasses it)
ALTER TABLE funnel_snapshots_daily ENABLE ROW LEVEL SECURITY;
```

### Capture Endpoint Pattern
```typescript
// Source: follows capture-snapshot/route.ts pattern (existing project pattern)
import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { getLabelTierPerformance } from '@/lib/shopping-funnel/service'

export async function POST(request: NextRequest) {
  // Auth check (shared secret)
  const authHeader = request.headers.get('authorization')
  const expectedToken = process.env.CRON_SECRET
  if (!expectedToken || authHeader !== `Bearer ${expectedToken}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const yesterday = new Date()
  yesterday.setUTCDate(yesterday.getUTCDate() - 1)
  const snapshotDate = yesterday.toISOString().split('T')[0]

  // Fetch from Google Ads (same query as live dashboard)
  const result = await getLabelTierPerformance({
    startDate: snapshotDate,
    endDate: snapshotDate,
  })

  // Write to Supabase
  const supabase = createAdminClient()
  const rows = result.rows.map(row => ({
    snapshot_date: snapshotDate,
    custom_label_0: row.custom_label_0,
    tier: row.tier,
    impressions: row.impressions,
    clicks: row.clicks,
    cost_micros: row.cost_micros,
    conversions: row.conversions,
    conversions_value: row.conversions_value,
    roas: row.roas,
  }))

  const { error: upsertError } = await supabase
    .from('funnel_snapshots_daily')
    .upsert(rows, { onConflict: 'snapshot_date,custom_label_0,tier' })

  if (upsertError) throw new Error(upsertError.message)

  // 90-day retention cleanup
  const cutoff = new Date()
  cutoff.setUTCDate(cutoff.getUTCDate() - 90)
  await supabase
    .from('funnel_snapshots_daily')
    .delete()
    .lt('snapshot_date', cutoff.toISOString().split('T')[0])

  return NextResponse.json({
    snapshot_date: snapshotDate,
    rows_captured: rows.length,
  })
}
```

### Cloud Scheduler Setup Script
```bash
#!/bin/bash
# Source: follows scripts/setup-cloud-scheduler.sh pattern from Phase 8

PROJECT_ID="bobbys-project-346400"
LOCATION="us-east1"
JOB_NAME="feedops-funnel-snapshot-daily"
DASHBOARD_URL="https://allied-feed-ops.vercel.app"
CRON_SECRET="${1:?Usage: $0 <CRON_SECRET>}"

# 5 AM ET = cron in America/New_York timezone
# Note: Consider 8 AM ET (5 AM PT) for better data settlement
gcloud scheduler jobs create http "$JOB_NAME" \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --schedule="0 5 * * *" \
  --time-zone="America/New_York" \
  --uri="$DASHBOARD_URL/api/funnel-snapshots/capture" \
  --http-method=POST \
  --headers="Content-Type=application/json,Authorization=Bearer ${CRON_SECRET}" \
  --message-body='{}' \
  --attempt-deadline=120s \
  --max-retry-attempts=3 \
  --min-backoff=60s \
  --max-backoff=300s
```

### Trend Cards UI Pattern
```typescript
// Source: follows performance/page.tsx TrendIcon pattern (line 164-168)
function TrendArrow({ current, previous, invertColor }: {
  current: number
  previous: number
  invertColor?: boolean // true for cost metrics where "down" is good
}) {
  if (previous === 0) return <span className="text-xs text-muted-foreground">No prior data</span>
  const pctChange = ((current - previous) / previous) * 100
  const isUp = pctChange > 5
  const isDown = pctChange < -5

  if (!isUp && !isDown) return <Minus className="h-4 w-4 text-muted-foreground" />

  const positive = invertColor ? isDown : isUp
  const color = positive ? 'text-green-600' : 'text-red-600'
  const Icon = isUp ? TrendingUp : TrendingDown

  return (
    <div className={`flex items-center gap-1 ${color}`}>
      <Icon className="h-4 w-4" />
      <span className="text-xs font-medium">{pctChange >= 0 ? '+' : ''}{pctChange.toFixed(1)}%</span>
    </div>
  )
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| service.ts 2-min cache only | Daily snapshots + live cache | Phase 30 (this phase) | Enables historical trend analysis |
| No automated funnel monitoring | Cloud Scheduler daily capture | Phase 30 (this phase) | Zero user intervention needed |

**Existing infrastructure this phase builds on:**
- `getLabelTierPerformance()` in service.ts (proven, 6+ months in production)
- Cloud Scheduler pattern from Phase 8 (`feedops-daily-incremental-refresh` job)
- `createAdminClient()` for Supabase service-role writes
- Performance page TrendIcon component for visual pattern reference

## Open Questions

1. **Cloud Scheduler timing: 5 AM ET vs 8 AM ET**
   - What we know: Google Ads data for yesterday is typically finalized by 3-4 AM PT. 5 AM ET = 2 AM PT, which is BEFORE settlement.
   - What's unclear: Whether partial data at 2 AM PT is "close enough" for trend analysis (likely 95%+ complete).
   - Recommendation: Use 8 AM ET (5 AM PT) to be safe. The user specified 5 AM ET but this may cause slightly incomplete data. Flag to user during planning.

2. **CRON_SECRET management**
   - What we know: Vercel doesn't support OIDC. A shared secret is the standard pattern for Vercel cron endpoints.
   - What's unclear: Whether `CRON_SECRET` env var already exists in Vercel settings.
   - Recommendation: Add `CRON_SECRET` to Vercel env vars. Generate a random UUID. Pass it to the Cloud Scheduler setup script.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 3.2.4 |
| Config file | `dashboard/vitest.config.ts` |
| Quick run command | `cd dashboard && npx vitest run` |
| Full suite command | `cd dashboard && npm test` |
| Estimated runtime | ~10 seconds |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HIST-01 | funnel_snapshots_daily table created with correct schema | manual (Supabase MCP) | N/A -- verified by SQL execution | N/A |
| HIST-01 | 90-day retention cleanup deletes old rows | unit | `cd dashboard && npx vitest run src/app/api/funnel-snapshots/__tests__/capture.test.ts` | No -- Wave 0 gap |
| HIST-02 | Capture endpoint calls getLabelTierPerformance and writes to Supabase | unit | `cd dashboard && npx vitest run src/app/api/funnel-snapshots/__tests__/capture.test.ts` | No -- Wave 0 gap |
| HIST-02 | Auth check rejects unauthorized requests | unit | `cd dashboard && npx vitest run src/app/api/funnel-snapshots/__tests__/capture.test.ts` | No -- Wave 0 gap |
| HIST-02 | Cloud Scheduler setup script is syntactically valid | manual (human runs) | N/A | N/A |
| HIST-03 | Trends API returns correct 7d vs prev-7d aggregates | unit | `cd dashboard && npx vitest run src/app/api/funnel-snapshots/__tests__/trends.test.ts` | No -- Wave 0 gap |
| HIST-03 | Trend cards render with correct arrows and thresholds | unit | `cd dashboard && npx vitest run src/app/(dashboard)/shopping-funnel/__tests__/FunnelTrendCards.test.tsx` | No -- Wave 0 gap |
| HIST-03 | Cards handle missing data gracefully ("No prior data") | unit | Same as above | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task -> run: `cd dashboard && npx vitest run`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green + `npm run build` passes
- **Estimated feedback latency per task:** ~10 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `dashboard/src/app/api/funnel-snapshots/__tests__/capture.test.ts` -- covers HIST-01 (retention), HIST-02 (capture + auth)
- [ ] `dashboard/src/app/api/funnel-snapshots/__tests__/trends.test.ts` -- covers HIST-03 (aggregation logic)
- [ ] `dashboard/src/app/(dashboard)/shopping-funnel/__tests__/FunnelTrendCards.test.tsx` -- covers HIST-03 (UI rendering)

## Sources

### Primary (HIGH confidence)
- `dashboard/src/lib/shopping-funnel/service.ts` -- `getLabelTierPerformance()` function (lines 1042-1101), `fetchAdsContext()` (lines 479-660), GAQL query (lines 553-569), cache mechanism (lines 107, 480-485)
- `dashboard/src/lib/shopping-funnel/types.ts` -- `LabelTierPerformance` type definition (lines 200-218)
- `dashboard/src/app/(dashboard)/shopping-funnel/page.tsx` -- existing page structure, tabs, layout
- `dashboard/src/app/api/performance/capture-snapshot/route.ts` -- existing capture endpoint pattern
- `dashboard/src/lib/supabase/admin.ts` -- `createAdminClient()` for service-role writes
- `dashboard/src/app/(dashboard)/performance/page.tsx` -- TrendIcon component pattern (lines 164-168), delta calculation (lines 125-148)
- `.planning/milestones/v1.0-phases/08-monitoring-automation/08-04-PLAN.md` -- Cloud Scheduler setup pattern with OIDC
- `.planning/phases/28-architecture-audit-migration-triage/28-null-audit-and-quota.md` -- API quota analysis confirming sustainability

### Secondary (MEDIUM confidence)
- Google Ads data settlement timing (3-4 AM PT) -- based on operational experience documented in Phase 28 research

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- follows exact patterns from Phase 8 (Cloud Scheduler) and Phase 29 (Supabase tables)
- Pitfalls: HIGH -- based on direct code inspection of service.ts and existing capture endpoints

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable domain, no fast-moving dependencies)
