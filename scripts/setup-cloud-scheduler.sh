#!/bin/bash
# Setup Cloud Scheduler for daily incremental data refresh
# Idempotent: deletes existing job before creating new one

set -euo pipefail

PROJECT_ID="bobbys-project-346400"
LOCATION="us-east1"
JOB_NAME="feedops-daily-incremental-refresh"
SERVICE_URL="${SERVICE_URL:-${1:-}}"
SERVICE_ACCOUNT="profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com"
SCHEDULE="15 2 * * *"
TIME_ZONE="America/New_York"
SNAPSHOT_JOB_NAME="feedops-daily-snapshot-capture"
SNAPSHOT_SCHEDULE="45 2 * * *"

if [[ -z "${SERVICE_URL}" ]]; then
  echo "SERVICE_URL must be provided via environment variable or first positional argument." >&2
  exit 1
fi

SERVICE_URL="${SERVICE_URL%/}"

echo "Setting up Cloud Scheduler job: $JOB_NAME"

# Delete existing job if it exists (idempotent)
gcloud scheduler jobs delete "$JOB_NAME" \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --quiet 2>/dev/null || true

# Create new scheduler job
# Schedule: 2:15 AM Eastern Time, daily
# Payload: incremental mode with 1-day lookback, empty SKU list (auto-detect stale)
gcloud scheduler jobs create http "$JOB_NAME" \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --schedule="$SCHEDULE" \
  --time-zone="$TIME_ZONE" \
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
echo "  Schedule: Daily at 2:15 AM ET"
echo "  Target: ${SERVICE_URL}/backfill/start"
echo "  Auth: OIDC via ${SERVICE_ACCOUNT}"
echo ""
echo "To test manually: gcloud scheduler jobs run $JOB_NAME --project=$PROJECT_ID --location=$LOCATION"

echo ""
echo "Setting up Cloud Scheduler job: $SNAPSHOT_JOB_NAME"

# Delete existing snapshot job if it exists (idempotent)
gcloud scheduler jobs delete "$SNAPSHOT_JOB_NAME" \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --quiet 2>/dev/null || true

# Create snapshot capture job
# Schedule: 2:45 AM Eastern Time, daily
gcloud scheduler jobs create http "$SNAPSHOT_JOB_NAME" \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --schedule="$SNAPSHOT_SCHEDULE" \
  --time-zone="$TIME_ZONE" \
  --uri="${SERVICE_URL}/performance/capture-snapshot" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"platform":"google","environment":"production"}' \
  --oidc-service-account-email="$SERVICE_ACCOUNT" \
  --oidc-token-audience="$SERVICE_URL" \
  --attempt-deadline=1800s \
  --max-retry-attempts=3 \
  --min-backoff=60s \
  --max-backoff=300s

echo "Cloud Scheduler job created successfully."
echo "  Schedule: Daily at 2:45 AM ET"
echo "  Target: ${SERVICE_URL}/performance/capture-snapshot"
echo "  Auth: OIDC via ${SERVICE_ACCOUNT}"
echo ""
echo "To test manually: gcloud scheduler jobs run $SNAPSHOT_JOB_NAME --project=$PROJECT_ID --location=$LOCATION"
