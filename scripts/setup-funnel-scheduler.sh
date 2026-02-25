#!/bin/bash
set -euo pipefail

# Setup GCP Cloud Scheduler job for daily funnel snapshot capture
#
# Usage:
#   bash scripts/setup-funnel-scheduler.sh <CRON_SECRET>
#   bash scripts/setup-funnel-scheduler.sh --delete
#
# Prerequisites:
#   1. Add CRON_SECRET to Vercel env vars (Dashboard > Settings > Environment Variables)
#   2. gcloud CLI authenticated with appropriate project access
#
# Schedule: 6 AM UTC daily (fixed timezone, no DST shift)
# Google Ads data for yesterday is typically fully settled by this time.

PROJECT="bobbys-project-346400"
LOCATION="us-east1"
JOB_NAME="feedops-funnel-snapshot-daily"
URI="https://allied-feed-ops.vercel.app/api/funnel-snapshots/capture"

# Handle --delete option
if [ "${1:-}" = "--delete" ]; then
  echo "Deleting Cloud Scheduler job: ${JOB_NAME}..."
  gcloud scheduler jobs delete "${JOB_NAME}" \
    --project="${PROJECT}" \
    --location="${LOCATION}" \
    --quiet
  echo "Done. Job ${JOB_NAME} deleted."
  exit 0
fi

# Require CRON_SECRET argument
if [ -z "${1:-}" ]; then
  echo "Usage: $0 <CRON_SECRET>"
  echo "       $0 --delete"
  echo ""
  echo "CRON_SECRET must match the value set in Vercel environment variables."
  exit 1
fi

CRON_SECRET="$1"

COMMON_ARGS=(
  --project="${PROJECT}"
  --location="${LOCATION}"
  --schedule="0 6 * * *"
  --time-zone="UTC"
  --uri="${URI}"
  --http-method=POST
  --message-body='{}'
  --attempt-deadline="120s"
  --max-retry-attempts=2
  --min-backoff="300s"
  --max-backoff="300s"
)

HEADERS="Content-Type=application/json,Authorization=Bearer ${CRON_SECRET}"

if gcloud scheduler jobs describe "${JOB_NAME}" --project="${PROJECT}" --location="${LOCATION}" --quiet 2>/dev/null; then
  echo "Job ${JOB_NAME} already exists. Updating..."
  echo "  Schedule: 6 AM UTC daily (fixed timezone, no DST shift)"
  echo "  Target:   ${URI}"
  gcloud scheduler jobs update http "${JOB_NAME}" "${COMMON_ARGS[@]}" \
    --update-headers="${HEADERS}"
else
  echo "Creating Cloud Scheduler job: ${JOB_NAME}..."
  echo "  Schedule: 6 AM UTC daily (fixed timezone, no DST shift)"
  echo "  Target:   ${URI}"
  gcloud scheduler jobs create http "${JOB_NAME}" "${COMMON_ARGS[@]}" \
    --headers="${HEADERS}" \
    --description="Daily funnel snapshot capture - persists Google Ads shopping tier data"
fi

echo ""
echo "Done. Job ${JOB_NAME} configured."
echo "Verify with: gcloud scheduler jobs describe ${JOB_NAME} --project=${PROJECT} --location=${LOCATION}"
