# Task: Set Up GCP Cloud Run for Python Pipeline

## Objective

Install and configure Google Cloud MCP servers in Claude Code, then deploy the FeedOps Python pipeline to Google Cloud Run for scalable content generation.

## Prerequisites

- GCP project with billing enabled
- `gcloud` CLI installed locally
- Service account with appropriate permissions
- Docker installed (for local container testing)

## CRITICAL: Use Context7 MCP for Documentation

**Before implementing any code**, use the Context7 MCP server to fetch current documentation:

```
# Resolve library IDs first
mcp__plugin_context7_context7__resolve-library-id("fastapi")
mcp__plugin_context7_context7__resolve-library-id("google-cloud-run")
mcp__plugin_context7_context7__resolve-library-id("uvicorn")
mcp__plugin_context7_context7__resolve-library-id("pydantic")

# Then query docs for specific topics
mcp__plugin_context7_context7__query-docs(library_id, "deployment")
mcp__plugin_context7_context7__query-docs(library_id, "async endpoints")
```

Use Context7 for:
- FastAPI async endpoint patterns and best practices
- Google Cloud Run deployment configuration
- Uvicorn production settings
- Pydantic v2 model patterns
- Google Secret Manager integration

## Phase 1: MCP Server Installation

### 1.1 Install gcloud-mcp (Google Cloud SDK MCP)

Repository: https://github.com/googleapis/gcloud-mcp

```bash
# Clone and install
git clone https://github.com/googleapis/gcloud-mcp.git ~/mcp-servers/gcloud-mcp
cd ~/mcp-servers/gcloud-mcp
npm install
npm run build
```

### 1.2 Install cloud-run-mcp (Cloud Run specific)

Repository: https://github.com/GoogleCloudPlatform/cloud-run-mcp

```bash
# Clone and install
git clone https://github.com/GoogleCloudPlatform/cloud-run-mcp.git ~/mcp-servers/cloud-run-mcp
cd ~/mcp-servers/cloud-run-mcp
npm install
npm run build
```

### 1.3 Configure Claude Code MCP Settings

