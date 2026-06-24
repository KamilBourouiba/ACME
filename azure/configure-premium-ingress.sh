#!/usr/bin/env bash
# Enable premium ingress with extended idle request timeout (max 30 min)
set -euo pipefail

RG="${RG:-rg-acme}"
CAE_NAME="${CAE_NAME:-cae-acme}"
WLP_NAME="${WLP_NAME:-Ingress-D4}"
WLP_TYPE="${WLP_TYPE:-D4}"
MIN_NODES="${MIN_NODES:-2}"
MAX_NODES="${MAX_NODES:-2}"
IDLE_TIMEOUT_MIN="${IDLE_TIMEOUT_MIN:-30}"

if ! az containerapp env workload-profile show -g "$RG" -n "$CAE_NAME" --workload-profile-name "$WLP_NAME" &>/dev/null; then
  echo "==> Add dedicated workload profile $WLP_NAME ($WLP_TYPE)"
  az containerapp env workload-profile add \
    -g "$RG" -n "$CAE_NAME" \
    --workload-profile-name "$WLP_NAME" \
    --workload-profile-type "$WLP_TYPE" \
    --min-nodes "$MIN_NODES" \
    --max-nodes "$MAX_NODES" \
    -o none
else
  echo "==> Ensure $WLP_NAME has at least $MIN_NODES nodes (required for premium ingress)"
  az containerapp env workload-profile update \
    -g "$RG" -n "$CAE_NAME" \
    --workload-profile-name "$WLP_NAME" \
    --min-nodes "$MIN_NODES" \
    --max-nodes "$MAX_NODES" \
    -o none
fi

if az containerapp env premium-ingress show -g "$RG" -n "$CAE_NAME" --only-show-errors -o json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('requestIdleTimeout') else 1)"; then
  echo "==> Update premium ingress (idle timeout ${IDLE_TIMEOUT_MIN}m)"
  az containerapp env premium-ingress update \
    -g "$RG" -n "$CAE_NAME" \
    --workload-profile-name "$WLP_NAME" \
    --request-idle-timeout "$IDLE_TIMEOUT_MIN" \
    -o none
else
  echo "==> Enable premium ingress (idle timeout ${IDLE_TIMEOUT_MIN}m)"
  az containerapp env premium-ingress add \
    -g "$RG" -n "$CAE_NAME" \
    --workload-profile-name "$WLP_NAME" \
    --min-replicas "$MIN_NODES" \
    --max-replicas "$MAX_NODES" \
    --request-idle-timeout "$IDLE_TIMEOUT_MIN" \
    -o none
fi

echo "✅ Premium ingress configured on $CAE_NAME (idle timeout ${IDLE_TIMEOUT_MIN} min)"
