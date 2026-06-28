#!/usr/bin/env bash
# Push site stack files to VM via az run-command (avoids CLI length limits).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_FILE="${ROOT}/azure/demo-squad.env"
RG="${RG:-rg-nexus-demo}"
VM_NAME="${DEMO_VM_NAME:-nexus-squad-vm}"
SITE="${ROOT}/acme/demo/site"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "Run azure/demo-squad-stack.sh first." >&2
  exit 1
fi

TMP="$(mktemp)"
python3 <<PY > "$TMP"
import base64
from pathlib import Path

site = Path("${SITE}")
files = {
    "deploy_receiver.py": site / "deploy_receiver.py",
    "server.py": site / "server.py",
    "requirements.txt": site / "requirements.txt",
    "Dockerfile": site / "Dockerfile",
    "docker-compose.yml": site / "docker-compose.yml",
    "nginx.conf": site / "nginx.conf",
}
print("#!/bin/bash")
print("set -euo pipefail")
print("mkdir -p /opt/nexus-site/static /opt/nexus-site/certs")
for name, path in files.items():
    b64 = base64.b64encode(path.read_bytes()).decode()
    print(f"python3 -c \"import base64; open('/opt/nexus-site/{name}','wb').write(base64.b64decode('{b64}'))\"")
print("cat > /etc/systemd/system/nexus-deploy.service <<'UNIT'")
print("[Unit]")
print("Description=Nexus squad deploy receiver")
print("After=docker.service")
print("Requires=docker.service")
print("")
print("[Service]")
print("Type=simple")
print("WorkingDirectory=/opt/nexus-site")
print("EnvironmentFile=/opt/nexus-site/.env")
print("Environment=DEPLOY_PORT=9090")
print("ExecStart=/usr/bin/python3 /opt/nexus-site/deploy_receiver.py")
print("Restart=always")
print("")
print("[Install]")
print("WantedBy=multi-user.target")
print("UNIT")
print("systemctl daemon-reload")
print("systemctl enable nexus-deploy")
print("systemctl restart nexus-deploy")
print("sleep 3")
print("systemctl is-active nexus-deploy")
PY

echo "==> Install stack files + deploy receiver on $VM_NAME"
az vm run-command invoke -g "$RG" -n "$VM_NAME" \
  --command-id RunShellScript \
  --scripts @"$TMP" \
  -o json | python3 -c "import sys,json; print(json.load(sys.stdin)['value'][0]['message'])"
rm -f "$TMP"
