# 03 Request-ID Dedupe and Batch Job Snapshot

## Query A (Request-ID duplicate coverage)
```sql
with recent as (
  select request_id, count(*) as row_count, min(created_at) as first_seen, max(created_at) as last_seen
  from regeneration_history
  where created_at >= now() - interval '7 days'
    and request_id is not null
  group by request_id
), dupes as (
  select * from recent where row_count > 1
)
select
  (select count(*) from recent) as distinct_request_ids,
  (select count(*) from dupes) as duplicate_request_ids,
  (select coalesce(sum(row_count),0) from dupes) as duplicate_rows_total,
  (select max(row_count) from dupes) as max_rows_for_single_request_id;
```

### Result
- `distinct_request_ids=10`
- `duplicate_request_ids=0`
- `duplicate_rows_total=0`

## Query B (Batch tables present + recent batch jobs)
```sql
select to_regclass('public.batch_generation_sku_details') as batch_generation_sku_details_table,
       to_regclass('public.batch_generation_jobs') as batch_generation_jobs_table;

select id, status, total_skus, completed_skus, failed_skus, created_at, started_at, completed_at
from batch_generation_jobs
order by created_at desc
limit 20;
```

### Result Highlights
- `batch_generation_jobs_table` exists.
- Latest batch job (`0c52acdc-ac07-4437-8731-40432ec47a1a`) status was `failed` with `total_skus=2`, `completed_skus=1`, `failed_skus=1`.
- Multiple historical rows show inconsistent relationships between `status` and `completed_skus/failed_skus`, supporting R1 batch-detail hardening scope.
