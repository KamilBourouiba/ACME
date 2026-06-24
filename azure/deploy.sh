#!/usr/bin/env bash
# Deploy ACME to Azure Container Apps (Postgres + Neo4j + API)
# Uses existing Azure OpenAI deployment (default: gpt-4.1 on TESTING-CHAT-BETA)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOCATION="${LOCATION:-westeurope}"
RG="${RG:-rg-acme}"
ACR_NAME="${ACR_NAME:-acmeacrdfbe2a}"
CAE_NAME="${CAE_NAME:-cae-acme}"
API_APP="${API_APP:-acme-api}"
NEO4J_APP="${NEO4J_APP:-acme-neo4j}"
PG_APP="${PG_APP:-acme-postgres}"
PG_USER="${PG_USER:-acme}"
PG_PASSWORD="${PG_PASSWORD:-$(openssl rand -base64 16 | tr -dc 'A-Za-z0-9' | head -c 16)}"
PG_DB="${PG_DB:-acme}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-$(openssl rand -base64 16 | tr -dc 'A-Za-z0-9' | head -c 16)}"

OPENAI_RG="${OPENAI_RG:-Testing}"
OPENAI_ACCOUNT="${OPENAI_ACCOUNT:-TESTING-CHAT-BETA}"
OPENAI_DEPLOYMENT="${OPENAI_DEPLOYMENT:-gpt-4.1}"
EMBEDDING_DEPLOYMENT="${EMBEDDING_DEPLOYMENT:-text-embedding-3-small}"

echo "==> Register Azure providers"
az provider register --namespace Microsoft.App --wait -o none 2>/dev/null || true
az provider register --namespace Microsoft.OperationalInsights --wait -o none 2>/dev/null || true

echo "==> Resource group: $RG ($LOCATION)"
az group create --name "$RG" --location "$LOCATION" -o none

if ! az acr show -n "$ACR_NAME" -g "$RG" &>/dev/null; then
  echo "==> Container Registry: $ACR_NAME"
  az acr create --resource-group "$RG" --name "$ACR_NAME" --sku Basic --admin-enabled true -o none
fi

