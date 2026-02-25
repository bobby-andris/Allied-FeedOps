# Phase 30: Historical Funnel Persistence - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Persist the live Google Ads shopping funnel data (currently ephemeral with 2-min cache in service.ts) into daily snapshots stored in Supabase. Surface 7-day vs previous-7-day trend indicators on the Shopping Funnel dashboard page. No new funnel management capabilities — just historical persistence and trend display for existing data.

</domain>

<decisions>
## Implementation Decisions

### Snapshot granularity
- Label-tier aggregates only — one row per custom_label_0 + tier (HIGH/MEDIUM/LOW) per day
- ~60 rows/day × 90 days retention = ~5,400 rows max
- Store daily totals (single day's metrics), not rolling period sums — rolling windows computed at query time
- Reuse the same GAQL query from service.ts with startDate=endDate=yesterday — guarantees parity with live dashboard data
- Tier performance metrics only: impressions, clicks, cost_micros, conversions, conversions_value, ROAS
- No search-term-level snapshots, no needs-decision counts

### Trend display
- All 6 funnel metrics get trend indicators: Impressions, Clicks, CTR, Ad Spend, Conversions, ROAS
- 5% threshold: changes under 5% show as flat (─), over 5% shows arrow up (▲) or down (▼)
- Summary cards placed above existing tabs (Needs Decision / Existing Funnel)
- Account-wide totals across all labels and tiers — no label filter dropdown
- 6 cards in 2 rows of 3: Row 1 = Impressions, Clicks, CTR; Row 2 = Ad Spend, Conversions, ROAS

### Historical visualization
- Trend arrows only — no sparklines, no time-series charts, no separate history tab
- Fixed 7-day comparison window (last 7 days vs previous 7 days) — no user-selectable window
- When insufficient historical data: show current 7-day value with muted "No prior data" instead of trend arrow
- Cards hidden entirely only if zero snapshot data exists

### Capture endpoint & scheduling
- New dashboard API route: /api/funnel-snapshots/capture (Next.js, leverages existing service.ts GAQL)
- Cloud Scheduler triggers at 5 AM ET daily (Google Ads data for yesterday settled by then)
- Retry 3x with backoff on failure, then skip that day — dashboard handles gaps gracefully
- 90-day retention cleanup runs inline with each capture (DELETE WHERE snapshot_date < NOW() - 90 days)

### Claude's Discretion
- Exact table schema (column types, indexes, constraints)
- Cloud Scheduler configuration details (cron expression, HTTP target auth)
- API route authentication (service account key vs shared secret)
- Error logging format and destination
- Exact card component styling (shadows, spacing, responsive breakpoints)

</decisions>

<specifics>
## Specific Ideas

- Summary cards should follow the same visual pattern as the Overview page's metric cards
- The capture endpoint must not add latency to the live service.ts query path (write-behind, separate call)
- Phase 28 API quota analysis confirmed daily capture fits within Google Ads Standard Access limits

</specifics>

<deferred>
## Deferred Ideas

- Per-label-tier trend breakdown (inline trends in existing funnel tables) — future enhancement
- Selectable comparison windows (14d, 30d) — future enhancement
- Sparkline charts in summary cards — future enhancement
- Search-term-level daily snapshots — future phase if needed for term-level trend analysis
- Alerting on significant metric changes (e.g., ROAS drops >20%) — separate feature

</deferred>

---

*Phase: 30-historical-funnel-persistence*
*Context gathered: 2026-02-25*
