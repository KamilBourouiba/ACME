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

if curl -sf "${DEMO_VM_URL}/health" &>/dev/null; then
  echo "==> Deploy receiver already healthy at ${DEMO_VM_URL} — skipping install"
else
  echo "==> Install deploy receiver (may take a few minutes)"
  "${ROOT}/azure/install-nexus-vm.sh"
  echo "==> Wait for deploy receiver"
  for i in $(seq 1 30); do
    if curl -sf "${DEMO_VM_URL}/health" &>/dev/null; then
      break
    fi
    [[ "$i" -eq 30 ]] && { echo "Deploy receiver never came up" >&2; exit 1; }
    sleep 10
  done
fi

echo "==> Push baseline stack"
cd "$ROOT"
python3 - <<PY
import asyncio
from acme.demo.artifacts import SITE_ARTIFACTS
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
