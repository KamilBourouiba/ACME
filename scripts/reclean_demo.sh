#!/usr/bin/env bash
# Full reclean: repair VM stack, wipe GitHub + tenants via API reset, redeploy baseline.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="${ACME_API:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
SECRETS="${ROOT}/azure/demo-squad.env"

echo "==> 1/3 Repair VM stack (receiver + docker)"
if [[ -f "$SECRETS" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS"
  "${ROOT}/azure/install-nexus-vm.sh" || true
  "${ROOT}/azure/repair-nexus-vm.sh" || true
  echo "==> Seed baseline site on VM"
  cd "$ROOT"
  PYTHONPATH=. python3 - <<PY
import asyncio
from acme.demo.artifacts import SITE_ARTIFACTS
from acme.demo.vm_deploy import deploy_to_vm

async def main():
    result = await deploy_to_vm(
        dict(SITE_ARTIFACTS),
        vm_url="${DEMO_VM_URL}",
        deploy_key="${DEMO_VM_DEPLOY_KEY}",
    )
    print("VM baseline deployed:", result.get("live_ok"), result.get("site_url"))

asyncio.run(main())
PY
else
  echo "WARN: $SECRETS missing — skip VM repair (run azure/demo-squad-stack.sh first)" >&2
fi

echo "==> 2/3 Reset demo tenants + wipe GitHub/VM via API"
curl -sf -X POST "$API/api/v1/demo/reset" | python3 -m json.tool

echo "==> 3/3 External probes"
curl -sf "${DEMO_VM_URL:-http://20.199.121.183:9090}/health" && echo " receiver OK" || echo " receiver FAIL"
curl -sk "${DEMO_VM_SITE_URL:-https://20.199.121.183}/api/health" && echo "" || echo " site API FAIL"
curl -sf "https://KamilBourouiba.github.io/erebor-site-demo/" -o /dev/null -w "Pages HTTP %{http_code}\n"

echo "✅ Reclean complete — demo UI: https://kamilbourouiba.github.io/ACME/demo.html"
