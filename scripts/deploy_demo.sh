#!/usr/bin/env bash
# Enable public multi-agent demo on prod (GPT-5.4 optional).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="${RG:-rg-acme}"
ACR_NAME="${ACR_NAME:-acmeacrdfbe2a}"
API_APP="${API_APP:-acme-api}"
TAG="${TAG:-membench-v3-fidelity}"
SUFFIX="${SUFFIX:-demo-live-$(date +%Y%m%d%H%M)}"
DEMO_MODEL="${DEMO_AZURE_DEPLOYMENT:-gpt-5.4}"
INTERVAL="${DEMO_INTERVAL_SEC:-45}"

echo "==> Build acme-api:${TAG}"
az acr build --registry "$ACR_NAME" --image "acme-api:${TAG}" "$ROOT" -o none

echo "==> Deploy with demo enabled (model=${DEMO_MODEL})"
# Demo state is in-process; keep a single replica so SSE/state stay consistent.
az containerapp update -n "$API_APP" -g "$RG" \
  --image "${ACR_NAME}.azurecr.io/acme-api:${TAG}" \
  --revision-suffix "$SUFFIX" \
  --min-replicas 1 \
  --max-replicas 1 \
  --set-env-vars \
    "DEMO_ENABLED=true" \
    "DEMO_AZURE_DEPLOYMENT=${DEMO_MODEL}" \
    "DEMO_INTERVAL_SEC=${INTERVAL}" \
    "DEMO_LLM_PARAPHRASE=true" \
  -o none

echo "==> Demo UI: https://kamilbourouiba.github.io/ACME/demo.html"
echo "==> SSE: ${ACME_API_URL:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}/api/v1/demo/events"
