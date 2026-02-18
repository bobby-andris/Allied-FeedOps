---
phase: quick-1
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/components/shared/Sidebar.tsx
autonomous: true

must_haves:
  truths:
    - "Backfill Monitoring link appears in sidebar and navigates to /backfill"
    - "Performance snapshots table has been queried and row count is confirmed"
    - "Cloud Scheduler has a daily snapshot capture job at 3am PT targeting the Vercel endpoint"
  artifacts:
    - path: "dashboard/src/components/shared/Sidebar.tsx"
      provides: "Backfill Monitoring nav entry"
      contains: "Activity"
  key_links:
    - from: "Sidebar.tsx navigation array"
      to: "/backfill route"
      via: "href: '/backfill'"
      pattern: "href.*backfill"
---

<objective>
Add Backfill Monitoring to the sidebar navigation, verify what performance snapshot data exists in Supabase, and create a Cloud Scheduler job for daily snapshot capture.

Purpose: Surface the backfill monitoring page through normal navigation; understand current snapshot data coverage; automate daily performance tracking.
Output: Updated sidebar with Backfill Monitoring entry, confirmed snapshot data state, Cloud Scheduler job for daily captures.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@dashboard/src/components/shared/Sidebar.tsx
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add Backfill Monitoring to sidebar navigation</name>
  <files>dashboard/src/components/shared/Sidebar.tsx</files>
  <action>
    In `dashboard/src/components/shared/Sidebar.tsx`:

    1. Add `Activity` to the lucide-react import (line 16, alongside ClipboardList, Layers, etc.)
    2. Insert a new nav entry in the `navigation` array between `Search Insights` and `Settings`:
       ```
       { name: 'Backfill Monitoring', href: '/backfill', icon: Activity },
       ```

    The final navigation array order should be:
    Overview, Generate, Review Queue, Competitors, Batches, Performance, Search Insights, Backfill Monitoring, Settings
  </action>
  <verify>
    cd dashboard && npm run build
    Confirm build passes with zero TypeScript errors.
    Visually confirm: run `npm run dev`, navigate to http://localhost:3000 — "Backfill Monitoring" appears in sidebar and clicking it loads /backfill.
  </verify>
  <done>Sidebar shows Backfill Monitoring link with Activity icon; /backfill page loads; build passes with zero errors.</done>
</task>

<task type="auto">
  <name>Task 2: Check performance_snapshots data</name>
  <files></files>
  <action>
    Use `mcp__supabase__execute_sql` to query the performance_snapshots table and understand current data state.

    Run these queries against project `qezuszwufortkiutlhym`:

    Query 1 — Row count and date range:
    ```sql
    SELECT
      COUNT(*) AS total_snapshots,
      COUNT(DISTINCT master_sku) AS distinct_skus,
      MIN(captured_at) AS earliest_snapshot,
      MAX(captured_at) AS latest_snapshot
    FROM performance_snapshots;
    ```

    Query 2 — Breakdown by platform:
    ```sql
    SELECT platform, COUNT(*) AS snapshot_count
    FROM performance_snapshots
    GROUP BY platform
    ORDER BY snapshot_count DESC;
    ```

    Query 3 — Days since publish distribution (sample):
    ```sql
    SELECT days_since_publish, COUNT(*) AS count
    FROM performance_snapshots
    WHERE days_since_publish IS NOT NULL
    GROUP BY days_since_publish
    ORDER BY days_since_publish;
    ```

    Record the results in the SUMMARY.
  </action>
  <verify>All three queries return without error. Results are recorded in SUMMARY.</verify>
  <done>Performance snapshots data state is documented: total rows, distinct SKUs, date range, platform breakdown, days_since_publish distribution.</done>
</task>

<task type="auto">
  <name>Task 3: Create Cloud Scheduler job for daily snapshot capture</name>
  <files></files>
  <action>
    A Cloud Scheduler job for incremental refresh already exists (`feedops-daily-incremental-refresh` at 2:00 AM PT).
    No snapshot capture job exists yet.

    Create a new Cloud Scheduler HTTP job targeting the Vercel dashboard endpoint:

    ```bash
    gcloud scheduler jobs create http feedops-daily-snapshot-capture \
      --project=bobbys-project-346400 \
      --location=us-east1 \
      --schedule="0 3 * * *" \
      --time-zone="America/Los_Angeles" \
      --uri="https://allied-feed-ops.vercel.app/api/performance/capture-snapshot" \
      --http-method=POST \
      --headers="Content-Type=application/json" \
      --message-body="{}" \
      --description="Daily performance snapshot capture for all published SKUs" \
      --attempt-deadline=30m
    ```

    Schedule: 3:00 AM PT daily (1 hour after the incremental refresh completes at 2am, so fresh search/performance data is available before snapshot runs).

    After creating, verify the job exists and is ENABLED:
    ```bash
    gcloud scheduler jobs describe feedops-daily-snapshot-capture \
      --project=bobbys-project-346400 \
      --location=us-east1
    ```

    Optionally test-trigger the job to confirm the endpoint responds:
    ```bash
    gcloud scheduler jobs run feedops-daily-snapshot-capture \
      --project=bobbys-project-346400 \
      --location=us-east1
    ```
    Then check the job's last attempt status to confirm success (not failure).
  </action>
  <verify>
    `gcloud scheduler jobs list --project=bobbys-project-346400 --location=us-east1` shows both:
    - feedops-daily-incremental-refresh (existing)
    - feedops-daily-snapshot-capture (new, ENABLED, schedule 0 3 * * *)
  </verify>
  <done>Cloud Scheduler job `feedops-daily-snapshot-capture` exists, is ENABLED, scheduled at 3:00 AM PT daily, and targets https://allied-feed-ops.vercel.app/api/performance/capture-snapshot.</done>
</task>

</tasks>

<verification>
1. `cd dashboard && npm run build` passes with zero errors
2. Sidebar shows Backfill Monitoring between Search Insights and Settings
3. `gcloud scheduler jobs list --project=bobbys-project-346400 --location=us-east1` shows two jobs
4. Performance snapshots query results documented in SUMMARY
</verification>

<success_criteria>
- Backfill Monitoring is accessible from sidebar navigation at /backfill
- Performance snapshots data state is known (row count, SKU coverage, date range)
- Cloud Scheduler job automates daily snapshot capture at 3am PT
- Dashboard build passes with zero TypeScript/lint errors
</success_criteria>

<output>
After completion, create `.planning/quick/1-add-backfill-monitoring-to-sidebar-check/1-SUMMARY.md`
Include: sidebar change confirmed, snapshot data query results (table), scheduler job created with details.
</output>
