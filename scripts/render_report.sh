#!/usr/bin/env bash
# Render report/report.md -> report/report.pdf (pandoc -> HTML -> headless Chrome).
#   scripts/render_report.sh        # needs pandoc and google-chrome (or chromium) on PATH
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME=$(command -v google-chrome || command -v chromium || command -v chromium-browser)
sed 's/^\\newpage$/<div class="newpage"><\/div>/' report/report.md \
  | pandoc -f markdown -t html5 --standalone --embed-resources --css report/style.css \
      --metadata pagetitle="RAHBAR A3 report" -o report/report.html
"$CHROME" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf=report/report.pdf \
  "file://$PWD/report/report.html" 2>/dev/null
command -v pdfinfo >/dev/null && pdfinfo report/report.pdf | grep Pages || true
