# 04 Key Lineage and Telemetry Columns

## Query
```sql
select table_name, column_name, data_type
from information_schema.columns
where table_schema='public'
  and (
    (table_name='regeneration_history' and column_name in (
      'request_id','master_sku','platform','content_type','mode','tokens_used','cost_usd','latency_ms',
      'prompt_hash','system_prompt','user_prompt','generated_content_id','created_at'
    ))
    or (table_name='batch_generation_jobs' and column_name in (
      'id','status','total_skus','completed_skus','failed_skus','created_at','started_at','completed_at'
    ))
    or (table_name='variant_finish_sentences' and column_name in (
      'master_sku','platform','finish_sentences','created_at'
    ))
    or (table_name='generation_jobs' and column_name in (
      'id','status','master_sku','job_type','result','error','created_at','completed_at'
    ))
  )
order by table_name, column_name;
```

## Result Summary
Required baseline lineage/telemetry columns are present in `regeneration_history`:
- `request_id`, `prompt_hash`, `system_prompt`, `user_prompt`, `generated_content_id`
- `tokens_used`, `cost_usd`, `latency_ms`

Batch status coverage fields are present in `batch_generation_jobs`:
- `status`, `total_skus`, `completed_skus`, `failed_skus`, lifecycle timestamps.
