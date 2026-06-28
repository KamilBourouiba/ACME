#!/usr/bin/env bash
# Enable public Slack-style squad demo on prod (autonomous GitHub publish).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="${RG:-rg-acme}"
ACR_NAME="${ACR_NAME:-acmeacrdfbe2a}"
API_APP="${API_APP:-acme-api}"
TAG="${TAG:-membench-v3-fidelity}"
SUFFIX="${SUFFIX:-demo-live-$(date +%Y%m%d%H%M)}"
DEMO_MODEL="${DEMO_AZURE_DEPLOYMENT:-gpt-5.4}"
INTERVAL="${DEMO_INTERVAL_SEC:-5}"
GITHUB_REPO="${DEMO_GITHUB_REPO:-KamilBourouiba/consulting-site-demo}"

if [[ -z "${DEMO_GITHUB_TOKEN:-}" ]] && command -v gh &>/dev/null; then
  DEMO_GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"
fi

if [[ -z "${DEMO_GITHUB_TOKEN:-}" ]]; then
  echo "WARNING: DEMO_GITHUB_TOKEN not set — squad cannot autonomously publish to GitHub." >&2
  echo "  export DEMO_GITHUB_TOKEN=ghp_…  OR  gh auth login" >&2
fi

echo "==> Build acme-api:${TAG}"
az acr build --registry "$ACR_NAME" --image "acme-api:${TAG}" "$ROOT" -o none

ENV_VARS=(
  "DEMO_ENABLED=true"
  "DEMO_AZURE_DEPLOYMENT=${DEMO_MODEL}"
  "DEMO_INTERVAL_SEC=${INTERVAL}"
  "DEMO_LLM_PARAPHRASE=false"
  "DEMO_AUTO_PUBLISH=true"
  "DEMO_CLEAN_ON_START=true"
  "DEMO_GITHUB_REPO=${GITHUB_REPO}"
  "DEMO_GITHUB_BRANCH=main"
  "DEMO_VECTOR_SEARCH_LIMIT=50"
)

if [[ -n "${DEMO_GITHUB_TOKEN:-}" ]]; then
  ENV_VARS+=("DEMO_GITHUB_TOKEN=secretref:demo-github-token")
fi

SECRETS_FILE="${ROOT}/azure/demo-squad.env"
if [[ -f "$SECRETS_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  if [[ -n "${DEMO_VM_URL:-}" ]]; then
    ENV_VARS+=("DEMO_VM_URL=${DEMO_VM_URL}")
    ENV_VARS+=("DEMO_VM_SITE_URL=${DEMO_VM_SITE_URL:-}")
    ENV_VARS+=("DEMO_VM_AUTO_DEPLOY=true")
  fi
  if [[ -n "${DEMO_VM_DEPLOY_KEY:-}" ]]; then
    az containerapp secret set -n "$API_APP" -g "$RG" \
      --secrets "demo-vm-deploy-key=${DEMO_VM_DEPLOY_KEY}" -o none
    ENV_VARS+=("DEMO_VM_DEPLOY_KEY=secretref:demo-vm-deploy-key")
  fi
fi

echo "==> Deploy demo (interval=${INTERVAL}s, auto-publish=${GITHUB_REPO})"

if [[ -n "${DEMO_GITHUB_TOKEN:-}" ]]; then
  az containerapp secret set -n "$API_APP" -g "$RG" \
    --secrets "demo-github-token=${DEMO_GITHUB_TOKEN}" -o none
fi

az containerapp update -n "$API_APP" -g "$RG" \
  --image "${ACR_NAME}.azurecr.io/acme-api:${TAG}" \
  --revision-suffix "$SUFFIX" \
  --min-replicas 1 \
  --max-replicas 1 \
  --set-env-vars "${ENV_VARS[@]}" \
  -o none

echo "==> Demo UI: https://kamilbourouiba.github.io/ACME/demo.html"
echo "==> Site target: https://${GITHUB_REPO%%/*}.github.io/${GITHUB_REPO##*/}/"
