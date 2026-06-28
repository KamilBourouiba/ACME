#!/usr/bin/env bash
# Reset live demo (tenants + in-memory state + optional GitHub baseline).
set -euo pipefail
API="${ACME_API:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
echo "==> POST $API/api/v1/demo/reset"
curl -sf -X POST "$API/api/v1/demo/reset" | python3 -m json.tool
