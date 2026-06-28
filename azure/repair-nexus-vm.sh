#!/usr/bin/env bash
# Repair Nexus VM stack (fix .env, redeploy docker, verify health).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_FILE="${ROOT}/azure/demo-squad.env"
RG="${RG:-rg-nexus-demo}"
VM_NAME="${DEMO_VM_NAME:-nexus-squad-vm}"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "Missing $SECRETS_FILE — run azure/demo-squad-stack.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$SECRETS_FILE"

DNS_ZONE="${DEMO_PG_SERVER}.private.postgres.database.azure.com"
PG_A_NAME="$(az network private-dns record-set a list -g "$RG" -z "$DNS_ZONE" --query "[?name!='@' && name!=''].name | [0]" -o tsv 2>/dev/null || true)"
if [[ -n "$PG_A_NAME" ]]; then
  DEMO_PG_HOST="${PG_A_NAME}.${DNS_ZONE}"
  DATABASE_URL_NEXUS="postgresql://${DEMO_PG_USER}:${DEMO_PG_PASSWORD}@${DEMO_PG_HOST}:5432/${DEMO_PG_DB}?sslmode=require"
fi

echo "==> Postgres host: ${DEMO_PG_HOST}"
echo "==> Fix .env + redeploy docker on $VM_NAME"
if ! timeout 600 az vm run-command invoke -g "$RG" -n "$VM_NAME" --command-id RunShellScript \
  --scripts "cat > /opt/nexus-site/.env <<EOF
DATABASE_URL=${DATABASE_URL_NEXUS}
DEPLOY_KEY=${DEMO_VM_DEPLOY_KEY}
EOF
chmod 600 /opt/nexus-site/.env
cd /opt/nexus-site
docker-compose down --remove-orphans 2>/dev/null || true
docker rm -f nexus-site_api_1 nexus-site_nginx_1 2>/dev/null || true
if [ ! -f /opt/nexus-site/certs/server.crt ]; then
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /opt/nexus-site/certs/server.key \
    -out /opt/nexus-site/certs/server.crt \
    -subj "/CN=nexus-squad-vm"
fi
docker-compose build --no-cache api
docker-compose up -d --force-recreate
sleep 45
docker ps
curl -sk https://127.0.0.1/api/health" \
  -o json | python3 -c "import sys,json; print(json.load(sys.stdin)['value'][0]['message'])"; then
  echo "Repair run-command failed or timed out" >&2
  exit 1
fi

if curl -sf "${DEMO_VM_URL}/health" &>/dev/null; then
  echo "==> Deploy receiver OK — skip reinstall"
else
  "${ROOT}/azure/install-nexus-vm.sh"
fi

echo "==> External check"
curl -sk "${DEMO_VM_SITE_URL}/api/health"
echo ""
