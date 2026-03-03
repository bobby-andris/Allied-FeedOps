# Phase 8 Runbook: 72k Scale-Up (Generate -> Review -> Publish)

## Scope
This runbook is the operational procedure for scaling content generation from current production usage to full-catalog coverage (~72k SKUs) with controlled risk.

It is aligned to current runtime code paths and tables:
- Generation entrypoint (dashboard): `dashboard/src/app/api/sku-selection/generate/route.ts`
- Generation engine (Cloud Run): `src/feedops/api/main.py` (`POST /batch-optimize`, `GET /batch-status/{job_id}`)
- Job status surfaces: `dashboard/src/app/api/sku-selection/jobs/route.ts`, `dashboard/src/app/api/sku-selection/generate/[jobId]/route.ts`, `dashboard/src/app/api/sku-selection/jobs/[jobId]/route.ts`
- Review APIs: `dashboard/src/app/api/approvals/route.ts`
- Publish APIs: `dashboard/src/app/api/publish/sku/route.ts`, `dashboard/src/app/api/publish/batch/route.ts`, `dashboard/src/app/api/batches/route.ts`
- Publish guard: `dashboard/src/lib/auth/publish-guard.ts`
- Rollback CLI: `src/feedops/cli/publish.py` (`feedops rollback`)
- Tables: `batch_generation_jobs`, `batch_generation_job_skus`, `sku_approvals`, `publish_batches`, `batch_sku_assignments`, `publish_events`, `generated_content`

## 1) Concrete Batch Sizing Strategy

### Hard limits and observed throughput
- Per request limit is hard-capped at `100` SKUs by both dashboard and pipeline contracts.
- Validation evidence in this environment:
  - `batch-optimize` dry run (`2` SKUs) completed with `2/2` success.
  - `batch-optimize` non-dry run (`1` SKU) completed with `1/1` success.
  - Latest observed non-idle throughput from `started_at` -> `completed_at`: `~1.55 SKU/min`.

### Wave plan (production)
1. `Wave 0 (calibration)`:
- `2 SKUs`, `dry_run=true`, `1` concurrent job.
- Goal: verify health, status propagation, and prompt-hash traceability.

2. `Wave 1 (pilot)`:
- `25 SKUs`, `dry_run=false`, `1` concurrent job.
- Goal: validate operator review/publish load and failure profile.

3. `Wave 2 (ramp)`:
- `100 SKUs/job`, `2` concurrent jobs.
- Gate: proceed only if stop conditions are not triggered.

4. `Wave 3 (steady-state)`:
- `100 SKUs/job`, default `4` concurrent jobs.
- Optional increase to `6` concurrent jobs only after 3 clean steady-state waves.

### Capacity estimate
- Full catalog requires ~`720` jobs at `100` SKUs/job.
- At ~`1.55 SKU/min` and `4` concurrent jobs, theoretical max is ~`370 SKU/hour` (subject to provider and operator constraints).

## 2) Operator Runbook (Generate -> Review -> Publish)

### A. Generate

#### A1. Preflight health checks
```bash
curl -sS -o /tmp/feedops_local_health.json -w '%{http_code}\n' http://127.0.0.1:3010/api/health
cat /tmp/feedops_local_health.json | jq '{supabase: .supabase.status, googleAds: .googleAds.status, gmc: .gmc.status, shopify: .shopify.status, googleAnalytics: .googleAnalytics.status}'
set -a; source dashboard/.env.local; set +a; curl -sS "$FEEDOPS_PIPELINE_URL/health" | jq '{status,service,supabase_connected,product_catalog_count}'
```
Expected outcomes:
- First command returns HTTP `200`.
- Local health JSON shows core dependencies as `connected`/`configured`.
- Pipeline health shows `status: "healthy"`, `supabase_connected: true`, and non-zero `product_catalog_count`.

