#!/bin/bash
# Setup Cloud Scheduler for daily incremental data refresh
# Idempotent: deletes existing job before creating new one

set -euo pipefail

PROJECT_ID="bobbys-project-346400"
LOCATION="us-east1"
JOB_NAME="feedops-daily-incremental-refresh"
SERVICE_URL="https://feedops-pipeline-623866089882.us-east1.run.app"
SERVICE_ACCOUNT="profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com"

echo "Setting up Cloud Scheduler job: $JOB_NAME"

# Delete existing job if it exists (idempotent)
gcloud scheduler jobs delete "$JOB_NAME" \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --quiet 2>/dev/null || true

# Create new scheduler job
# Schedule: 2:00 AM Pacific Time, daily
# Payload: incremental mode with 1-day lookback, empty SKU list (auto-detect stale)
gcloud scheduler jobs create http "$JOB_NAME" \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --schedule="0 2 * * *" \
  --time-zone="America/Los_Angeles" \
  --uri="${SERVICE_URL}/backfill/start" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"job_type":"full_backfill","skus":[],"config":{"days_lookback":1,"batch_size":50,"mode":"incremental"}}' \
  --oidc-service-account-email="$SERVICE_ACCOUNT" \
  --oidc-token-audience="$SERVICE_URL" \
  --attempt-deadline=1800s \
  --max-retry-attempts=3 \
  --min-backoff=60s \
  --max-backoff=300s

echo "Cloud Scheduler job created successfully."
echo "  Schedule: Daily at 2:00 AM PT"
echo "  Target: ${SERVICE_URL}/backfill/start"
echo "  Auth: OIDC via ${SERVICE_ACCOUNT}"
echo ""
echo "To test manually: gcloud scheduler jobs run $JOB_NAME --project=$PROJECT_ID --location=$LOCATION"
