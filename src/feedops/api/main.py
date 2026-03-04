"""FastAPI entry point for Cloud Run deployment.

This module exposes the FeedOps Python pipeline as HTTP endpoints,
enabling the Next.js dashboard to call Python-based content generation.

Endpoints:
- GET / - API info
- GET /health - Health check with Supabase status
- POST /optimize-sku - Single SKU optimization
- POST /regenerate - Content regeneration with feedback
- POST /batch-optimize - Batch job creation
- GET /batch-status/{job_id} - Batch job progress
- POST /hybrid-generate - Hybrid multi-SKU batch generation
- POST /performance/capture-baseline - Capture performance baselines for SKUs
- GET /performance/baseline/{master_sku} - Get baseline status for SKU
- POST /performance/collect-daily - Collect durable daily performance snapshots
- POST /performance/compute-impact - Compute persisted diff-in-diff impact scores
- GET /performance/impact-scores - Read persisted impact scorecards
- POST /performance/capture-snapshot - Backward-compatible collector alias
- POST /search-insights/sync - Sync search terms from Google Ads
- GET /search-insights/sync/{job_id} - Get search term sync status
- POST /backfill/start - Create and start a backfill job
- GET /backfill/status/{job_id} - Get backfill job progress
- POST /backfill/resume/{job_id} - Resume failed/partial job
- GET /backfill/jobs - List backfill jobs
- POST /score-intent - Score search queries for feed alignment

Route handlers live in feedops.api.routes (DECOMP-09, Plan 03-02).
This module contains only: lifespan, app creation, middleware, and router mounts.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from feedops.api.env_contract import (
    RuntimeEnvContractError,
    validate_runtime_env_contract,
)
from feedops.observability import request_context
from feedops.observability.metrics import metrics_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# API version
API_VERSION = "1.0.0"


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    """Fail fast on missing runtime env contract requirements."""
    try:
        validate_runtime_env_contract()
    except RuntimeEnvContractError as exc:
        logger.error(str(exc))
        raise RuntimeError(str(exc)) from exc

    # Recover stale jobs left behind by container restarts
    try:
        from feedops.db.supabase_client import get_client
        from datetime import datetime, timezone, timedelta
        sb = get_client()
        stale_cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        stale = sb.table("batch_generation_jobs") \
            .select("id") \
            .eq("status", "processing") \
            .lt("created_at", stale_cutoff) \
            .execute()
        for row in (stale.data or []):
            sb.table("batch_generation_jobs").update({
                "status": "failed",
                "error_message": "Recovered: container restart during processing",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).execute()
            logger.warning("Recovered stale job %s", row["id"])
    except Exception as recovery_err:
        logger.error("Startup recovery sweep failed: %s", recovery_err)

    yield


app = FastAPI(
    title="FeedOps Pipeline API",
    description="Content generation pipeline for Allied Brass products",
    version=API_VERSION,
    lifespan=_app_lifespan,
)

# CORS middleware — allow dashboard to call Cloud Run endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://allied-feed-ops.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus /metrics endpoint (MON-10)
from prometheus_client import make_asgi_app, REGISTRY  # noqa: E402
metrics_app = make_asgi_app(registry=REGISTRY)
app.mount("/metrics", metrics_app)

# Include search insights router
from feedops.api.search_insights import router as search_insights_router  # noqa: E402
app.include_router(search_insights_router)

# Include monitoring router
from feedops.api.monitoring import router as monitoring_router  # noqa: E402
app.include_router(monitoring_router)

# Include GMC sync router
from feedops.api.gmc_sync import router as gmc_sync_router  # noqa: E402
app.include_router(gmc_sync_router)

# Include performance baseline router
from feedops.api.performance_baseline import router as performance_baseline_router  # noqa: E402
app.include_router(performance_baseline_router)

# Include intent scoring router
from feedops.api.intent_scoring import router as intent_scoring_router  # noqa: E402
app.include_router(intent_scoring_router)

# Include all main route handlers (extracted in DECOMP-09 Plan 03-02)
from feedops.api.routes import router as main_router  # noqa: E402
app.include_router(main_router)


@app.middleware("http")
async def attach_request_context(request: Request, call_next):
    """Attach request ID context for structured logs/metrics."""
    request_id = (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or uuid.uuid4().hex
    )

    with request_context(request_id):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            metrics_registry.increment(
                "http_request_error_total",
                method=request.method,
                path=request.url.path,
            )
            raise
        finally:
            metrics_registry.observe(
                "http_request_latency_seconds",
                time.perf_counter() - started,
                method=request.method,
                path=request.url.path,
            )

    response.headers["X-Request-ID"] = request_id
    return response

