#!/usr/bin/env bash
# Run MemoryBench compare async against prod with a specific Azure OpenAI deployment.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="${ACME_API_URL:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
DEPLOYMENT="${1:?Usage: $0 <azure-openai-deployment> [revision-suffix]}"
SUFFIX="${2:-bench-$(echo "$DEPLOYMENT" | tr '.' '-')}"
ENV_FILE="${ROOT}/azure/api-key.env"
RG="${RG:-rg-acme}"
API_APP="${API_APP:-acme-api}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi
[[ -n "${API_KEY:-}" ]] || { echo "Missing API_KEY" >&2; exit 1; }

HDR=(-H "X-API-Key: ${API_KEY}" -H "Content-Type: application/json")
OUT="${ROOT}/benchmark-results"
mkdir -p "$OUT"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TAG="${DEPLOYMENT}-${STAMP}"

echo "==> Switch API to deployment: $DEPLOYMENT (revision: $SUFFIX)"
az containerapp update -n "$API_APP" -g "$RG" \
  --set-env-vars "AZURE_OPENAI_DEPLOYMENT=${DEPLOYMENT}" \
  --revision-suffix "$SUFFIX" -o none

echo "==> Wait for healthy"
for i in $(seq 1 30); do
  if curl -sf "${API}/api/v1/health" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='healthy' else 1)"; then
    curl -sf "${API}/api/v1/health" | tee "$OUT/health-${TAG}.json"
    break
  fi
  sleep 5
done

echo "==> Compare async ($DEPLOYMENT)"
curl -sf -X POST "${API}/api/v1/benchmark/compare/async" "${HDR[@]}" -o "$OUT/compare-job-${TAG}.json"
JOB=$(python3 -c "import json; print(json.load(open('$OUT/compare-job-${TAG}.json'))['job_id'])")
echo "Job: $JOB"
for i in $(seq 1 80); do
  if curl -sf --retry 3 --retry-delay 2 "${API}/api/v1/benchmark/compare/jobs/${JOB}" "${HDR[@]}" -o "$OUT/compare-status-${TAG}.json"; then
    S=$(python3 -c "import json; print(json.load(open('$OUT/compare-status-${TAG}.json'))['status'])")
    echo "poll $i: $S"
    [[ "$S" == "completed" || "$S" == "failed" ]] && break
  else
    echo "poll $i: curl error, retrying..."
  fi
  sleep 15
done

cp "$OUT/compare-status-${TAG}.json" "$OUT/compare-${DEPLOYMENT}-latest.json"
python3 - <<PY
import json, pathlib, os
tag = "$TAG"
out = pathlib.Path("$OUT")
j = json.loads((out / f"compare-status-{tag}.json").read_text())
if j["status"] != "completed":
    raise SystemExit("FAILED: " + str(j.get("error")))
r = j["result"]
summary = {
    "deployment": "$DEPLOYMENT",
    "job_id": j["job_id"],
    "duration_sec": j.get("duration_sec"),
    "completed_at": j.get("completed_at"),
    "systems": {},
}
for k in ["acme", "rag_baseline", "memgpt_baseline", "langgraph_baseline"]:
    s = r[k]
    summary["systems"][k] = {
        "overall": s["overall_score"],
        "retention": s["retention_score"],
        "groundedness": s["hallucination_resistance_score"],
        "feedback": s["feedback_correction_score"],
        "belief": s["belief_quality_score"],
        "failures": s.get("details", {}).get("failures", []),
    }
(out / f"summary-{tag}.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
PY

echo "✅ $DEPLOYMENT results: $OUT/compare-${DEPLOYMENT}-latest.json"
