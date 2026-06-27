#!/usr/bin/env bash
# Enable public Slack-style squad demo on prod.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="${RG:-rg-acme}"
ACR_NAME="${ACR_NAME:-acmeacrdfbe2a}"
API_APP="${API_APP:-acme-api}"
TAG="${TAG:-membench-v3-fidelity}"
SUFFIX="${SUFFIX:-demo-live-$(date +%Y%m%d%H%M)}"
DEMO_MODEL="${DEMO_AZURE_DEPLOYMENT:-gpt-5.4}"
INTERVAL="${DEMO_INTERVAL_SEC:-10}"
GITHUB_REPO="${DEMO_GITHUB_REPO:-KamilBourouiba/consulting-site-demo}"

echo "==> Build acme-api:${TAG}"
az acr build --registry "$ACR_NAME" --image "acme-api:${TAG}" "$ROOT" -o none

ENV_VARS=(
  "DEMO_ENABLED=true"
  "DEMO_AZURE_DEPLOYMENT=${DEMO_MODEL}"
  "DEMO_INTERVAL_SEC=${INTERVAL}"
  "DEMO_LLM_PARAPHRASE=false"
  "DEMO_GITHUB_REPO=${GITHUB_REPO}"
  "DEMO_GITHUB_BRANCH=main"
)

if [[ -n "${DEMO_GITHUB_TOKEN:-}" ]]; then
  ENV_VARS+=("DEMO_GITHUB_TOKEN=secretref:demo-github-token")
fi

echo "==> Deploy demo (interval=${INTERVAL}s, repo=${GITHUB_REPO})"

if [[ -n "${DEMO_GITHUB_TOKEN:-}" ]]; then
  az containerapp secret set -n "$API_APP" -g "$RG" \
    --secrets "demo-github-token=${DEMO_GITHUB_TOKEN}" -o none
fi

az containerapp update -n "$API_APP" -g "$RG" \
  --image "${ACR_NAME}.azurecr.io/acme-api:${TAG}" \
  --revision-suffix "$SUFFIX" \
  --min-replicas 1 \
  --max-replicas 1 \
  --set-env-vars "${ENV_VARS[@]}" \
  -o none

echo "==> Demo UI: https://kamilbourouiba.github.io/ACME/demo.html"
echo "==> SSE: ${ACME_API_URL:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}/api/v1/demo/events"