#### A2. Pull candidate SKUs and baseline job queue status
```bash
curl -sS 'http://127.0.0.1:3010/api/sku-selection?count=5&excludeOptimized=true' | jq '{recommended_count: (.recommended|length), using_sample_data, first_sku: .recommended[0].master_sku}'
curl -sS 'http://127.0.0.1:3010/api/sku-selection/jobs' | jq '{job_count: (.jobs|length), latest_status: .jobs[0].status, latest_job_id: .jobs[0].id}'
```
Expected outcomes:
- `recommended_count` > 0 and `using_sample_data` is `false` for live-data operation.
- Jobs endpoint returns a valid latest job record (`latest_job_id`, `latest_status`).

#### A3. Calibration dry run (`dry_run=true`)
```bash
set -a; source dashboard/.env.local; set +a; \
curl -sS -X POST "$FEEDOPS_PIPELINE_URL/batch-optimize" \
  -H 'Content-Type: application/json' \
  -d '{"skus":["SB-16","107"],"num_candidates":1,"dry_run":true}' \
  | tee /tmp/phase8_batch_optimize_response.json \
  | jq '{success,job_id,status,total_skus}'

set -a; source dashboard/.env.local; set +a; \
JOB_ID=$(jq -r '.job_id' /tmp/phase8_batch_optimize_response.json); \
curl -sS "$FEEDOPS_PIPELINE_URL/batch-status/$JOB_ID" \
  | jq '{job_id,status,total_skus,completed_skus,failed_skus,sample_errors:[.skus[] | select(.status=="failed") | {master_sku,error_message}]}'

JOB_ID=$(jq -r '.job_id' /tmp/phase8_batch_optimize_response.json); \
curl -sS "http://127.0.0.1:3010/api/sku-selection/generate/$JOB_ID" \
  | jq '{job_id,status,total_skus,completed_skus,failed_skus,estimated_remaining_minutes,failed_list: .skus_by_status.failed}'
```
Expected outcomes:
- Initial create response returns `success: true`, `status: "queued"`, and a `job_id`.
- Status eventually reaches `completed` (or `partial`/`failed` with actionable errors).
- Dashboard job detail reflects the same totals and error list.

#### A4. Pilot production-mode run (`dry_run=false`)
```bash
set -a; source dashboard/.env.local; set +a; \
curl -sS -X POST "$FEEDOPS_PIPELINE_URL/batch-optimize" \
  -H 'Content-Type: application/json' \
  -d '{"skus":["1098"],"num_candidates":1,"dry_run":false}' \
  | tee /tmp/phase8_batch_optimize_nondry_response.json \
  | jq '{success,job_id,status,total_skus}'

JOB_ID=$(jq -r '.job_id' /tmp/phase8_batch_optimize_nondry_response.json); \
curl -sS "http://127.0.0.1:3010/api/sku-selection/jobs" \
  | jq -c --arg JOB "$JOB_ID" '.jobs[] | select(.id==$JOB) | {id,status,options,total_skus,completed_skus,failed_skus}'

.venv/bin/python - <<'PY'
from feedops.db.supabase_client import get_client
client=get_client()
sku='1098'
rows=client.table('generated_content').select('platform,content_type,generation_prompt_hash,generation_model,updated_at').eq('master_sku',sku).order('updated_at', desc=True).limit(6).execute().data or []
print({'sku':sku,'rows':len(rows),'latest':rows[0] if rows else None})
PY
```
Expected outcomes:
- Create response returns `success: true` and a new `job_id`.
- Jobs list shows this job with `options.dry_run: false`.
- `generated_content` contains fresh rows with non-empty `generation_prompt_hash` and `generation_model`.

### B. Review

Operator action (UI):
1. Open `/review` and process SKUs in `pending` state.
2. Approve/reject via dashboard controls (uses `/api/approvals` and variant approval routes).
3. Keep review queue balanced before launching the next generation wave.

