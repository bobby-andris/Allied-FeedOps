# OpenAI Usage Permissions Runbook

## Purpose
This runbook documents how to enable and verify OpenAI organization usage/cost access for dashboard reconciliation.

The reconciliation pipeline reads:
- `https://api.openai.com/v1/organization/usage/completions`
- `https://api.openai.com/v1/organization/costs`

If credentials are missing or under-scoped, reconciliation still runs but returns warnings and `missing_openai_data` windows.

## Required Environment Variables
Configure these in Vercel (dashboard runtime). Configure in Cloud Run only if that service calls reconciliation endpoints.

1. `OPENAI_USAGE_API_KEY` (preferred)
2. `OPENAI_ORG_ID`
3. `OPENAI_PROJECT_ID` (optional; narrows usage window to one project)

Fallback order in runtime:
1. `OPENAI_USAGE_API_KEY`
2. `OPENAI_ADMIN_API_KEY`
3. `OPENAI_API_KEY`

## Symptoms Of Missing Permissions
Warnings in reconciliation payload/logs:

1. `OpenAI usage key is not configured; set OPENAI_USAGE_API_KEY (preferred), OPENAI_ADMIN_API_KEY, or OPENAI_API_KEY.`
2. `OpenAI usage API auth error (401|403); ... Use an org-level key with organization usage/cost permissions and set OPENAI_ORG_ID if required.`
3. `OpenAI costs API auth error (401|403); ... Use an org-level key with organization usage/cost permissions and set OPENAI_ORG_ID if required.`

## Verification Steps
1. Confirm env vars are set in Vercel production.
2. Trigger reconciliation capture:
```bash
curl -X POST "https://allied-feed-ops.vercel.app/api/monitoring/cost-reconciliation?lookback_days=1" \
  -H "x-vercel-cron: 1"
```
3. Confirm response has `success=true` and no auth warnings.
4. Confirm Supabase rows populate for the captured window:
   - `openai_usage_window_rollups`
   - `generation_cost_window_rollups`
   - `cost_reconciliation_deltas`

## SQL Spot Checks
```sql
select window_start, window_end, total_cost_usd, currency, captured_at
from openai_usage_window_rollups
order by window_start desc
limit 5;
```

```sql
select window_start, window_end, status, mismatch_categories, captured_at
from cost_reconciliation_deltas
order by window_start desc
limit 5;
```

## Troubleshooting
1. If windows show `missing_openai_data`, inspect `warnings` in `cost_reconciliation_deltas.metadata`.
2. If auth warnings persist after key rotation, verify org membership and key scope.
3. If internal rows exist but OpenAI rows are null, check clock/window boundaries and `OPENAI_PROJECT_ID` filter.
