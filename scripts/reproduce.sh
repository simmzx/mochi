#!/usr/bin/env bash
# Reproduce every artefact of the MOCHI project (macOS / Linux).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
echo "== repository: $root"

echo
echo "[1/4] installing runtime dependencies"
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet -r requirements.txt

echo
echo "[2/4] offline self-checks"
python3 tests/run_checks.py

echo
echo "[3/4] four scenarios (offline engine)"
python3 cases/run_all.py --engine offline

if [[ "${1:-}" != "--skip-docs" ]]; then
  echo
  echo "[4/4] rebuilding report and slides"
  ( cd paper && python3 make_report.py && python3 build_deck.py )
  echo "LaTeX report: (cd paper/latex && tectonic -X compile main.tex)"
fi

echo
echo "Done. Run directories are under outputs/."