Verification commands:
```bash
curl -sS 'http://127.0.0.1:3010/api/approvals?status=pending&limit=3' | jq '{pending_count: (.data|length), sample_sku: .data[0].master_sku, sample_status: .data[0].approval_status}'
curl -sS 'http://127.0.0.1:3010/api/approvals?status=approved&limit=10' | jq '{approved_count:(.data|length), skus:[.data[].master_sku]}'
```
Expected outcomes:
- Pending queue should remain non-zero but bounded; values trend down as approvals are processed.
- Approved count should increase before publish waves.

### C. Publish

Operator action (UI/API with authenticated session):
1. Build/adjust batch in `/batches`.
2. Set status to pending and execute publish via dashboard publish flow.
3. Monitor per-SKU assignment and `publish_events` outcomes.

Verification commands:
```bash
curl -sS 'http://127.0.0.1:3010/api/batches?batch_id=batch-ft16-uppercase-mpn-test' | jq '{rows:(.data|length), batch_id:.data[0].batch_id, status:.data[0].status, sku_count:.data[0].sku_count, success_count:.data[0].success_count, failed_count:.data[0].failed_count}'

.venv/bin/python - <<'PY'
from collections import Counter
from feedops.db.supabase_client import get_client
client=get_client()
batch='batch-ft16-uppercase-mpn-test'
events=client.table('publish_events').select('master_sku,platform,status,error_message,published_at').eq('batch_id',batch).execute().data or []
counts=Counter(e['status'] for e in events)
print({'batch_id':batch,'event_count':len(events),'status_counts':dict(counts),'sample':events[:2]})
PY
```
Expected outcomes:
- Batch record exists and status reflects execution (`published`, `partial`, or `failed`).
- Publish events exist for batch SKUs/platforms and provide error context when failures occur.

## 3) Stop Conditions and Rollback Instructions

### 3.1 Stop-condition thresholds
Pause the current wave immediately if any threshold is hit:

1. Generation failure ratio > `2%` over recent SKU rows.
```bash
.venv/bin/python - <<'PY'
from feedops.db.supabase_client import get_client
client = get_client()
jobs = client.table('batch_generation_jobs').select('id').order('created_at', desc=True).limit(20).execute().data or []
job_ids = [j['id'] for j in jobs]
failed = total = 0
if job_ids:
    rows = client.table('batch_generation_job_skus').select('status').in_('job_id', job_ids).execute().data or []
    total = len(rows)
    failed = sum(1 for r in rows if r.get('status') == 'failed')
ratio = (failed / total) if total else 0.0
print({'jobs_considered': len(job_ids), 'sku_rows': total, 'failed_rows': failed, 'failure_ratio': round(ratio,4)})
PY
```
Expected outcome:
- `failure_ratio <= 0.02` to continue scaling.

2. Publish failure ratio > `3%` in the last 24h.
```bash
.venv/bin/python - <<'PY'
from collections import Counter
from datetime import datetime, timedelta, timezone
from feedops.db.supabase_client import get_client
client = get_client()
cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
events = client.table('publish_events').select('status,published_at').gte('published_at', cutoff).limit(5000).execute().data or []
counts = Counter(e.get('status') for e in events)
total = sum(counts.values())
failed = counts.get('failed',0)
ratio = (failed / total) if total else 0.0
print({'events_24h': total, 'failed_24h': failed, 'publish_failure_ratio_24h': round(ratio,4)})
PY
```
Expected outcome:
- `publish_failure_ratio_24h <= 0.03` to continue publish waves.

3. Review rejection ratio > `25%` in recent approvals.
```bash
.venv/bin/python - <<'PY'
from collections import Counter
from feedops.db.supabase_client import get_client
client = get_client()
rows = client.table('sku_approvals').select('approval_status,updated_at').order('updated_at', desc=True).limit(200).execute().data or []
counts = Counter(r.get('approval_status','unknown') for r in rows)
total = sum(counts.values())
rejected = counts.get('rejected',0)
ratio = (rejected/total) if total else 0.0
print({'rows_considered': total, 'status_counts': dict(counts), 'rejection_rate': round(ratio,4)})
PY
```
Expected outcome:
- `rejection_rate <= 0.25` to keep generation wave size unchanged.

