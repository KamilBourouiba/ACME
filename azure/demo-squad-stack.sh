#!/usr/bin/env bash
# Secure Nexus squad stack: private Postgres (~1 TB) + API VM (TLS, NSG).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="${RG:-rg-nexus-demo}"
LOCATION="${LOCATION:-francecentral}"
FALLBACK_LOCATION="${FALLBACK_LOCATION:-westeurope}"

VNET="${DEMO_VNET:-nexus-demo-vnet}"
VM_SUBNET="${DEMO_VM_SUBNET:-squad-api}"
PG_SUBNET="${DEMO_PG_SUBNET:-squad-db}"
VM_NAME="${DEMO_VM_NAME:-nexus-squad-vm}"
NSG_NAME="${DEMO_NSG:-nexus-squad-nsg}"
PUBLIC_IP="${DEMO_PUBLIC_IP:-nexus-squad-pip}"
NIC_NAME="${DEMO_NIC:-nexus-squad-nic}"

PG_SERVER="${DEMO_PG_SERVER:-nexus-squad-pg}"
PG_DB="${DEMO_PG_DB:-nexus}"
PG_USER="${DEMO_PG_USER:-nexusadmin}"
PG_SKU="${DEMO_PG_SKU:-Standard_D4ds_v5}"
PG_STORAGE_GB="${DEMO_PG_STORAGE_GB:-1024}"

VM_SIZE="${DEMO_VM_SIZE:-Standard_D4s_v5}"
ADMIN_USER="${DEMO_VM_ADMIN:-azureuser}"
SECRETS_FILE="${ROOT_DIR}/azure/demo-squad.env"

