#!/usr/bin/env bash
# Build & deploy ACME API with V3_SCENARIOS + MemGPT summarize-on-evict (no env wipe).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="${RG:-rg-acme}"
ACR_NAME="${ACR_NAME:-acmeacrdfbe2a}"
API_APP="${API_APP:-acme-api}"
TAG="${TAG:-membench-v3-fidelity}"
SUFFIX="${SUFFIX:-membench-v3-fidelity}"
API="${ACME_API_URL:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"

echo "==> ACR build acme-api:${TAG}"
az acr build --registry "$ACR_NAME" --image "acme-api:${TAG}" "$ROOT" -o none

echo "==> Update ${API_APP} (preserves secrets / DATABASE_URL)"
az containerapp update -n "$API_APP" -g "$RG" \
  --image "${ACR_NAME}.azurecr.io/acme-api:${TAG}" \
  --revision-suffix "$SUFFIX" \
  -o none

echo "==> Wait for revision acme-api--${SUFFIX}"
for _ in $(seq 1 60); do
  REV=$(az containerapp revision list -n "$API_APP" -g "$RG" \
    --query "[?properties.trafficWeight==\`100\`].name" -o tsv 2>/dev/null || true)
  [[ "$REV" == "acme-api--${SUFFIX}" ]] && break
  sleep 5
done

echo "==> Health check"
for _ in $(seq 1 30); do
  if curl -sf "${API}/api/v1/health" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='healthy' else 1)"; then
    curl -sf "${API}/api/v1/health" | python3 -m json.tool
    echo "✅ Deployed acme-api--${SUFFIX}"
    exit 0
  fi
  sleep 10
done
echo "WARN: health not stable — try: az containerapp revision restart -n acme-neo4j -g $RG" >&2
exit 1