### 3.2 Rollback instructions

1. Identify recent publish history for target SKU/platform.
```bash
.venv/bin/feedops publish-history --limit 3
```
Expected outcome:
- Table output with recent `publish` events and statuses.

2. Preview rollback first (required).
```bash
.venv/bin/feedops rollback --sku FT-16 --platform shopify --dry-run
```
Expected outcome:
- Either a rollback preview (current vs original) or a clear "No patch found" message.

3. Execute rollback (only after preview sign-off).
```bash
.venv/bin/feedops rollback --sku FT-16 --platform shopify
```
Expected outcome:
- Success confirmation, or explicit failure/no-patch message for operator action.

4. Verify rollback/publish snapshot data for auditing.
```bash
.venv/bin/python - <<'PY'
from feedops.db.supabase_client import get_client
client = get_client()
sku='FT-16'
rows = client.table('publish_events').select('id,master_sku,platform,environment,status,published_title,published_description,published_at').eq('master_sku', sku).order('published_at', desc=True).limit(3).execute().data or []
print({'sku': sku, 'events_found': len(rows), 'latest_event': rows[0] if rows else None})
PY
```
Expected outcome:
- Event snapshots available for audit/rollback traceability.

## 4) Dry-Run and Spot-Check Verification Bundle
Run this bundle before each scale increase:

```bash
# 1) Local and pipeline health
curl -sS -o /tmp/feedops_local_health.json -w '%{http_code}\n' http://127.0.0.1:3010/api/health
cat /tmp/feedops_local_health.json | jq '{supabase: .supabase.status, googleAds: .googleAds.status, gmc: .gmc.status, shopify: .shopify.status, googleAnalytics: .googleAnalytics.status}'
set -a; source dashboard/.env.local; set +a; curl -sS "$FEEDOPS_PIPELINE_URL/health" | jq '{status,service,supabase_connected,product_catalog_count}'

# 2) Candidate selection and queue visibility
curl -sS 'http://127.0.0.1:3010/api/sku-selection?count=5&excludeOptimized=true' | jq '{recommended_count: (.recommended|length), using_sample_data, first_sku: .recommended[0].master_sku}'
curl -sS 'http://127.0.0.1:3010/api/sku-selection/jobs' | jq '{job_count: (.jobs|length), latest_status: .jobs[0].status, latest_job_id: .jobs[0].id}'

# 3) Auth guard sanity (non-authenticated write should redirect)
set -a; source dashboard/.env.local; set +a; curl -sS -o /tmp/phase8_local_generate_post.json -w '%{http_code}\n' -X POST http://127.0.0.1:3010/api/sku-selection/generate -H 'Content-Type: application/json' -d '{"skus":["SB-16"],"options":{"titles":true,"descriptions":true,"images":false,"platforms":["google","bing","shopify"],"num_candidates":1}}'
cat /tmp/phase8_local_generate_post.json | head -c 180

# 4) Stop-condition checks
.venv/bin/python - <<'PY'
from feedops.db.supabase_client import get_client
client = get_client()
jobs = client.table('batch_generation_jobs').select('id').order('created_at', desc=True).limit(20).execute().data or []
job_ids = [j['id'] for j in jobs]
failed = total = 0
if job_ids:
    rows = client.table('batch_generation_job_skus').select('status').in_('job_id', job_ids).execute().data or []
    total = len(rows)
    failed = sum(1 for r in rows if r.get('status') == 'failed')
ratio = (failed / total) if total else 0.0
print({'jobs_considered': len(job_ids), 'sku_rows': total, 'failed_rows': failed, 'failure_ratio': round(ratio,4)})
PY
```

Expected outcomes:
- Health checks all pass.
- Candidate and jobs endpoints return non-error JSON.
- Local unauthenticated POST returns redirect semantics (`307` and `/login` body) confirming write-route guard.
- Failure ratio remains below configured stop threshold.