if [[ -f "$SECRETS_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
fi

if [[ -z "${PG_PASSWORD:-}" ]]; then
  PG_PASSWORD="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
fi
if [[ -z "${DEPLOY_KEY:-}" ]]; then
  DEPLOY_KEY="$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)"
fi

ADMIN_IP="${ADMIN_IP:-$(curl -sf -4 https://ifconfig.me 2>/dev/null || curl -sf https://ifconfig.me 2>/dev/null || echo "0.0.0.0")}"

if [[ "$VNET" == "nexus-demo-vnet" ]]; then
  VNET="nexus-demo-vnet-${LOCATION}"
fi

echo "==> Resource group: $RG (stack location: $LOCATION)"
az group create --name "$RG" --location "$LOCATION" -o none

echo "==> VNet + subnets (private DB, public API VM)"
if ! az network vnet show -g "$RG" -n "$VNET" &>/dev/null; then
  az network vnet create -g "$RG" -n "$VNET" -l "$LOCATION" \
    --address-prefixes 10.60.0.0/16 \
    --subnet-name "$VM_SUBNET" --subnet-prefixes 10.60.1.0/24 \
    -o none
  az network vnet subnet create -g "$RG" --vnet-name "$VNET" -n "$PG_SUBNET" \
    --address-prefixes 10.60.2.0/24 \
    --delegations Microsoft.DBforPostgreSQL/flexibleServers \
    -o none
fi

echo "==> NSG (443/80 public, SSH from ADMIN_IP=$ADMIN_IP only)"
if ! az network nsg show -g "$RG" -n "$NSG_NAME" &>/dev/null; then
  az network nsg create -g "$RG" -n "$NSG_NAME" -l "$LOCATION" -o none
  az network nsg rule create -g "$RG" --nsg-name "$NSG_NAME" -n AllowHTTPS \
    --priority 100 --direction Inbound --access Allow --protocol Tcp \
    --destination-port-ranges 443 80 --source-address-prefixes Internet -o none
  az network nsg rule create -g "$RG" --nsg-name "$NSG_NAME" -n AllowSSH \
    --priority 110 --direction Inbound --access Allow --protocol Tcp \
    --destination-port-ranges 22 --source-address-prefixes "$ADMIN_IP" -o none
  az network nsg rule create -g "$RG" --nsg-name "$NSG_NAME" -n AllowDeploy \
    --priority 120 --direction Inbound --access Allow --protocol Tcp \
    --destination-port-ranges 9090 --source-address-prefixes Internet -o none
fi

echo "==> PostgreSQL Flexible Server ($PG_SKU, ${PG_STORAGE_GB}GB, private VNet) in $LOCATION"
if ! az postgres flexible-server show -g "$RG" -n "$PG_SERVER" &>/dev/null; then
  az postgres flexible-server create \
    -g "$RG" -n "$PG_SERVER" -l "$LOCATION" \
    --tier GeneralPurpose --sku-name "$PG_SKU" \
    --storage-size "$PG_STORAGE_GB" \
    --version 16 \
    --admin-user "$PG_USER" \
    --admin-password "$PG_PASSWORD" \
    --vnet "$VNET" --subnet "$PG_SUBNET" \
    --private-dns-zone "${PG_SERVER}.private.postgres.database.azure.com" \
    --yes \
    -o none
fi

DNS_ZONE="${PG_SERVER}.private.postgres.database.azure.com"
PG_PRIVATE_HOST="${PG_SERVER}.private.postgres.database.azure.com"
PG_A_NAME="$(az network private-dns record-set a list -g "$RG" -z "$DNS_ZONE" --query "[?name!='@' && name!=''].name | [0]" -o tsv 2>/dev/null || true)"
if [[ -n "$PG_A_NAME" ]]; then
  PG_PRIVATE_HOST="${PG_A_NAME}.${DNS_ZONE}"
fi
DATABASE_URL="postgresql://${PG_USER}:${PG_PASSWORD}@${PG_PRIVATE_HOST}:5432/${PG_DB}?sslmode=require"

az postgres flexible-server db create -g "$RG" -s "$PG_SERVER" -d "$PG_DB" -o none 2>/dev/null || true

echo "==> Link VNet to Postgres private DNS zone"
DNS_ZONE="${PG_SERVER}.private.postgres.database.azure.com"
az network private-dns link vnet create \
  -g "$RG" \
  -n "${VNET}-pg-link" \
  -z "$DNS_ZONE" \
  --virtual-network "$VNET" \
  --registration-enabled false \
  -o none 2>/dev/null || true

echo "==> Public IP + NIC for API VM"
if ! az network public-ip show -g "$RG" -n "$PUBLIC_IP" &>/dev/null; then
  az network public-ip create -g "$RG" -n "$PUBLIC_IP" -l "$LOCATION" --sku Standard -o none
fi
if ! az network nic show -g "$RG" -n "$NIC_NAME" &>/dev/null; then
  az network nic create -g "$RG" -n "$NIC_NAME" -l "$LOCATION" \
    --vnet-name "$VNET" --subnet "$VM_SUBNET" \
    --network-security-group "$NSG_NAME" \
    --public-ip-address "$PUBLIC_IP" \
    --dns-servers 168.63.129.16 \
    -o none
fi

VM_IP="$(az network public-ip show -g "$RG" -n "$PUBLIC_IP" --query ipAddress -o tsv)"
CLOUD_INIT="${ROOT_DIR}/azure/cloud-init/nexus-squad-vm.yaml"
TMP_INIT="$(mktemp)"
sed \
  -e "s|__DATABASE_URL__|${DATABASE_URL}|g" \
  -e "s|__DEPLOY_KEY__|${DEPLOY_KEY}|g" \
  "$CLOUD_INIT" > "$TMP_INIT"

echo "==> Linux VM ($VM_SIZE) — docker stack bootstrap"
if ! az vm show -g "$RG" -n "$VM_NAME" &>/dev/null; then
  az vm create -g "$RG" -n "$VM_NAME" -l "$LOCATION" \
    --size "$VM_SIZE" \
    --nics "$NIC_NAME" \
    --image "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest" \
    --admin-username "$ADMIN_USER" \
    --generate-ssh-keys \
    --custom-data "$TMP_INIT" \
    -o none
else
  echo "   VM $VM_NAME already exists — run-command to refresh stack if needed"
fi
rm -f "$TMP_INIT"

VM_DEPLOY_URL="http://${VM_IP}:9090"
SITE_URL="https://${VM_IP}"

cat > "$SECRETS_FILE" <<EOF
DEMO_VM_NAME=${VM_NAME}
DEMO_VM_IP=${VM_IP}
DEMO_VM_URL=${VM_DEPLOY_URL}
DEMO_VM_DEPLOY_KEY=${DEPLOY_KEY}
DEMO_VM_SITE_URL=${SITE_URL}
DEMO_PG_SERVER=${PG_SERVER}
DEMO_PG_HOST=${PG_PRIVATE_HOST}
DEMO_PG_USER=${PG_USER}
DEMO_PG_PASSWORD=${PG_PASSWORD}
DEMO_PG_DB=${PG_DB}
DATABASE_URL_NEXUS=${DATABASE_URL}
EOF
chmod 600 "$SECRETS_FILE"

echo ""
echo "✅ Nexus squad stack ready"
echo "   VM public IP:     ${VM_IP}"
echo "   Site (TLS):       ${SITE_URL}  (self-signed cert on first boot)"
echo "   Deploy webhook:   ${VM_DEPLOY_URL}/deploy"
echo "   Postgres:         ${PG_PRIVATE_HOST} (${PG_STORAGE_GB} GB, private)"
echo "   VM size:          ${VM_SIZE} (4 vCPU / 16 GiB)"
echo "   Postgres SKU:     ${PG_SKU} (~16 GiB RAM)"
echo "   Credentials:      azure/demo-squad.env (gitignored)"
echo ""
echo "Wire ACME API:"
echo "  DEMO_VM_URL=${VM_DEPLOY_URL}"
echo "  DEMO_VM_DEPLOY_KEY=<from demo-squad.env>"
echo "  DEMO_VM_SITE_URL=${SITE_URL}"
echo ""
echo "Seed stack: ./azure/seed-nexus-vm.sh"
