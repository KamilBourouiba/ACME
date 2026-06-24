#!/usr/bin/env bash
# Deploy ACME consolidation worker as Azure Container Apps Job (scheduled)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="${RG:-rg-acme}"
CAE_NAME="${CAE_NAME:-cae-acme}"
JOB_NAME="${JOB_NAME:-acme-consolidation}"
API_APP="${API_APP:-acme-api}"
ACR_NAME="${ACR_NAME:-acmeacrdfbe2a}"
SCHEDULE="${SCHEDULE:-0 */6 * * *}"

API_URL=$(az containerapp show -n "$API_APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
ACR_LOGIN_SERVER=$(az acr show -n "$ACR_NAME" -g "$RG" --query loginServer -o tsv)
ACR_USER=$(az acr credential show -n "$ACR_NAME" -g "$RG" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR_NAME" -g "$RG" --query passwords[0].value -o tsv)

echo "==> Build consolidation worker image"
az acr build --registry "$ACR_NAME" --image acme-consolidation:latest \
  --file "$ROOT_DIR/azure/Dockerfile.consolidation" "$ROOT_DIR" -o none

REGISTRY_ARGS=(
  --registry-server "$ACR_LOGIN_SERVER"
  --registry-username "$ACR_USER"
  --registry-password "$ACR_PASS"
)

if az containerapp job show -n "$JOB_NAME" -g "$RG" &>/dev/null; then
  echo "==> Update consolidation job"
  az containerapp job update \
    -n "$JOB_NAME" -g "$RG" \
    --image "${ACR_LOGIN_SERVER}/acme-consolidation:latest" \
    --cron-expression "$SCHEDULE" \
    "${REGISTRY_ARGS[@]}" \
    --set-env-vars "ACME_API_URL=https://${API_URL}" "CONSOLIDATION_INTERVAL=0" \
    -o none
else
  echo "==> Create consolidation job (cron: $SCHEDULE)"
  az containerapp job create \
    -n "$JOB_NAME" -g "$RG" \
    --environment "$CAE_NAME" \
    --trigger-type Schedule \
    --cron-expression "$SCHEDULE" \
    --replica-timeout 1800 \
    --replica-retry-limit 1 \
    --replica-completion-count 1 \
    --parallelism 1 \
    --image "${ACR_LOGIN_SERVER}/acme-consolidation:latest" \
    "${REGISTRY_ARGS[@]}" \
    --cpu 0.5 --memory 1Gi \
    --env-vars "ACME_API_URL=https://${API_URL}" "CONSOLIDATION_INTERVAL=0" \
    -o none
fi

echo "==> Trigger test execution"
az containerapp job start -n "$JOB_NAME" -g "$RG" -o none

echo "✅ Consolidation job deployed: $JOB_NAME (cron: every 6h → https://${API_URL})"
