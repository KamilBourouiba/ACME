#!/usr/bin/env bash
# LongMemEval on production API (async job + poll).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="${ACME_API_URL:-https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io}"
ENV_FILE="${ROOT}/azure/api-key.env"
OUT="${ROOT}/benchmark-results"
mkdir -p "$OUT"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

TYPES="${LONGMEMEVAL_TYPES:-knowledge-update}"
# Set LONGMEMEVAL_TYPES=all for full oracle split (500 Q)
if [[ "${LONGMEMEVAL_TYPES}" == "all" ]]; then
  TYPES=""
else
  TYPES="${LONGMEMEVAL_TYPES}"
fi
LIMIT="${LONGMEMEVAL_LIMIT:-}"
SYSTEMS="${LONGMEMEVAL_SYSTEMS:-acme,rag,memgpt}"
POLL_SEC="${LONGMEMEVAL_POLL_SEC:-30}"
MAX_WAIT_MIN="${LONGMEMEVAL_MAX_WAIT_MIN:-180}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi
[[ -n "${API_KEY:-}" ]] || { echo "Missing API_KEY — run azure/set-api-key.sh" >&2; exit 1; }

HDR=(-H "X-API-Key: ${API_KEY}" -H "Content-Type: application/json")

BODY=$(python3 - <<PY
import json, os
types_raw = os.environ.get("LONGMEMEVAL_TYPES", "knowledge-update").strip()
if types_raw == "all":
    types = None
elif types_raw:
    types = types_raw.split(",")
else:
    types = None
limit_raw = os.environ.get("LONGMEMEVAL_LIMIT", "").strip()
limit = int(limit_raw) if limit_raw else None
systems = "${SYSTEMS}".split(",")
print(json.dumps({
    "question_types": types,
    "limit": limit,
    "systems": systems,
}))
PY
)

echo "==> Premium ingress (long benchmark)"
bash "${ROOT}/azure/configure-premium-ingress.sh" 2>/dev/null || true

echo "==> Health"
curl -sf "${API}/api/v1/health" | tee "$OUT/longmemeval-health-${STAMP}.json"

echo "==> Start LongMemEval async (types=${TYPES:-all})"
START_RESP=$(curl -sf -X POST "${API}/api/v1/benchmark/longmemeval/async" "${HDR[@]}" -d "$BODY")
echo "$START_RESP" | tee "$OUT/longmemeval-start-${STAMP}.json"
JOB_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])" <<<"$START_RESP")

echo "==> Poll job $JOB_ID (max ${MAX_WAIT_MIN} min)"
DEADLINE=$(( $(date +%s) + MAX_WAIT_MIN * 60 ))
while [[ $(date +%s) -lt $DEADLINE ]]; do
  STATUS_JSON=$(curl -sf "${API}/api/v1/benchmark/compare/jobs/${JOB_ID}" "${HDR[@]}")
  STATUS=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" <<<"$STATUS_JSON")
  echo "  $(date -u +%H:%M:%S) status=$STATUS"
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    echo "$STATUS_JSON" | tee "$OUT/longmemeval-${STAMP}.json"
    cp "$OUT/longmemeval-${STAMP}.json" "$OUT/longmemeval-latest.json"
    if [[ "$STATUS" == "completed" ]]; then
      python3 - <<PY
import json
d = json.load(open("$OUT/longmemeval-latest.json"))
for row in d.get("result", {}).get("summary_table", []):
    print(f"  {row['system']:8s} accuracy={row['accuracy']:.3f}  by_type={row.get('by_type')}")
PY
      echo "✅ Done — $OUT/longmemeval-latest.json"
      exit 0
    fi
    echo "❌ Job failed" >&2
    exit 1
  fi
  sleep "$POLL_SEC"
done

echo "❌ Timed out after ${MAX_WAIT_MIN} minutes (job may still be running: $JOB_ID)" >&2
exit 1
