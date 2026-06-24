#!/usr/bin/env bash
# Export docs/PAPER.md to PDF for arXiv submission (requires pandoc)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/docs/PAPER.pdf"
if ! command -v pandoc &>/dev/null; then
  echo "Install pandoc: brew install pandoc basictex" >&2
  exit 1
fi
pandoc "${ROOT}/docs/PAPER.md" -o "$OUT" --pdf-engine=pdflatex -V geometry:margin=1in
echo "✅ Wrote $OUT"
