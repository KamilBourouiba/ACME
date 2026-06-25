#!/usr/bin/env bash
# Export docs/PAPER.md -> docs/PAPER.tex -> docs/PAPER.pdf (XeLaTeX)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS="${ROOT}/docs"
TEX="${DOCS}/PAPER.tex"
PDF="${DOCS}/PAPER.pdf"

for cmd in pandoc xelatex; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Missing $cmd — install: brew install pandoc basictex" >&2
    exit 1
  fi
done

echo "==> Markdown -> LaTeX"
pandoc "${DOCS}/PAPER.md" -o "$TEX" \
  --standalone \
  --template="${DOCS}/paper-template.tex" \
  --from markdown+raw_tex \
  --to latex \
  --shift-heading-level-by=-1 \
  --highlight-style=tango

echo "==> XeLaTeX (pass 1)"
(cd "$DOCS" && xelatex -interaction=nonstopmode -halt-on-error PAPER.tex >/dev/null)

echo "==> XeLaTeX (pass 2)"
(cd "$DOCS" && xelatex -interaction=nonstopmode -halt-on-error PAPER.tex >/dev/null)

# Clean auxiliary files (keep .tex)
rm -f "${DOCS}/PAPER.aux" "${DOCS}/PAPER.log" "${DOCS}/PAPER.out"

echo "✅ Wrote ${PDF}"
echo "   LaTeX source: ${TEX}"
