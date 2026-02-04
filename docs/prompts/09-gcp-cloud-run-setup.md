# Task: Set Up GCP Cloud Run for Python Pipeline

## Objective

Install and configure Google Cloud MCP servers in Claude Code, then deploy the FeedOps Python pipeline to Google Cloud Run for scalable content generation.

## Prerequisites

- GCP project with billing enabled
- `gcloud` CLI installed locally
- Service account with appropriate permissions
- Docker installed (for local container testing)

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

### 2.2 Create FastAPI Entry Point

Create `src/feedops/api/main.py`:

```python
"""FastAPI entry point for Cloud Run deployment."""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os

from feedops.pipeline.optimize import optimize_sku
from feedops.pipeline.generator import generate_candidates
from feedops.db.supabase_client import get_supabase_client

app = FastAPI(
    title="FeedOps Pipeline API",
    description="Content generation pipeline for Allied Brass",
    version="1.0.0"
)

class OptimizeRequest(BaseModel):
    master_sku: str
    platforms: list[str] = ["google", "shopify", "bing"]
    num_candidates: int = 3

class RegenerateRequest(BaseModel):
    master_sku: str
    content_type: str  # "title" or "description"
    feedback: Optional[str] = None
    platform: str = "google"

class BatchOptimizeRequest(BaseModel):
    skus: list[str]
    platforms: list[str] = ["google", "shopify", "bing"]
    num_candidates: int = 3

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy", "service": "feedops-pipeline"}

@app.post("/optimize-sku")
async def optimize_single_sku(request: OptimizeRequest):
    """Optimize a single SKU - generates titles, descriptions, images."""
    try:
        result = await optimize_sku(
            master_sku=request.master_sku,
            platforms=request.platforms,
            num_candidates=request.num_candidates
        )
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/regenerate")
async def regenerate_content(request: RegenerateRequest):
    """Regenerate specific content with feedback."""
    try:
        result = await generate_candidates(
            master_sku=request.master_sku,
            content_type=request.content_type,
            feedback=request.feedback,
            platform=request.platform
        )
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch-optimize")
async def batch_optimize(
    request: BatchOptimizeRequest,
    background_tasks: BackgroundTasks
):
    """Queue batch optimization job."""
    # Create job in Supabase
    supabase = get_supabase_client()
    job = supabase.table("generation_jobs").insert({
        "status": "queued",
        "total_skus": len(request.skus),
        "options": {
            "platforms": request.platforms,
            "num_candidates": request.num_candidates
        }
    }).execute()

    job_id = job.data[0]["id"]

    # Queue background processing
    background_tasks.add_task(
        process_batch_job,
        job_id=job_id,
        skus=request.skus,
        platforms=request.platforms,
        num_candidates=request.num_candidates
    )

    return {
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "total_skus": len(request.skus)
    }

async def process_batch_job(job_id: str, skus: list, platforms: list, num_candidates: int):
    """Background task to process batch optimization."""
    supabase = get_supabase_client()

    # Update job status
    supabase.table("generation_jobs").update({
        "status": "processing"
    }).eq("id", job_id).execute()

    completed = 0
    failed = 0

    for sku in skus:
        try:
            await optimize_sku(sku, platforms, num_candidates)
            completed += 1
        except Exception as e:
            failed += 1
            # Log error for this SKU
            supabase.table("generation_job_skus").insert({
                "job_id": job_id,
                "master_sku": sku,
                "status": "failed",
                "error_message": str(e)
            }).execute()

        # Update progress
        supabase.table("generation_jobs").update({
            "completed_skus": completed,
            "failed_skus": failed
        }).eq("id", job_id).execute()

    # Mark complete
    supabase.table("generation_jobs").update({
        "status": "completed",
        "completed_at": "now()"
    }).eq("id", job_id).execute()
```

### 2.3 Add FastAPI Dependencies

Add to `requirements.txt`:

```
fastapi>=0.109.0
uvicorn>=0.27.0
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
```

## Phase 3: Deploy to Cloud Run

### 3.1 Build and Push Container

```bash
# Set project
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export SERVICE_NAME="feedops-pipeline"

# Build container
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Or use Docker locally then push
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

### 4.2 Update Dashboard API Routes

Modify `/api/regenerate/route.ts` to optionally call Cloud Run:

```typescript
const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

async function callPipeline(endpoint: string, body: object) {
  if (!PIPELINE_URL) {
    throw new Error('FEEDOPS_PIPELINE_URL not configured')
  }

  const response = await fetch(`${PIPELINE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    throw new Error(`Pipeline error: ${response.statusText}`)
  }

  return response.json()
}
```

### 4.3 Update Batch Generation to Use Cloud Run

The `/api/sku-selection/generate` route should call Cloud Run for batch processing.

## Phase 5: Database Migrations

### 5.1 Apply Generation Jobs Tables

Create `supabase/migrations/006_generation_jobs.sql`:

```sql
-- Generation jobs table for batch processing
CREATE TABLE IF NOT EXISTS generation_jobs (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  status text DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
  total_skus integer NOT NULL,
  completed_skus integer DEFAULT 0,
  failed_skus integer DEFAULT 0,
  options jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  error_message text
);

-- Individual SKU tracking within a job
CREATE TABLE IF NOT EXISTS generation_job_skus (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  job_id uuid REFERENCES generation_jobs(id) ON DELETE CASCADE,
  master_sku text NOT NULL,
  status text DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  error_message text,
  created_at timestamptz DEFAULT now()
);

-- Index for job lookups
CREATE INDEX IF NOT EXISTS idx_generation_job_skus_job_id ON generation_job_skus(job_id);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_status ON generation_jobs(status);
```

### 5.2 Apply Migration

```bash
supabase db push
# Or via Supabase dashboard SQL editor
```

## Phase 6: Testing & Verification

### 6.1 Local Container Testing

```bash
# Build locally
docker build -t feedops-pipeline .

# Run locally
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e SUPABASE_URL=$SUPABASE_URL \
  -e SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY \
  feedops-pipeline

# Test health endpoint
curl http://localhost:8080/health

# Test optimize endpoint
curl -X POST http://localhost:8080/optimize-sku \
  -H "Content-Type: application/json" \
  -d '{"master_sku": "1051", "platforms": ["google"]}'
```

### 6.2 Cloud Run Verification

```bash
# Get service URL
gcloud run services describe feedops-pipeline --region=$REGION --format='value(status.url)'

# Test health
curl https://feedops-pipeline-xxxxx-uc.a.run.app/health

# Check logs
gcloud run logs read feedops-pipeline --region=$REGION --limit=50
```

### 6.3 Dashboard Integration Test

1. Update dashboard `.env.local` with Cloud Run URL
2. Run dashboard locally: `cd dashboard && npm run dev`
3. Navigate to a SKU review page
4. Click "Regenerate" and verify it calls Cloud Run
5. Check Cloud Run logs to confirm request received

## Success Criteria

1. [ ] gcloud-mcp server installed and responding in Claude Code
2. [ ] cloud-run-mcp server installed and responding in Claude Code
3. [ ] Dockerfile builds successfully
4. [ ] Container runs locally and responds to `/health`
5. [ ] Container deployed to Cloud Run
6. [ ] Secrets stored in Secret Manager (not in plain env vars)
7. [ ] Dashboard can call Cloud Run endpoints
8. [ ] Batch generation jobs tracked in `generation_jobs` table
9. [ ] Logs visible in Cloud Run console

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
