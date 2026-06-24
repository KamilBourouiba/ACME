#!/usr/bin/env bash
# Run investor demo against prod (requires API_KEY in azure/api-key.env for benchmarks)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL="${ACME_API_URL:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
ENV_FILE="${ROOT}/azure/api-key.env"
EXTRA=()
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  export ACME_API_KEY="${API_KEY:-}"
fi
cd "$ROOT"
PYTHONPATH=. .venv/bin/python scripts/investor_demo.py --url "$URL" "$@"