ACR_LOGIN_SERVER=$(az acr show -n "$ACR_NAME" -g "$RG" --query loginServer -o tsv)
ACR_USER=$(az acr credential show -n "$ACR_NAME" -g "$RG" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR_NAME" -g "$RG" --query passwords[0].value -o tsv)

echo "==> Build & push API image"
az acr build --registry "$ACR_NAME" --image acme-api:latest "$ROOT_DIR" -o none

OPENAI_ENDPOINT=$(az cognitiveservices account show -g "$OPENAI_RG" -n "$OPENAI_ACCOUNT" --query properties.endpoint -o tsv)
OPENAI_KEY=$(az cognitiveservices account keys list -g "$OPENAI_RG" -n "$OPENAI_ACCOUNT" --query key1 -o tsv)

if ! az containerapp env show -n "$CAE_NAME" -g "$RG" &>/dev/null; then
  echo "==> Container Apps environment: $CAE_NAME"
  az containerapp env create -n "$CAE_NAME" -g "$RG" -l "$LOCATION" -o none
fi

if ! az containerapp show -n "$PG_APP" -g "$RG" &>/dev/null; then
  echo "==> Deploy PostgreSQL container"
  az containerapp create \
    -n "$PG_APP" -g "$RG" \
    --environment "$CAE_NAME" \
    --image postgres:16-alpine \
    --target-port 5432 \
    --ingress internal \
    --transport tcp \
    --min-replicas 1 --max-replicas 1 \
    --cpu 0.5 --memory 1Gi \
    --env-vars \
      "POSTGRES_USER=${PG_USER}" \
      "POSTGRES_PASSWORD=secretref:pg-password" \
      "POSTGRES_DB=${PG_DB}" \
    --secrets "pg-password=${PG_PASSWORD}" \
    -o none
fi

if ! az containerapp show -n "$NEO4J_APP" -g "$RG" &>/dev/null; then
  echo "==> Deploy Neo4j"
  az containerapp create \
    -n "$NEO4J_APP" -g "$RG" \
    --environment "$CAE_NAME" \
    --image neo4j:5-community \
    --target-port 7687 \
    --ingress internal \
    --transport tcp \
    --min-replicas 1 --max-replicas 1 \
    --cpu 1.0 --memory 2Gi \
    --env-vars "NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}" \
    -o none
fi

DATABASE_URL="postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@${PG_APP}:5432/${PG_DB}"

if az containerapp show -n "$API_APP" -g "$RG" &>/dev/null; then
  echo "==> Update ACME API"
  az containerapp update \
    -n "$API_APP" -g "$RG" \
    --image "${ACR_LOGIN_SERVER}/acme-api:latest" \
    --set-env-vars \
      "LLM_PROVIDER=azure_openai" \
      "AZURE_OPENAI_ENDPOINT=${OPENAI_ENDPOINT}" \
      "AZURE_OPENAI_API_KEY=secretref:openai-key" \
      "AZURE_OPENAI_DEPLOYMENT=${OPENAI_DEPLOYMENT}" \
      "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${EMBEDDING_DEPLOYMENT:-text-embedding-3-small}" \
      "AZURE_OPENAI_API_VERSION=2024-10-21" \
      "PGVECTOR_ENABLED=true" \
      "DATABASE_URL=secretref:database-url" \
      "NEO4J_URI=bolt://${NEO4J_APP}:7687" \
      "NEO4J_USER=neo4j" \
      "NEO4J_PASSWORD=secretref:neo4j-password" \
      "LOG_LEVEL=INFO" \
    --replace-env-vars \
      "LLM_PROVIDER=azure_openai" \
      "AZURE_OPENAI_ENDPOINT=${OPENAI_ENDPOINT}" \
      "AZURE_OPENAI_API_KEY=secretref:openai-key" \
      "AZURE_OPENAI_DEPLOYMENT=${OPENAI_DEPLOYMENT}" \
      "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${EMBEDDING_DEPLOYMENT:-text-embedding-3-small}" \
      "AZURE_OPENAI_API_VERSION=2024-10-21" \
      "PGVECTOR_ENABLED=true" \
      "DATABASE_URL=secretref:database-url" \
      "NEO4J_URI=bolt://${NEO4J_APP}:7687" \
      "NEO4J_USER=neo4j" \
      "NEO4J_PASSWORD=secretref:neo4j-password" \
      "LOG_LEVEL=INFO" \
    -o none
else
  echo "==> Deploy ACME API"
  az containerapp create \
    -n "$API_APP" -g "$RG" \
    --environment "$CAE_NAME" \
    --image "${ACR_LOGIN_SERVER}/acme-api:latest" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PASS" \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 --max-replicas 2 \
    --cpu 1.0 --memory 2Gi \
    --env-vars \
      "LLM_PROVIDER=azure_openai" \
      "AZURE_OPENAI_ENDPOINT=${OPENAI_ENDPOINT}" \
      "AZURE_OPENAI_API_KEY=secretref:openai-key" \
      "AZURE_OPENAI_DEPLOYMENT=${OPENAI_DEPLOYMENT}" \
      "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${EMBEDDING_DEPLOYMENT:-text-embedding-3-small}" \
      "AZURE_OPENAI_API_VERSION=2024-10-21" \
      "PGVECTOR_ENABLED=true" \
      "DATABASE_URL=secretref:database-url" \
      "NEO4J_URI=bolt://${NEO4J_APP}:7687" \
      "NEO4J_USER=neo4j" \
      "NEO4J_PASSWORD=secretref:neo4j-password" \
      "LOG_LEVEL=INFO" \
    --secrets \
      "openai-key=${OPENAI_KEY}" \
      "database-url=${DATABASE_URL}" \
      "neo4j-password=${NEO4J_PASSWORD}" \
    -o none
fi

API_URL=$(az containerapp show -n "$API_APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)

cat > "$ROOT_DIR/azure/deployment.env" <<EOF
RG=$RG
API_URL=https://${API_URL}
OPENAI_DEPLOYMENT=$OPENAI_DEPLOYMENT
OPENAI_ENDPOINT=$OPENAI_ENDPOINT
PG_APP=$PG_APP
NEO4J_APP=$NEO4J_APP
EOF

echo ""
echo "✅ ACME deployed!"
echo "   API:      https://${API_URL}"
echo "   Docs:     https://${API_URL}/docs"
echo "   Health:   https://${API_URL}/api/v1/health"
echo "   LLM:      Azure OpenAI / ${OPENAI_DEPLOYMENT}"
echo "   Details:  azure/deployment.env"
