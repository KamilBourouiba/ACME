#!/usr/bin/env bash
# Switch Container Apps environment back to Consumption-only (disable premium ingress billing)
set -euo pipefail

RG="${RG:-rg-acme}"
CAE_NAME="${CAE_NAME:-cae-acme}"

if az containerapp env premium-ingress show -g "$RG" -n "$CAE_NAME" --only-show-errors -o json &>/dev/null; then
  echo "==> Remove premium ingress from $CAE_NAME"
  az containerapp env premium-ingress delete -g "$RG" -n "$CAE_NAME" -y -o none
else
  echo "==> Premium ingress not enabled"
fi

echo "✅ Environment on Consumption profile (use configure-premium-ingress.sh before long benchmarks)"
