#!/usr/bin/env bash
# Run MemoryBench v3 + compare async against production API (requires API key).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="${ACME_API_URL:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
ENV_FILE="${ROOT}/azure/api-key.env"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi
if [[ -z "${API_KEY:-}" ]]; then
  echo "Missing API_KEY — run azure/set-api-key.sh first" >&2
  exit 1
fi

HDR=(-H "X-API-Key: ${API_KEY}" -H "Content-Type: application/json")
OUT="${ROOT}/benchmark-results"
mkdir -p "$OUT"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="${OUT}/run-${STAMP}.log"
exec > >(tee -a "$LOG") 2>&1

export BENCH_OUT="$OUT" BENCH_STAMP="$STAMP"

echo "==> Health"
curl -sf "${API}/api/v1/health" | tee "$OUT/health-${STAMP}.json"

export BENCH_OUT="$OUT" BENCH_STAMP="$STAMP"

echo "==> MemoryBench v3"
curl -sf -X POST "${API}/api/v1/benchmark/memorybench" "${HDR[@]}" \
  --max-time 900 -o "$OUT/memorybench-${STAMP}.json" \
  -w " HTTP:%{http_code} TIME:%{time_total}s\n"
python3 - <<'PY'
import json, os, pathlib
out = os.environ["BENCH_OUT"]
stamp = os.environ["BENCH_STAMP"]
p = pathlib.Path(out) / f"memorybench-{stamp}.json"
d = json.loads(p.read_text())
print(f"Overall={d['overall_score']:.3f} Belief={d['belief_quality_score']:.3f} Scenarios={d['details']['scenarios_run']}")
PY

echo "==> Compare async"
curl -sf -X POST "${API}/api/v1/benchmark/compare/async" "${HDR[@]}" -o "$OUT/compare-job-${STAMP}.json"
JOB=$(python3 -c "import json; print(json.load(open('$OUT/compare-job-${STAMP}.json'))['job_id'])")
echo "Job: $JOB"
for i in $(seq 1 60); do
  curl -sf "${API}/api/v1/benchmark/compare/jobs/${JOB}" "${HDR[@]}" -o "$OUT/compare-status-${STAMP}.json"
  S=$(python3 -c "import json; print(json.load(open('$OUT/compare-status-${STAMP}.json'))['status'])")
  echo "poll $i: $S"
  [[ "$S" == "completed" || "$S" == "failed" ]] && break
  sleep 15
done
cp "$OUT/compare-status-${STAMP}.json" "$OUT/compare-latest.json"
python3 - <<'PY'
import json, os
out = os.environ["BENCH_OUT"]
stamp = os.environ["BENCH_STAMP"]
j = json.load(open(f"{out}/compare-status-{stamp}.json"))
if j["status"] != "completed":
    raise SystemExit("Compare failed: " + str(j.get("error")))
r = j["result"]
for k in ["acme", "rag_baseline", "memgpt_baseline", "langgraph_baseline"]:
    print(f"{k:22} overall={r[k]['overall_score']:.3f}")
PY

echo "✅ Results in $OUT/"
