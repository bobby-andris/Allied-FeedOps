# 01 Table Presence and Estimated Rows

## Query
```sql
select now() as captured_at_utc, relname as table_name, n_live_tup::bigint as estimated_rows
from pg_stat_user_tables
where schemaname='public'
  and relname in (
    'generated_content',
    'regeneration_history',
    'generation_jobs',
    'batch_generation_jobs',
    'batch_generation_sku_details',
    'variant_finish_sentences',
    'variant_index'
  )
order by relname;
```

## Result Snapshot
Captured at UTC: `2026-02-27 08:16:16.581667+00`

| table_name | estimated_rows |
|---|---:|
| batch_generation_jobs | 27 |
| generated_content | 585 |
| generation_jobs | 1 |
| regeneration_history | 1234 |
| variant_finish_sentences | 196 |
| variant_index | 72023 |

Note: `batch_generation_sku_details` not returned by `pg_stat_user_tables` in this snapshot.
