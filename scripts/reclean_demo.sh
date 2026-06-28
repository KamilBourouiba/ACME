#!/usr/bin/env bash
# Nuclear reclean: delete GitHub repo, wipe VM storage, reset all demo tenants, fresh start.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="${ACME_API:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
SECRETS="${ROOT}/azure/demo-squad.env"
GITHUB_REPO="${DEMO_GITHUB_REPO:-KamilBourouiba/erebor-site-demo}"

if [[ -f "${ROOT}/.env" ]]; then
  # shellcheck disable=SC1090
  source "${ROOT}/.env"
fi

if [[ -z "${DEMO_GITHUB_TOKEN:-}" ]] && command -v gh &>/dev/null; then
  DEMO_GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"
fi

echo "==> 1/5 Delete GitHub repo ${GITHUB_REPO} (if exists)"
if [[ -n "${DEMO_GITHUB_TOKEN:-}" ]]; then
  PYTHONPATH="${ROOT}" python3 - <<PY || true
import asyncio
from acme.demo.github_deploy import delete_repo
import os
async def main():
    ok = await delete_repo(token=os.environ["DEMO_GITHUB_TOKEN"], repo="${GITHUB_REPO}")
    print("deleted" if ok else "not_found")
asyncio.run(main())
PY
else
  echo "WARN: no DEMO_GITHUB_TOKEN — skip repo delete" >&2
fi

echo "==> 2/5 VM receiver + docker prune"
if [[ -f "$SECRETS" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS"
  "${ROOT}/azure/install-nexus-vm.sh" || true
  KEY="${DEMO_VM_DEPLOY_KEY}"
  URL="${DEMO_VM_URL:-http://20.199.121.183:9090}"
  curl -sf -X POST "${URL}/deploy" \
    -H "Authorization: Bearer ${KEY}" \
    -H "Content-Type: application/json" \
    -d '{"files":{},"wipe":true}' || true
  curl -sf -X POST "${URL}/exec" \
    -H "Authorization: Bearer ${KEY}" \
    -H "Content-Type: application/json" \
    -d '{"command":"docker system prune -af --volumes","timeout":120}' || true
  "${ROOT}/azure/repair-nexus-vm.sh" || true
fi

echo "==> 3/5 Reset demo (tenants + in-memory state)"
curl -sf -X POST "${API}/api/v1/demo/reset" | python3 -m json.tool

echo "==> 4/5 Wait for API restart loop"
sleep 12

echo "==> 5/5 Probes"
curl -sf "${URL:-http://20.199.121.183:9090}/health" && echo " receiver OK" || echo " receiver FAIL"
curl -sk "${DEMO_VM_SITE_URL:-https://20.199.121.183}/api/health" && echo "" || echo " site API FAIL"
curl -sf "${API}/api/v1/demo/state" | python3 -c "
import sys,json
s=json.load(sys.stdin)
print('phase', s['phase'], 'tick', s['tick'], 'agents', len(s['agents']), 'channels', len(s['channels']))
"

echo "✅ Nuclear reclean done — https://kamilbourouiba.github.io/ACME/demo.html"
