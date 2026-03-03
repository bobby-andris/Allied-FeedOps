#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <revision-tag>"
  echo "Example: $0 cert-query-intent"
  exit 1
fi

REVISION_TAG="$1"
PROJECT_ID="${PROJECT_ID:-bobbys-project-346400}"
REGION="${REGION:-us-east1}"
SERVICE_NAME="${SERVICE_NAME:-feedops-pipeline}"
IMAGE_REPO="us-east1-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${SERVICE_NAME}"
COMMIT_SHA="$(git rev-parse HEAD)"
IMAGE_TAG="${COMMIT_SHA}-amd64"
IMAGE_REF="${IMAGE_REPO}:${IMAGE_TAG}"
BASE_ENV_VARS="GOOGLE_ADS_CUSTOMER_ID=6253381786,GOOGLE_ADS_API_ENABLED=1,FEEDOPS_ENV_CONTRACT_STRICT=1"
EXTRA_ENV_VARS="${EXTRA_ENV_VARS:-}"

if [[ -n "${EXTRA_ENV_VARS}" ]]; then
  ENV_VARS="${BASE_ENV_VARS},${EXTRA_ENV_VARS}"
else
  ENV_VARS="${BASE_ENV_VARS}"
fi

echo "==> Building linux/amd64 image for exact branch certification"
docker buildx build \
  --platform linux/amd64 \
  --tag "${IMAGE_REF}" \
  --push \
  .

echo "==> Deploying tagged no-traffic Cloud Run revision"
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_REF}" \
  --region "${REGION}" \
  --tag "${REVISION_TAG}" \
  --no-traffic \
  --set-secrets "OPENAI_API_KEY=feedops-openai-api-key:latest,SUPABASE_URL=feedops-supabase-url:latest,SUPABASE_KEY=feedops-supabase-key:latest,GOOGLE_ADS_DEVELOPER_TOKEN=feedops-google-ads-developer-token:latest,GOOGLE_ADS_CLIENT_ID=feedops-google-ads-client-id:latest,GOOGLE_ADS_CLIENT_SECRET=feedops-google-ads-client-secret:latest,GOOGLE_ADS_REFRESH_TOKEN=feedops-google-ads-refresh-token:latest,GOOGLE_ADS_LOGIN_CUSTOMER_ID=feedops-google-ads-login-customer-id:latest,GEMINI_API_KEY=feedops-gemini-api-key:latest,SLACK_WEBHOOK_URL=feedops-slack-webhook-url:latest" \
  --set-env-vars "${ENV_VARS}" \
  --service-account "profit-pilot-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format="value(status.traffic[?tag='${REVISION_TAG}'].url)")"
if [[ -z "${SERVICE_URL}" ]]; then
  SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --format="value(status.url)")"
fi

echo
echo "Tagged revision deployed successfully."
echo "  Commit SHA:   ${COMMIT_SHA}"
echo "  Image ref:    ${IMAGE_REF}"
echo "  Service:      ${SERVICE_NAME}"
echo "  Region:       ${REGION}"
echo "  Revision tag: ${REVISION_TAG}"
echo "  Tagged URL:   ${SERVICE_URL}"
if [[ -n "${EXTRA_ENV_VARS}" ]]; then
  echo "  Extra env:    ${EXTRA_ENV_VARS}"
fi
echo
echo "Use this path for pre-PR exact-branch certification only."
echo "Post-merge production deploys must still use the GitHub-connected Cloud Build path on origin/master."
