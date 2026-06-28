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
INTERVAL="${DEMO_INTERVAL_SEC:-0}"
PIPELINE="${DEMO_PIPELINE_MODE:-true}"
PROBE_REFRESH="${DEMO_PROBE_REFRESH_SEC:-8}"
TURN_YIELD="${DEMO_TURN_YIELD_MS:-500}"
AGENT_COOLDOWN="${DEMO_AGENT_MESSAGE_COOLDOWN_SEC:-15}"
PUBLISH_COOLDOWN="${DEMO_PUBLISH_COOLDOWN_SEC:-15}"
CODE_TIMEOUT="${DEMO_CODE_TIMEOUT_SEC:-65}"
GITHUB_REPO="${DEMO_GITHUB_REPO:-KamilBourouiba/erebor-site-demo}"

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
  "DEMO_PIPELINE_MODE=${PIPELINE}"
  "DEMO_PROBE_REFRESH_SEC=${PROBE_REFRESH}"
  "DEMO_TURN_YIELD_MS=${TURN_YIELD}"
  "DEMO_AGENT_MESSAGE_COOLDOWN_SEC=${AGENT_COOLDOWN}"
  "DEMO_STARTUP_DELAY_SEC=0"
  "DEMO_RESET_COOLDOWN_SEC=3"
  "DEMO_PUBLISH_COOLDOWN_SEC=${PUBLISH_COOLDOWN}"
  "DEMO_CODE_TIMEOUT_SEC=${CODE_TIMEOUT}"
  "DEMO_LLM_PARAPHRASE=false"
  "DEMO_LLM_CODE=true"
  "DEMO_CODE_FALLBACK=false"
  "DEMO_AUTO_PUBLISH=true"
  "DEMO_BELIEF_REFRESH_TICKS=3"
  "DEMO_MESSAGE_CAP=400"
  "DEMO_STATE_MESSAGE_CAP=150"
  "DEMO_CLEAN_ON_START=false"
  "DEMO_WIPE_ON_CLEAN=false"
  "DEMO_AUTO_RECYCLE=false"
  "DEMO_CONTINUOUS_IMPROVEMENT=true"
  "DEMO_CLEAN_REPO_ON_RESET=true"
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

echo "==> Deploy demo (pipeline=${PIPELINE}, interval=${INTERVAL}s, auto-publish=${GITHUB_REPO})"

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
