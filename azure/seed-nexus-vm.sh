#!/usr/bin/env bash
# Install deploy receiver on VM and push baseline stack.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_FILE="${ROOT}/azure/demo-squad.env"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "Run azure/demo-squad-stack.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$SECRETS_FILE"

"${ROOT}/azure/install-nexus-vm.sh"

echo "==> Wait for deploy receiver"
for i in $(seq 1 30); do
  if curl -sf "${DEMO_VM_URL}/health" &>/dev/null; then
    break
  fi
  sleep 10
done

echo "==> Push baseline stack"
cd "$ROOT"
python3 - <<PY
import asyncio
from acme.demo.agents import SITE_ARTIFACTS
from acme.demo.vm_deploy import deploy_to_vm

async def main():
    result = await deploy_to_vm(
        dict(SITE_ARTIFACTS),
        vm_url="${DEMO_VM_URL}",
        deploy_key="${DEMO_VM_DEPLOY_KEY}",
    )
    print("deployed", result)

asyncio.run(main())
PY

echo "✅ VM seeded — site: ${DEMO_VM_SITE_URL:-https://${DEMO_VM_IP}}"
