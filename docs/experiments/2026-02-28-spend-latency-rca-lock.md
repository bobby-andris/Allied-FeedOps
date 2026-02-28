# Spend + Latency RCA Lock (2026-02-28)

## Scope
- Repo: `Allied-FeedOps`
- Branch at capture: `codex/e245-spend-latency-containment-20260228`
- Runtime surfaces: Cloud Run (`feedops-pipeline`), Supabase (`qezuszwufortkiutlhym`), Vercel reconciliation tables
- Window analyzed: latest 24h, including the 6pm–11pm ET incident window

## Evidence Snapshot

### Supabase lineage + latency evidence
- `regeneration_history` rows with non-null latency (24h):
  - `total_rows=21`
  - `p50=42169ms`
  - `p90=164382ms`
  - `p99=220006ms`
  - `max=231308ms`
  - avg `provider_attempt_count=1.33`
- `request_id` coverage issue (24h):
  - `request_id_null=52` of `79` rows
- `result_state` distribution (24h):
  - `null=61`, `completed=18`
- Reconciliation tables:
  - `cost_reconciliation_deltas` rows present, but status is `missing_openai_data`
  - `mismatch_categories` include `openai_usage_unavailable` and `internal_only_activity`

Representative high-latency request IDs:
- `6d0dafc52b9b43c8bfb322da8e700b41` (231308ms, google/description)
- `4c632a37-4df8-401c-ae76-7dab5d26e363` (174798ms, google/description)
- `4cfa65be-a43d-47ab-8588-35b22038f768` (164382ms, google/description)

### Cloud Run log evidence (`bobbys-project-346400`, `us-east1`)
- For the above request IDs, logs show:
  - repeated `provider.generate.retry` + timeout warnings
  - terminal summaries with elevated `provider_attempt_count` (2–3) and high latency
  - long-tail durations correlate with retry/timeout envelope before terminal failure or success

### Hybrid batch consistency evidence
- Failed parent job observed:
  - `batch_generation_jobs.id=2ccd5453-e145-43ea-885f-eeb40a3550d6`, status `failed`
- Child SKU rows for that failed parent included a lingering `pending` row instead of terminal state.

## Hypothesis Table (ranked)

| Rank | Hypothesis | Evidence | Confidence | Impact |
|---|---|---|---|---|
| 1 | Retry/timeout envelope amplification drives long-tail latency and spend | Cloud Run retries/timeouts + 164–231s requests + attempts 2–3 | High | High |
| 2 | Finish sub-call and per-platform fan-out can amplify spend per user action | Description path includes finish branch, multi-platform usage aggregation in lineage | Medium | Medium/High |
| 3 | Incomplete lineage/telemetry obscures true cost path and incident triage | High `request_id` null rate, many `result_state=null`, missing OpenAI usage join | High | High |
| 4 | Hybrid parent failure can leave non-terminal child rows | Failed parent with child pending rows | High | Medium |

## Locked Conclusions
1. Long latency is not random; it is consistent with bounded-but-too-wide retry/timeout behavior under provider failures.
2. Spend opacity is partly data-quality related (lineage gaps), not only provider-side billing lag.
3. Hybrid state fan-out requires deterministic terminalization to keep job accounting trustworthy.
4. Reconciliation is not fully operational until OpenAI usage API data is ingested successfully.

## Immediate Containment Objectives
1. Tighten default timeout/retry envelope.
2. Add request-level budget stop guard.
3. Mark diagnostic runs explicitly and support low-cost mode.
4. Ensure summary events include enough context to explain spend and finish-branch behavior.
