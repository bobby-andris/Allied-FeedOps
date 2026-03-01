# Hybrid Generation Architecture Decision

> Historical reference only. This document captures an earlier hybrid-routing decision and is not the complete current runtime contract.
>
> Canonical sources:
> - `AGENTS.md`
> - `docs/architecture/generation-runtime-truth.md`
> - `docs/architecture/generation-core-task-model.md`
> - `docs/experiments/2026-02-28-production-divergence-closure/report.md`

**Date:** 2026-02-08
**Status:** ✅ Cloud Run Implementation Only

## Decision: Always Use Cloud Run Python Implementation

**The TypeScript dashboard implementation at `/api/sku-selection/generate-hybrid` should be deprecated.**

All hybrid generation should use the Cloud Run Python pipeline via the `pipeline-client.ts`:

```typescript
import { getPipelineClient } from '@/lib/pipeline-client'

const client = getPipelineClient()
const result = await client.hybridGenerate({
  skus: ['920-6', 'CL-28-18', ...],
  options: {
    titles: true,
    descriptions: true,
    platforms: ['google', 'bing', 'shopify']
  }
})

// Poll for completion
const status = await client.waitForBatchCompletion(result.job_id, {
  onProgress: (status) => console.log(`${status.completed_skus}/${status.total_skus}`)
})
```

## Why Cloud Run Only?

### 1. No Timeout Limits

**Problem:** Vercel serverless timeout limits make large batches impossible
- Pro: 60 seconds
- Enterprise: 15 minutes
- **Real failure:** 51 SKUs failed after 25 minutes with 0 completions

**Cloud Run:** No timeout limits
- Can process any batch size
- 641 families with missing content = ~2,000 SKUs possible

### 2. Better Infrastructure

**Cloud Run:**
- ✅ Designed for long-running batch operations
- ✅ Background job processing with FastAPI BackgroundTasks
- ✅ Job tracking in `batch_generation_jobs` table
- ✅ Progress updates during execution
- ✅ Monitoring via Cloud Run logs

**Vercel:**
- ❌ Designed for request-response cycles
- ❌ No job tracking (function times out)
- ❌ Limited observability

### 3. Single Source of Truth

**Before:** Two implementations to maintain
- TypeScript in `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts`
- Python in `src/feedops/api/hybrid_generation.py`
- Risk of drift, duplicate effort

**After:** One implementation
- Python in Cloud Run
- Dashboard just calls Cloud Run API
- Easier to maintain, test, and improve

### 4. Same Quality & Cost

**No trade-offs:**
- ✅ Same 60% cost savings for variants (temperature 0.6 vs 0.7)
- ✅ Same detection algorithm (product_id grouping)
- ✅ Same adaptation prompts
- ✅ Same database tagging (`{model}-variant-adaptation`)

## Implementation

### Cloud Run Endpoint

**POST** `/hybrid-generate`

```json
{
  "skus": ["920-6", "CL-28-18", ...],
  "options": {
    "titles": true,
    "descriptions": true,
    "platforms": ["google", "bing", "shopify"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "uuid",
  "status": "queued",
  "total_skus": 16,
  "multi_sku_families": 12,
  "single_skus": 4,
  "strategy": {
    "base_skus": 16,
    "variant_skus": 35
  }
}
```

### Dashboard Client

**Location:** `dashboard/src/lib/pipeline-client.ts`

```typescript
export interface HybridGenerateRequest {
  skus: string[]
  options: {
    titles: boolean
    descriptions: boolean
    platforms: ('google' | 'bing' | 'shopify')[]
  }
}

export interface HybridJobResponse {
  success: boolean
  job_id: string
  status: string
  total_skus: number
  multi_sku_families: number
  single_skus: number
  strategy: {
    base_skus: number
    variant_skus: number
  }
}

class PipelineClient {
  async hybridGenerate(request: HybridGenerateRequest): Promise<HybridJobResponse> {
    const response = await fetch(`${this.baseUrl}/hybrid-generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skus: request.skus, options: request.options }),
    })
    return response.json()
  }

  async waitForBatchCompletion(
    jobId: string,
    options?: { onProgress?: (status: BatchStatusResponse) => void }
  ): Promise<BatchStatusResponse> {
    // Polls /batch-status/{job_id} until completed
  }
}
```

## Migration Path

### Step 1: Update Dashboard Pages (Immediate)

**Change any code calling the dashboard endpoint:**

```typescript
// ❌ OLD - TypeScript dashboard (times out)
const response = await fetch('/api/sku-selection/generate-hybrid', {
  method: 'POST',
  body: JSON.stringify({ skus, options })
})

// ✅ NEW - Cloud Run Python (no timeout)
import { getPipelineClient } from '@/lib/pipeline-client'

const client = getPipelineClient()
const result = await client.hybridGenerate({ skus, options })

// Poll for completion
const status = await client.waitForBatchCompletion(result.job_id, {
  onProgress: (status) => {
    console.log(`Progress: ${status.completed_skus}/${status.total_skus}`)
  }
})
```

### Step 2: Deprecate TypeScript Endpoint (Soon)

**Mark as deprecated:**

```typescript
// dashboard/src/app/api/sku-selection/generate-hybrid/route.ts

