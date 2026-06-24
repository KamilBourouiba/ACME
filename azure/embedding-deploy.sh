#!/usr/bin/env bash
# Deploy Azure OpenAI embedding model and wire ACME API env
set -euo pipefail

OPENAI_RG="${OPENAI_RG:-Testing}"
OPENAI_ACCOUNT="${OPENAI_ACCOUNT:-TESTING-CHAT-BETA}"
EMBEDDING_DEPLOYMENT="${EMBEDDING_DEPLOYMENT:-text-embedding-3-small}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-text-embedding-3-small}"
EMBEDDING_VERSION="${EMBEDDING_VERSION:-1}"
API_APP="${API_APP:-acme-api}"
RG="${RG:-rg-acme}"

echo "==> Create embedding deployment: $EMBEDDING_DEPLOYMENT"
if ! az cognitiveservices account deployment show \
  -g "$OPENAI_RG" -n "$OPENAI_ACCOUNT" --deployment-name "$EMBEDDING_DEPLOYMENT" &>/dev/null; then
  az cognitiveservices account deployment create \
    -g "$OPENAI_RG" -n "$OPENAI_ACCOUNT" \
    --deployment-name "$EMBEDDING_DEPLOYMENT" \
    --model-name "$EMBEDDING_MODEL" \
    --model-version "$EMBEDDING_VERSION" \
    --model-format OpenAI \
    --sku-capacity 10 \
    --sku-name Standard \
    -o none
else
  echo "   Deployment already exists"
fi

if az containerapp show -n "$API_APP" -g "$RG" &>/dev/null; then
  echo "==> Update API env AZURE_OPENAI_EMBEDDING_DEPLOYMENT=$EMBEDDING_DEPLOYMENT"
  az containerapp update -n "$API_APP" -g "$RG" \
    --image "$(az containerapp show -n "$API_APP" -g "$RG" --query 'properties.template.containers[0].image' -o tsv)" \
    --revision-suffix "embed-$(date +%s | tail -c 6)" \
    --set-env-vars "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${EMBEDDING_DEPLOYMENT}" "PGVECTOR_ENABLED=true" \
    -o none
fi

echo "✅ Embedding deployment ready: $EMBEDDING_DEPLOYMENT"
