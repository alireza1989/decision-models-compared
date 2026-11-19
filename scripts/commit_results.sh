#!/usr/bin/env bash
# Signed commit of every raw result, the cost ledger and the analysis outputs, plus the harness changes
# made during the runs (each one is listed under Deviations in PREREGISTRATION.md).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/check_runs.py | tail -3
git add .gitignore PREREGISTRATION.md README.md run_all.sh dmc scripts tests results/raw results/cost_ledger.jsonl \
        results/summary.json results/tables
if git diff --cached --name-only | grep -E '(^|/)\.env$|_discarded'; then echo "STOP: a secret or discarded file is staged"; exit 1; fi
git commit -S -m "Results: all scored runs (r1, r2, r3), latency, cost ledger and analysis outputs"
git tag -s results-v1 -m "All scored runs complete"
git tag -v results-v1 2>&1 | grep -i "good" >/dev/null && echo "Committed and tagged: results-v1"
