#!/usr/bin/env bash
# Remove legacy container Postgres after migrating to Flexible Server
set -euo pipefail

RG="${RG:-rg-acme}"
PG_APP="${PG_APP:-acme-postgres}"
API_APP="${API_APP:-acme-api}"

if az containerapp show -n "$API_APP" -g "$RG" &>/dev/null; then
  DB_SECRET=$(az containerapp secret show -n "$API_APP" -g "$RG" --secret-name database-url --query value -o tsv 2>/dev/null || true)
  if [[ "$DB_SECRET" == *"postgres.database.azure.com"* ]]; then
    echo "==> API uses Flexible Server — safe to remove $PG_APP"
  else
    echo "ERROR: API database-url does not point to Flexible Server. Abort." >&2
    exit 1
  fi
fi

if az containerapp show -n "$PG_APP" -g "$RG" &>/dev/null; then
  echo "==> Delete container app $PG_APP"
  az containerapp delete -n "$PG_APP" -g "$RG" -y -o none
  echo "✅ Removed $PG_APP"
else
  echo "==> $PG_APP not found (already removed)"
fi
