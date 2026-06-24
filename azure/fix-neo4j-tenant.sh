#!/usr/bin/env bash
# One-time Neo4j migration: drop legacy name-only constraint, set tenant_id on all nodes.
set -euo pipefail
RG="${RG:-rg-acme}"
NEO4J_APP="${NEO4J_APP:-acme-neo4j}"

echo "==> Restart API to apply Neo4j constraint migration on connect"
az containerapp revision restart -n acme-api -g rg-acme --revision $(az containerapp revision list -n acme-api -g rg-acme --query "[?properties.active].name | [0]" -o tsv) -o none 2>/dev/null || \
az containerapp update -n acme-api -g rg-acme \
  --image "$(az containerapp show -n acme-api -g rg-acme --query 'properties.template.containers[0].image' -o tsv)" \
  --revision-suffix "neo4jfix-$(date +%s | tail -c 6)" -o none

echo "✅ API restarted — _init_constraints drops entity_name and sets tenant_id on legacy nodes"
