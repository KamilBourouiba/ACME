#!/usr/bin/env bash
# Set API_KEY secret and enable benchmark auth on Container App
set -euo pipefail

RG="${RG:-rg-acme}"
API_APP="${API_APP:-acme-api}"
API_KEY="${API_KEY:-$(openssl rand -hex 24)}"
RATE_LIMIT="${BENCHMARK_RATE_LIMIT_PER_HOUR:-10}"

echo "==> Configure API_KEY on $API_APP (rate limit ${RATE_LIMIT}/h for benchmarks)"
az containerapp secret set -n "$API_APP" -g "$RG" --secrets "api-key=${API_KEY}" -o none
az containerapp update -n "$API_APP" -g "$RG" \
  --image "$(az containerapp show -n "$API_APP" -g "$RG" --query 'properties.template.containers[0].image' -o tsv)" \
  --revision-suffix "sec-$(date +%s | tail -c 6)" \
  --set-env-vars \
    "API_KEY=secretref:api-key" \
    "BENCHMARK_RATE_LIMIT_PER_HOUR=${RATE_LIMIT}" \
  -o none

KEY_FILE="$(cd "$(dirname "$0")/.." && pwd)/azure/api-key.env"
cat > "$KEY_FILE" <<EOF
API_KEY=${API_KEY}
EOF
chmod 600 "$KEY_FILE"

echo "✅ API key saved to azure/api-key.env (gitignored)"
echo "   Use header: X-API-Key: \${API_KEY} for /benchmark/* and /benchmark/export"