Add to `~/.claude/mcp_servers.json` (or create if doesn't exist):

```json
{
  "mcpServers": {
    "gcloud": {
      "command": "node",
      "args": ["~/mcp-servers/gcloud-mcp/dist/index.js"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/service-account.json"
      }
    },
    "cloud-run": {
      "command": "node",
      "args": ["~/mcp-servers/cloud-run-mcp/dist/index.js"],
      "env": {
        "GOOGLE_CLOUD_PROJECT": "your-project-id",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/service-account.json"
      }
    }
  }
}
```

### 1.4 Verify MCP Installation

After restarting Claude Code:
- Run `/mcp` to list available MCP servers
- Verify gcloud and cloud-run servers appear
- Test a simple command like listing Cloud Run services

## Phase 2: Containerize Python Pipeline

### 2.1 Create Dockerfile

Create `Dockerfile` in repository root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY pyproject.toml .

# Install the package
RUN pip install --no-cache-dir -e .

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the FastAPI server
CMD ["uvicorn", "feedops.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Note**: The `data/` directory is included because `optimize_parent_sku` requires the product catalog CSV.

### 2.2 Create FastAPI Entry Point

Create `src/feedops/api/__init__.py`:

```python
"""FeedOps API module for Cloud Run deployment."""
```

Create `src/feedops/api/main.py`:

```python
"""FastAPI entry point for Cloud Run deployment.

IMPORTANT: This module wraps the existing pipeline functions for HTTP access.
The actual generation logic lives in feedops.pipeline.* modules.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
import os
import logging
from pathlib import Path

from feedops.db.supabase_client import get_supabase_client
from feedops.loaders.unified_loader import load_parent_sku_unified_with_status
from feedops.pipeline.optimize import optimize_parent_sku, OptimizationResult
from feedops.pipeline.generator import generate_candidates, build_prompt
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.prompts import SYSTEM_PROMPT, CANDIDATE_SCHEMA
from feedops.providers import get_provider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default paths
DEFAULT_CATALOG_PATH = Path(os.getenv("CATALOG_PATH", "/app/data/Product Catalog.csv"))

app = FastAPI(
    title="FeedOps Pipeline API",
    description="Content generation pipeline for Allied Brass",
    version="1.0.0"
)


# =============================================================================
# Request/Response Models
# =============================================================================

class OptimizeRequest(BaseModel):
    """Request to optimize a single SKU."""
    master_sku: str = Field(..., description="Master SKU to optimize (e.g., '1051')")
    num_candidates: int = Field(default=3, ge=1, le=10, description="Number of candidates to generate")
    dry_run: bool = Field(default=True, description="If true, don't save to database")


class RegenerateRequest(BaseModel):
    """Request to regenerate specific content with feedback."""
    master_sku: str = Field(..., description="Master SKU")
    content_type: str = Field(..., description="'title' or 'description'")
    platform: str = Field(default="google", description="Target platform: google, bing, shopify")
    feedback: Optional[str] = Field(default=None, description="Human feedback for improvement")
    finish_code: Optional[str] = Field(default=None, description="Specific finish code for variant")


class BatchOptimizeRequest(BaseModel):
    """Request to optimize multiple SKUs."""
    skus: list[str] = Field(..., min_length=1, max_length=100, description="List of master SKUs")
    num_candidates: int = Field(default=1, ge=1, le=5, description="Candidates per SKU")
    dry_run: bool = Field(default=True, description="If true, don't save to database")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    catalog_available: bool
    supabase_connected: bool


class OptimizeResponse(BaseModel):
    """Response from optimization endpoint."""
    success: bool
    master_sku: str
    message: str
    report: Optional[str] = None
    error: Optional[str] = None


class BatchJobResponse(BaseModel):
    """Response from batch optimization endpoint."""
    success: bool
    job_id: str
    status: str
    total_skus: int


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Cloud Run."""
    catalog_ok = DEFAULT_CATALOG_PATH.exists()

    supabase_ok = False
    try:
        supabase = get_supabase_client()
        supabase.table("variant_index").select("id").limit(1).execute()
        supabase_ok = True
    except Exception as e:
        logger.warning(f"Supabase health check failed: {e}")

    return HealthResponse(
        status="healthy" if (catalog_ok and supabase_ok) else "degraded",
        service="feedops-pipeline",
        catalog_available=catalog_ok,
        supabase_connected=supabase_ok
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "FeedOps Pipeline API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "optimize": "POST /optimize-sku",
            "regenerate": "POST /regenerate",
            "batch": "POST /batch-optimize"
        }
    }


# =============================================================================
# Single SKU Optimization
# =============================================================================

@app.post("/optimize-sku", response_model=OptimizeResponse)
async def optimize_single_sku(request: OptimizeRequest):
    """
    Optimize a single SKU - generates titles, descriptions for all platforms.

    This endpoint wraps the full optimization pipeline:
    1. Load product data from catalog
    2. Build evidence table
    3. Generate candidates via LLM
    4. Verify claims
    5. Save results (if not dry_run)
    """
    try:
        logger.info(f"Optimizing SKU: {request.master_sku}")

        if not DEFAULT_CATALOG_PATH.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Catalog not found at {DEFAULT_CATALOG_PATH}"
            )

        result: OptimizationResult = await optimize_parent_sku(
            master_sku=request.master_sku,
            catalog_path=DEFAULT_CATALOG_PATH,
            dry_run=request.dry_run,
            num_candidates=request.num_candidates,
        )

        return OptimizeResponse(
            success=True,
            master_sku=request.master_sku,
            message=f"Generated {request.num_candidates} candidates",
            report=result.report if hasattr(result, 'report') else None
        )

    except FileNotFoundError as e:
        logger.error(f"SKU not found: {request.master_sku} - {e}")
        raise HTTPException(status_code=404, detail=f"SKU not found: {request.master_sku}")
    except Exception as e:
        logger.error(f"Optimization failed for {request.master_sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Content Regeneration (with feedback)
# =============================================================================

@app.post("/regenerate")
async def regenerate_content(request: RegenerateRequest):
    """
    Regenerate specific content with optional human feedback.

    This endpoint is designed to match the TypeScript dashboard's regeneration
    functionality but uses the Python pipeline's comprehensive prompts.
    """
    try:
        logger.info(f"Regenerating {request.content_type} for SKU: {request.master_sku}")

        # Load product data
        parent_sku, data_source = load_parent_sku_unified_with_status(
            request.master_sku,
            catalog_path=DEFAULT_CATALOG_PATH
        )

        if not parent_sku:
            raise HTTPException(status_code=404, detail=f"SKU not found: {request.master_sku}")

        # Build evidence table
        evidence = build_evidence_table(parent_sku)
        evidence_markdown = format_evidence_markdown(evidence)

        # Get LLM provider
        llm = get_provider()

        # Build prompt with feedback if provided
        system_prompt = SYSTEM_PROMPT
        user_prompt = f"""
{evidence_markdown}

Target platform: {request.platform}
Content type to generate: {request.content_type}

{"FEEDBACK FROM REVIEWER:" + chr(10) + request.feedback if request.feedback else ""}

Generate only the {request.content_type} for {request.platform}.
Return as plain text, not JSON.
"""

        # Call LLM
        response = await llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1000 if request.content_type == "description" else 200,
            temperature=0.7
        )

        content = response.content.strip()

        # Save to Supabase
        supabase = get_supabase_client()

        # Log to regeneration_history
        supabase.table("regeneration_history").insert({
            "master_sku": request.master_sku,
            "content_type": request.content_type,
            "platform": request.platform,
            "mode": "with_feedback" if request.feedback else "simple",
            "feedback_text": request.feedback,
            "new_content": content,
            "model_version": llm.model_name if hasattr(llm, 'model_name') else "unknown",
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }).execute()

        return {
            "success": True,
            "content": content,
            "master_sku": request.master_sku,
            "content_type": request.content_type,
            "platform": request.platform,
            "used_feedback": request.feedback is not None
        }

    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Batch Optimization
# =============================================================================

@app.post("/batch-optimize", response_model=BatchJobResponse)
async def batch_optimize(
    request: BatchOptimizeRequest,
    background_tasks: BackgroundTasks
):
    """
    Queue batch optimization job for multiple SKUs.

    Creates a job record in Supabase and processes SKUs in the background.
    Use GET /batch-status/{job_id} to check progress.
    """
    try:
        supabase = get_supabase_client()

        # Create job in Supabase (using existing table from migration 006)
        job_result = supabase.table("batch_generation_jobs").insert({
            "status": "queued",
            "total_skus": len(request.skus),
            "completed_skus": 0,
            "failed_skus": 0,
            "options": {
                "num_candidates": request.num_candidates,
                "dry_run": request.dry_run
            }
        }).execute()

        job_id = job_result.data[0]["id"]

        # Create individual SKU records
        sku_records = [
            {"job_id": job_id, "master_sku": sku, "status": "pending"}
            for sku in request.skus
        ]
        supabase.table("batch_generation_job_skus").insert(sku_records).execute()

        # Queue background processing
        background_tasks.add_task(
            process_batch_job,
            job_id=job_id,
            skus=request.skus,
            num_candidates=request.num_candidates,
            dry_run=request.dry_run
        )

        return BatchJobResponse(
            success=True,
            job_id=job_id,
            status="queued",
            total_skus=len(request.skus)
        )

    except Exception as e:
        logger.error(f"Batch job creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batch-status/{job_id}")
async def get_batch_status(job_id: str):
    """Get status of a batch optimization job."""
    try:
        supabase = get_supabase_client()

        job = supabase.table("batch_generation_jobs").select("*").eq("id", job_id).single().execute()

        if not job.data:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        # Get SKU-level details
        skus = supabase.table("batch_generation_job_skus").select("*").eq("job_id", job_id).execute()

        return {
            "job": job.data,
            "skus": skus.data
        }

    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_batch_job(
    job_id: str,
    skus: list[str],
    num_candidates: int,
    dry_run: bool
):
    """Background task to process batch optimization."""
    supabase = get_supabase_client()

    # Update job status to processing
    supabase.table("batch_generation_jobs").update({
        "status": "processing",
        "started_at": "now()"
    }).eq("id", job_id).execute()

    completed = 0
    failed = 0

    for sku in skus:
        try:
            # Update SKU status
            supabase.table("batch_generation_job_skus").update({
                "status": "processing",
                "started_at": "now()"
            }).eq("job_id", job_id).eq("master_sku", sku).execute()

            # Run optimization
            await optimize_parent_sku(
                master_sku=sku,
                catalog_path=DEFAULT_CATALOG_PATH,
                dry_run=dry_run,
                num_candidates=num_candidates,
            )

            completed += 1

            # Update SKU as completed
            supabase.table("batch_generation_job_skus").update({
                "status": "completed",
                "completed_at": "now()"
            }).eq("job_id", job_id).eq("master_sku", sku).execute()

        except Exception as e:
            failed += 1
            logger.error(f"Batch SKU {sku} failed: {e}")

            # Update SKU as failed
            supabase.table("batch_generation_job_skus").update({
                "status": "failed",
                "error_message": str(e),
                "completed_at": "now()"
            }).eq("job_id", job_id).eq("master_sku", sku).execute()

        # Update job progress
        supabase.table("batch_generation_jobs").update({
            "completed_skus": completed,
            "failed_skus": failed
        }).eq("id", job_id).execute()

    # Mark job complete
    final_status = "completed" if failed == 0 else ("failed" if completed == 0 else "completed")
    supabase.table("batch_generation_jobs").update({
        "status": final_status,
        "completed_at": "now()"
    }).eq("id", job_id).execute()

    logger.info(f"Batch job {job_id} finished: {completed} completed, {failed} failed")
```

### 2.3 Add FastAPI Dependencies

Add to `requirements.txt`:

```
fastapi>=0.109.0
uvicorn>=0.27.0
python-multipart>=0.0.6
```

### 2.4 Create .dockerignore

```
.git
.venv
venv
__pycache__
*.pyc
.env
.env.*
node_modules
dashboard/
tests/
docs/
*.md
.pytest_cache
.mypy_cache
*.bundle
supabase/.temp/
test_output/
```

### 2.5 Verify Python Pipeline Functions

Before proceeding, verify the pipeline functions work locally:

```bash
# Activate virtual environment
source .venv/bin/activate

# Test that imports work
PYTHONPATH=./src python -c "
from feedops.pipeline.optimize import optimize_parent_sku
from feedops.pipeline.generator import generate_candidates
from feedops.loaders.unified_loader import load_parent_sku_unified_with_status
from feedops.providers import get_provider
print('All imports successful')
"

# Run existing tests
PYTHONPATH=./src python -m pytest tests/ -v --tb=short
```

## Phase 3: Deploy to Cloud Run

### 3.1 Build and Push Container

```bash
# Set project variables
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export SERVICE_NAME="feedops-pipeline"

# Build container using Cloud Build (recommended)
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Or build locally then push
docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME .
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME
```

### 3.2 Deploy to Cloud Run

```bash
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10 \
  --set-env-vars "OPENAI_API_KEY=your-key" \
  --set-env-vars "GEMINI_API_KEY=your-key" \
  --set-env-vars "SUPABASE_URL=your-url" \
  --set-env-vars "SUPABASE_SERVICE_KEY=your-key" \
  --allow-unauthenticated  # Or use IAM for auth
```

### 3.3 Store Secrets in Secret Manager (Recommended)

```bash
# Create secrets
echo -n "your-openai-key" | gcloud secrets create openai-api-key --data-file=-
echo -n "your-gemini-key" | gcloud secrets create gemini-api-key --data-file=-
echo -n "your-supabase-url" | gcloud secrets create supabase-url --data-file=-
echo -n "your-supabase-key" | gcloud secrets create supabase-service-key --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Repeat for other secrets...

# Deploy with secrets
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --set-secrets "OPENAI_API_KEY=openai-api-key:latest" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" \
  --set-secrets "SUPABASE_URL=supabase-url:latest" \
  --set-secrets "SUPABASE_SERVICE_KEY=supabase-service-key:latest"
```

## Phase 4: Connect Dashboard to Cloud Run

### 4.1 Add Cloud Run URL to Dashboard Environment

Add to `dashboard/.env.local`:

```
FEEDOPS_PIPELINE_URL=https://feedops-pipeline-xxxxx-uc.a.run.app
```

Add to Vercel environment variables for production.

### 4.2 Create Pipeline Client Library

Create `dashboard/src/lib/pipeline-client.ts`:

```typescript
/**
 * Client for calling the FeedOps Python pipeline on Cloud Run.
 *
 * Use this when you want to use the Python pipeline's comprehensive prompts
 * instead of the TypeScript implementation.
 */

const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

export interface OptimizeRequest {
  master_sku: string
  num_candidates?: number
  dry_run?: boolean
}

export interface RegenerateRequest {
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  feedback?: string
  finish_code?: string
}

export interface BatchOptimizeRequest {
  skus: string[]
  num_candidates?: number
  dry_run?: boolean
}

export class PipelineClient {
  private baseUrl: string

  constructor() {
    if (!PIPELINE_URL) {
      throw new Error('FEEDOPS_PIPELINE_URL environment variable not set')
    }
    this.baseUrl = PIPELINE_URL
  }

  async health(): Promise<{
    status: string
    catalog_available: boolean
    supabase_connected: boolean
  }> {
    const response = await fetch(`${this.baseUrl}/health`)
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`)
    }
    return response.json()
  }

  async optimizeSku(request: OptimizeRequest): Promise<{
    success: boolean
    master_sku: string
    message: string
    report?: string
  }> {
    const response = await fetch(`${this.baseUrl}/optimize-sku`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || response.statusText)
    }

    return response.json()
  }

  async regenerate(request: RegenerateRequest): Promise<{
    success: boolean
    content: string
    master_sku: string
    content_type: string
    platform: string
  }> {
    const response = await fetch(`${this.baseUrl}/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || response.statusText)
    }

    return response.json()
  }

  async batchOptimize(request: BatchOptimizeRequest): Promise<{
    success: boolean
    job_id: string
    status: string
    total_skus: number
  }> {
    const response = await fetch(`${this.baseUrl}/batch-optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || response.statusText)
    }

    return response.json()
  }

  async getBatchStatus(jobId: string): Promise<{
    job: Record<string, unknown>
    skus: Array<Record<string, unknown>>
  }> {
    const response = await fetch(`${this.baseUrl}/batch-status/${jobId}`)

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || response.statusText)
    }

    return response.json()
  }
}

