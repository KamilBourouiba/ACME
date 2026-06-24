# Azure cost estimate (~USD 100/month)

Budget target: **~$100/month** for ACME production + benchmarks.

| Resource | SKU / config | Est. monthly |
|----------|----------------|--------------|
| Container Apps — API | Consumption, 1-2 replicas | $15-25 |
| Container Apps — Neo4j | Consumption | $10-20 |
| Postgres Flexible | `Standard_B1ms`, 32 GB, francecentral | $25-35 |
| Premium ingress (Ingress-D4, 2 nodes) | Active during benchmarks | $30-50 when enabled |
| Azure OpenAI GPT-4.1 + embeddings | Pay-per-token (benchmarks) | $5-20 |
| ACR Basic | Image storage | ~$5 |

**Typical steady state (premium ingress off):** ~$55-75/month.  
**During benchmark weeks (premium ingress on):** ~$85-100/month.

## Scripts

| Script | Purpose |
|--------|---------|
| `azure/configure-premium-ingress.sh` | Enable before MemoryBench/compare (~30 min timeout) |
| `azure/configure-consumption-ingress.sh` | Disable premium to save cost |
| `azure/postgres-flexible.sh` | Managed Postgres + pgvector |
| `azure/set-api-key.sh` | Rotate benchmark API key |

## API key rotation

```bash
API_KEY=$(openssl rand -hex 24) ./azure/set-api-key.sh
```

New key written to `azure/api-key.env` (gitignored). Update any clients using `X-API-Key`.