/**
 * @deprecated Use Cloud Run Python implementation via pipeline-client.ts instead
 * This endpoint times out on large batches (>50 SKUs). See docs/architecture/hybrid-generation-architecture.md
 */
export async function POST(request: NextRequest) {
  return NextResponse.json(
    { error: 'This endpoint is deprecated. Use /hybrid-generate on Cloud Run instead.' },
    { status: 410 } // 410 Gone
  )
}
```

### Step 3: Remove TypeScript Implementation (Later)

Once all dashboard pages use Cloud Run:

```bash
# Remove deprecated files
rm dashboard/src/app/api/sku-selection/generate-hybrid/route.ts
rm dashboard/src/lib/multi-sku-detection.ts

# Keep only the Cloud Run client
# dashboard/src/lib/pipeline-client.ts
```

## Testing

### Test with Real Batch (16 Families, 51 SKUs)

```bash
bash /tmp/backfill-test.sh
```

Expected:
- ✅ Returns job_id immediately
- ✅ Processes in background (15-25 minutes)
- ✅ No timeout errors
- ✅ All 51 SKUs have content generated

### Verify Model Version

```sql
SELECT generation_model, COUNT(*)
FROM generated_content
WHERE master_sku IN (
  '920-6', 'CL-28-18', 'MA-21/18', 'P-200-18-TB', 'QN-31/18', '102', 'TS-25', '2016',
  'CL-41-18', 'CV-407-12SM', 'RC-5/16TB', 'CL-5-16', 'WP-1TB/16', 'WP-2TB/16-GAL', 'WP-1/16', 'NS-5/16'
)
AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY generation_model;

-- Expected:
-- gpt-5.2                      (base SKUs)
-- gpt-5.2-variant-adaptation   (variant SKUs)
```

## Model Configuration

**Default:** `gpt-5.2` (matches rest of codebase)

**Environment variable override:** `OPENAI_MODEL=gpt-5.2-flash` (if needed)

**Code location:**
```python
# src/feedops/api/hybrid_generation.py line 212
model = os.getenv("OPENAI_MODEL", "gpt-5.2")
```

**Consistency:**
- `src/feedops/providers/openai_provider.py:27` defaults to `gpt-5.2`
- `dashboard/src/lib/regeneration/core.ts:41` defaults to `gpt-5.2`
- All aligned on same model

## Monitoring

**Cloud Run logs:**
```bash
gcloud run services logs read feedops-pipeline \
  --project=bobbys-project-346400 \
  --limit=100
```

**Job status:**
```bash
curl "$FEEDOPS_PIPELINE_URL/batch-status/{job_id}"
```

**Database metrics:**
```sql
-- Recent hybrid jobs
SELECT
  id,
  status,
  total_skus,
  completed_skus,
  failed_skus,
  options->>'hybrid' as is_hybrid,
  EXTRACT(EPOCH FROM (completed_at - started_at)) / 60 as duration_minutes
FROM batch_generation_jobs
WHERE options->>'hybrid' = 'true'
ORDER BY created_at DESC
LIMIT 10;
```

## Cost Analysis

**Example batch: 51 SKUs (16 base + 35 variants)**

**Without hybrid (full generation for all):**
- 51 SKUs × 3 platforms × 2 types = 306 full generations
- Temperature: 0.7 (higher cost)
- Estimated cost: $X (baseline)

**With hybrid (base + variant adaptation):**
- 16 base SKUs × 3 platforms × 2 types = 96 full generations (0.7 temp)
- 35 variant SKUs × 3 platforms × 2 types = 210 adaptations (0.6 temp)
- Variant adaptations are ~60% cheaper (focused prompts, lower temp)
- Estimated cost: $X × 0.6 = 40% savings

**Savings scale with catalog:**
- 641 families with missing content
- ~1,892 total missing SKUs
- If average 3 variants per family: ~1,200 variants
- 40% cost savings on 1,200 SKUs = significant reduction

## References

**Implementation:**
- `src/feedops/api/multi_sku_detection.py` - Detection logic
- `src/feedops/api/hybrid_generation.py` - Adaptation logic
- `src/feedops/api/main.py` - `/hybrid-generate` endpoint
- `dashboard/src/lib/pipeline-client.ts` - Dashboard client

**Documentation:**
- `docs/audit/hybrid-generation-cloud-run-2026-02-08.md` - Implementation details
- `docs/architecture/content-generation-hybrid.md` - Hybrid strategy explanation

**Testing:**
- `/tmp/backfill-test.sh` - Test script
- `/tmp/hybrid-generation-verification.sql` - Verification queries

**Deprecated (to be removed):**
- `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts` - TypeScript endpoint
- `dashboard/src/lib/multi-sku-detection.ts` - TypeScript detection (duplicates Python)

## Summary

**Decision:** Always use Cloud Run Python implementation for hybrid generation.

**Why:**
1. ✅ No timeout limits (handles any batch size)
2. ✅ Better infrastructure (designed for long-running jobs)
3. ✅ Single source of truth (easier to maintain)
4. ✅ Same quality and cost savings

**Action:** Update dashboard pages to use `getPipelineClient().hybridGenerate()` instead of calling `/api/sku-selection/generate-hybrid`.

**Next:** Test with real batch, then deprecate TypeScript implementation.