// Singleton instance
let _client: PipelineClient | null = null

export function getPipelineClient(): PipelineClient {
  if (!_client) {
    _client = new PipelineClient()
  }
  return _client
}

export function isPipelineConfigured(): boolean {
  return !!PIPELINE_URL
}
```

### 4.3 Update Regenerate Route (Optional Cloud Run Mode)

Modify `dashboard/src/app/api/regenerate/route.ts` to support Cloud Run:

```typescript
// Add at top of file
import { isPipelineConfigured, getPipelineClient } from '@/lib/pipeline-client'

// Add option to use Cloud Run
const USE_CLOUD_RUN = process.env.FEEDOPS_USE_CLOUD_RUN === '1'

// In the POST handler, add early in the function:
if (USE_CLOUD_RUN && isPipelineConfigured()) {
  try {
    const client = getPipelineClient()
    const result = await client.regenerate({
      master_sku,
      content_type,
      platform,
      feedback: feedback?.user_feedback,
      finish_code: feedback?.finish
    })

    return NextResponse.json({
      success: true,
      content: result.content,
      version: 1,
      mode,
      model: 'cloud-run-python',
      used_cloud_run: true
    })
  } catch (error) {
    console.error('Cloud Run regeneration failed, falling back to local:', error)
    // Fall through to local implementation
  }
}

