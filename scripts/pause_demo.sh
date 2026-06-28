#!/usr/bin/env bash
set -euo pipefail
API="${ACME_API:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
ACTION="${1:-pause}"
echo "==> POST $API/api/v1/demo/$ACTION"
curl -sf -X POST "$API/api/v1/demo/$ACTION" | python3 -m json.tool
