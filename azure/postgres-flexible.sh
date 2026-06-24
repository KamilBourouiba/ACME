#!/usr/bin/env bash
# Provision Azure Database for PostgreSQL Flexible Server with pgvector
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="${RG:-rg-acme}"
LOCATION="${LOCATION:-westeurope}"
FALLBACK_LOCATION="${FALLBACK_LOCATION:-francecentral}"
SERVER="${PG_FLEX_SERVER:-acme-pg-flex}"
DB="${PG_DB:-acme}"
USER="${PG_USER:-acmeadmin}"
ADMIN_DB="${ADMIN_DB:-postgres}"
API_APP="${API_APP:-acme-api}"
SKU="${PG_SKU:-Standard_B1ms}"
STORAGE_GB="${PG_STORAGE_GB:-32}"
SECRETS_FILE="${ROOT_DIR}/azure/postgres-flex.env"

if [[ -f "$SECRETS_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
fi

if [[ -z "${PG_PASSWORD:-}" ]]; then
  PG_PASSWORD="$(openssl rand -base64 16 | tr -dc 'A-Za-z0-9' | head -c 20)"
fi

echo "==> PostgreSQL Flexible Server: $SERVER ($SKU) in $LOCATION"
if ! az postgres flexible-server show -g "$RG" -n "$SERVER" &>/dev/null; then
  if ! az postgres flexible-server create \
    -g "$RG" -n "$SERVER" -l "$LOCATION" \
    --tier Burstable --sku-name "$SKU" \
    --storage-size "$STORAGE_GB" \
    --version 16 \
    --admin-user "$USER" \
    --admin-password "$PG_PASSWORD" \
    --public-access 0.0.0.0-255.255.255.255 \
    -o none 2>/tmp/pgflex-create.err; then
    if rg -q "restricted for provisioning" /tmp/pgflex-create.err 2>/dev/null; then
      echo "==> $LOCATION restricted — retry in $FALLBACK_LOCATION"
      az postgres flexible-server create \
        -g "$RG" -n "$SERVER" -l "$FALLBACK_LOCATION" \
        --tier Burstable --sku-name "$SKU" \
        --storage-size "$STORAGE_GB" \
        --version 16 \
        --admin-user "$USER" \
        --admin-password "$PG_PASSWORD" \
        --public-access 0.0.0.0-255.255.255.255 \
        -o none
    else
      cat /tmp/pgflex-create.err >&2
      exit 1
    fi
  fi
  echo "==> Save credentials to $SECRETS_FILE"
  cat > "$SECRETS_FILE" <<EOF
PG_FLEX_SERVER=${SERVER}
PG_USER=${USER}
PG_PASSWORD=${PG_PASSWORD}
PG_DB=${DB}
EOF
  chmod 600 "$SECRETS_FILE"
else
  echo "==> Server $SERVER already exists (using saved credentials if present)"
fi

echo "==> Allow Azure services"
az postgres flexible-server firewall-rule create \
  -g "$RG" -s "$SERVER" \
  -n AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 \
  -o none 2>/dev/null || true

echo "==> Enable pgvector extension allow-list"
az postgres flexible-server parameter set \
  -g "$RG" -s "$SERVER" \
  -n azure.extensions -v VECTOR \
  -o none

PG_HOST="${SERVER}.postgres.database.azure.com"

echo "==> Create database ${DB} (if missing)"
if command -v psql &>/dev/null; then
  PGPASSWORD="$PG_PASSWORD" psql \
    "host=${PG_HOST} port=5432 dbname=${ADMIN_DB} user=${USER} sslmode=require" \
    -tc "SELECT 1 FROM pg_database WHERE datname='${DB}'" | grep -q 1 || \
  PGPASSWORD="$PG_PASSWORD" psql \
    "host=${PG_HOST} port=5432 dbname=${ADMIN_DB} user=${USER} sslmode=require" \
    -c "CREATE DATABASE ${DB};"

  echo "==> Apply pgvector extension on ${DB}"
  PGPASSWORD="$PG_PASSWORD" psql \
    "host=${PG_HOST} port=5432 dbname=${DB} user=${USER} sslmode=require" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;"
else
  echo "   psql not found locally — extension will be created on first API init if reachable"
fi

DATABASE_URL="postgresql+asyncpg://${USER}:${PG_PASSWORD}@${PG_HOST}:5432/${DB}?ssl=require"

if az containerapp show -n "$API_APP" -g "$RG" &>/dev/null; then
  echo "==> Point API at Flexible Server (new revision)"
  az containerapp secret set -n "$API_APP" -g "$RG" --secrets "database-url=${DATABASE_URL}" -o none
  az containerapp update -n "$API_APP" -g "$RG" \
    --image "$(az containerapp show -n "$API_APP" -g "$RG" --query 'properties.template.containers[0].image' -o tsv)" \
    --revision-suffix "pgflex-$(date +%s | tail -c 6)" \
    --set-env-vars "PGVECTOR_ENABLED=true" \
    -o none
fi

{
  echo "PG_FLEX_HOST=${PG_HOST}"
  echo "PG_FLEX_SERVER=${SERVER}"
  echo "DATABASE_URL_FLEX=${DATABASE_URL}"
} >> "$ROOT_DIR/azure/deployment.env"

echo "✅ Flexible Postgres ready: ${PG_HOST}"
echo "   Credentials: azure/postgres-flex.env (gitignored)"
echo "   API secret database-url updated"