// ... rest of existing implementation as fallback
```

## Phase 5: Testing & Verification

### 5.1 Local Container Testing

```bash
# Build locally
docker build -t feedops-pipeline .

# Run locally with environment variables
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e SUPABASE_URL=$SUPABASE_URL \
  -e SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY \
  feedops-pipeline

# Test health endpoint
curl http://localhost:8080/health

# Test root endpoint
curl http://localhost:8080/

# Test optimize endpoint
curl -X POST http://localhost:8080/optimize-sku \
  -H "Content-Type: application/json" \
  -d '{"master_sku": "1051", "num_candidates": 1, "dry_run": true}'

# Test regenerate endpoint
curl -X POST http://localhost:8080/regenerate \
  -H "Content-Type: application/json" \
  -d '{"master_sku": "1051", "content_type": "description", "platform": "google"}'
```

### 5.2 Cloud Run Verification

```bash
# Get service URL
gcloud run services describe feedops-pipeline --region=$REGION --format='value(status.url)'

# Test health
curl https://feedops-pipeline-xxxxx-uc.a.run.app/health

# Check logs
gcloud run logs read feedops-pipeline --region=$REGION --limit=50
```

### 5.3 Dashboard Integration Test

1. Update dashboard `.env.local` with Cloud Run URL
2. Set `FEEDOPS_USE_CLOUD_RUN=1` to enable Cloud Run mode
3. Run dashboard locally: `cd dashboard && npm run dev`
4. Navigate to a SKU review page
5. Click "Regenerate" and verify it calls Cloud Run
6. Check Cloud Run logs to confirm request received

## Success Criteria

1. [ ] gcloud-mcp server installed and responding in Claude Code
2. [ ] cloud-run-mcp server installed and responding in Claude Code
3. [ ] Context7 MCP used for FastAPI/GCP documentation lookup
4. [ ] Dockerfile builds successfully
5. [ ] Container runs locally and responds to `/health`
6. [ ] All endpoints respond correctly:
   - [ ] GET `/` - API info
   - [ ] GET `/health` - Health check with catalog/supabase status
   - [ ] POST `/optimize-sku` - Single SKU optimization
   - [ ] POST `/regenerate` - Content regeneration
   - [ ] POST `/batch-optimize` - Batch job creation
   - [ ] GET `/batch-status/{job_id}` - Batch job status
7. [ ] Container deployed to Cloud Run
8. [ ] Secrets stored in Secret Manager (not in plain env vars)
9. [ ] Dashboard can call Cloud Run endpoints
10. [ ] Batch generation jobs tracked in `batch_generation_jobs` table
11. [ ] Logs visible in Cloud Run console

## Cost Monitoring

Set up budget alerts:

```bash
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="FeedOps Cloud Run" \
  --budget-amount=50USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90
```

## Rollback Plan

If issues occur:

```bash
# List revisions
gcloud run revisions list --service=feedops-pipeline --region=$REGION

# Rollback to previous revision
gcloud run services update-traffic feedops-pipeline \
  --region=$REGION \
  --to-revisions=feedops-pipeline-00001-abc=100
```

## Next Steps After Deployment

After Cloud Run is deployed, proceed to **Prompt 21 (Unify Content Generation Methodology)** to:
1. Compare TypeScript vs Python prompt quality
2. Decide on unified architecture
3. Potentially have TypeScript call Cloud Run for all generation
