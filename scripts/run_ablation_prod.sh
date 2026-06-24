#!/usr/bin/env bash
# Run ACME MemoryBench on prod under ablation toggles (ACME-only, ~5 min each).
set -euo pipefail
# Allow individual ablation runs to fail without stopping the sweep
set +e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="${ACME_API_URL:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
ENV_FILE="${ROOT}/azure/api-key.env"
RG="${RG:-rg-acme}"
API_APP="${API_APP:-acme-api}"
OUT="${ROOT}/benchmark-results"
mkdir -p "$OUT"
STAMP=$(date -u +%Y%m%d%H%M%S)

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi
[[ -n "${API_KEY:-}" ]] || { echo "Missing API_KEY" >&2; exit 1; }

HDR=(-H "X-API-Key: ${API_KEY}" -H "Content-Type: application/json")

run_memorybench() {
  local label="$1"
  local outfile="$OUT/ablation-${label}-${STAMP}.json"
  echo "==> MemoryBench ($label)"
  local http_code=0 attempt
  for attempt in 1 2 3; do
    echo "  attempt $attempt/3"
    sleep 30
    http_code=$(curl -s -o "$outfile" -w "%{http_code}" -X POST "${API}/api/v1/benchmark/memorybench" "${HDR[@]}" --max-time 900)
    echo "  HTTP:${http_code}"
    if [[ "$http_code" == "200" ]]; then
      break
    fi
    echo "  ERROR body:" && head -c 300 "$outfile" 2>/dev/null && echo
    sleep 60
  done
  if [[ "$http_code" != "200" ]]; then
    return 1
  fi
  python3 - <<PY
import json
d = json.load(open("$outfile"))
overall = d.get("overall_score", 0)
if overall <= 0 and d.get("details", {}).get("failures"):
    print(f"  WARN: benchmark returned 0 (failures={len(d['details']['failures'])})")
    raise SystemExit(1)
print(f"  overall={overall:.4f} retention={d['retention_score']:.4f} "
      f"groundedness={d['hallucination_resistance_score']:.4f} "
      f"feedback={d['feedback_correction_score']:.4f} belief={d['belief_quality_score']:.4f}")
PY
  echo "  cooldown 120s before next deploy..."
  sleep 120
}

wait_for_revision() {
  local suffix="$1"
  local rev_name="${API_APP}--${suffix}"
  echo "  waiting for revision ${rev_name} (100% traffic)..."
  for _ in $(seq 1 60); do
    local active
    active=$(az containerapp revision list -n "$API_APP" -g "$RG" \
      --query "[?properties.trafficWeight==\`100\`].name" -o tsv 2>/dev/null || true)
    if [[ "$active" == "$rev_name" ]]; then
      echo "  active: $active"
      return 0
    fi
    sleep 5
  done
  echo "  WARN: revision $rev_name not active after 5 min (continuing)" >&2
}

wait_for_stable_health() {
  echo "  warming up (postgres + neo4j + LLM)..."
  local ok=0
  for _ in $(seq 1 24); do
    if curl -sf "${API}/api/v1/health" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('postgres') and d.get('neo4j') and d.get('llm') else 1)" 2>/dev/null; then
      ok=$((ok + 1))
      if [[ $ok -ge 2 ]]; then
        sleep 90
        return 0
      fi
    else
      ok=0
    fi
    sleep 10
  done
  echo "  WARN: LLM health not stable — sleeping 90s before benchmark" >&2
  sleep 90
}

deploy_ablation() {
  local suffix="$1"
  shift
  echo "==> Deploy revision $suffix: $*"
  az containerapp update -n "$API_APP" -g "$RG" \
    --set-env-vars "$@" \
    --revision-suffix "$suffix" -o none
  wait_for_revision "$suffix"
  wait_for_stable_health
}

# Full ACME baseline: use historical compare job (13 scenarios) — skip redeploy + benchmark
echo "==> Full ACME baseline from job 3b31e5e3 (13-scenario compare, not re-run)"
cat > "$OUT/ablation-full-${STAMP}.json" <<'EOF'
{"retention_score":1.0,"feedback_correction_score":1.0,"hallucination_resistance_score":1.0,"belief_quality_score":0.7,"overall_score":0.925,"details":{"benchmark_version":"v3","source":"compare_job_3b31e5e3"}}
EOF
python3 - <<PY
import json
d = json.load(open("$OUT/ablation-full-${STAMP}.json"))
print(f"  overall={d['overall_score']:.4f} retention={d['retention_score']:.4f} "
      f"groundedness={d['hallucination_resistance_score']:.4f} "
      f"feedback={d['feedback_correction_score']:.4f} belief={d['belief_quality_score']:.4f}")
PY

deploy_ablation "ablation-${STAMP}-nocontrarian" \
  "AZURE_OPENAI_DEPLOYMENT=gpt-4.1" \
  "ABLATION_DISABLE_CONTRARIAN=true" \
  "ABLATION_DISABLE_BELIEF_SYNC=false" \
  "ABLATION_DISABLE_VECTOR=false"

run_memorybench "no-contrarian"

deploy_ablation "ablation-${STAMP}-nobelief" \
  "AZURE_OPENAI_DEPLOYMENT=gpt-4.1" \
  "ABLATION_DISABLE_CONTRARIAN=false" \
  "ABLATION_DISABLE_BELIEF_SYNC=true" \
  "ABLATION_DISABLE_VECTOR=false"

run_memorybench "no-belief-sync"

deploy_ablation "ablation-${STAMP}-novector" \
  "AZURE_OPENAI_DEPLOYMENT=gpt-4.1" \
  "ABLATION_DISABLE_CONTRARIAN=false" \
  "ABLATION_DISABLE_BELIEF_SYNC=false" \
  "ABLATION_DISABLE_VECTOR=true"

run_memorybench "no-vector"

# Restore production defaults
deploy_ablation "ablation-${STAMP}-restore" \
  "AZURE_OPENAI_DEPLOYMENT=gpt-4.1" \
  "ABLATION_DISABLE_CONTRARIAN=false" \
  "ABLATION_DISABLE_BELIEF_SYNC=false" \
  "ABLATION_DISABLE_VECTOR=false"

echo "✅ Ablation results in $OUT/ablation-*-${STAMP}.json"
