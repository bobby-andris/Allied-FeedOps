# 02 Generation Telemetry (Last 7 Days)

## Query
```sql
select
  date_trunc('day', created_at) as day_utc,
  platform,
  content_type,
  mode,
  count(*) as total_rows,
  count(*) filter (where tokens_used is null) as tokens_null_rows,
  count(*) filter (where cost_usd is null) as cost_null_rows,
  round(avg(latency_ms)::numeric,2) as avg_latency_ms,
  round(percentile_cont(0.95) within group (order by latency_ms)::numeric,2) as p95_latency_ms
from regeneration_history
where created_at >= now() - interval '7 days'
group by 1,2,3,4
order by day_utc desc, platform, content_type, mode;
```

## Key Findings Snapshot
- `2026-02-27` google/description/full_generation_v2: `tokens_null_rows=1/1`, `cost_null_rows=1/1`, `latency_ms=231308`
- `2026-02-27` google/description/simple: `tokens_null_rows=2/6`, `cost_null_rows=2/6`, `avg_latency_ms=55505.50`
- `2026-02-27` google/title/simple: `tokens_null_rows=2/6`, `cost_null_rows=2/6`, `avg_latency_ms=111264.25`
- `2026-02-26` google/description/with_feedback: `tokens_null_rows=20/20`, `cost_null_rows=20/20`, `p95_latency_ms=608952.15`

Conclusion: telemetry null coverage and high-latency outliers exist in baseline and are valid R1 targets.
