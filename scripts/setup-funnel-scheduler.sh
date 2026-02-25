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
# NOTE: 5 AM ET = 2 AM PT. Google Ads data for yesterday may be ~95% settled at this time
# (full settlement typically by 3-4 AM PT). If snapshot data appears incomplete, consider
# changing schedule to "0 8 * * *" (8 AM ET / 5 AM PT) for full data settlement.

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

echo "Creating Cloud Scheduler job: ${JOB_NAME}..."
echo "  Schedule: 5 AM ET daily"
echo "  Target:   ${URI}"

gcloud scheduler jobs create http "${JOB_NAME}" \
  --project="${PROJECT}" \
  --location="${LOCATION}" \
  --schedule="0 5 * * *" \
  --time-zone="America/New_York" \
  --uri="${URI}" \
  --http-method=POST \
  --headers="Content-Type=application/json,Authorization=Bearer ${CRON_SECRET}" \
  --message-body='{}' \
  --attempt-deadline="120s" \
  --max-retry-attempts=3 \
  --min-backoff="60s" \
  --max-backoff="300s" \
  --description="Daily funnel snapshot capture - persists Google Ads shopping tier data"

echo ""
echo "Done. Job ${JOB_NAME} created."
echo "Verify with: gcloud scheduler jobs describe ${JOB_NAME} --project=${PROJECT} --location=${LOCATION}"
