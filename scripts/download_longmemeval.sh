#!/usr/bin/env bash
# Download official LongMemEval oracle dataset (evidence sessions only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${ROOT}/data/longmemeval/longmemeval_oracle.json"
URL="https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json"

mkdir -p "$(dirname "$DEST")"
echo "==> Downloading LongMemEval oracle dataset"
curl -fsSL "$URL" -o "$DEST"
python3 -c "import json; d=json.load(open('$DEST')); print(f'✅ {len(d)} questions -> $DEST')"
