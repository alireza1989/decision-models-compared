#!/usr/bin/env bash
# Reproduces every number in the post from scratch.
#
#   ./run_all.sh                 # everything
#   ./run_all.sh openrouter      # the 12 decision models (needs OPENROUTER_API_KEY in .env)
#   ./run_all.sh anthropic       # the Claude Haiku 5.5 baseline (needs ANTHROPIC_API_KEY in .env)
#   ./run_all.sh latency         # 200 sequential calls per model (Jev direct needs TYPESAFE_API_KEY)
#   ./run_all.sh analysis        # summary.json, tables and figures from saved results only
#
# Runs resume: rerunning a step skips every item already in results/raw/. Python 3.9 or newer;
# the API steps use the standard library only, the analysis needs numpy and matplotlib.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}
WHAT=${1:-all}

data() {
  [ -f data/test.jsonl ] || $PY data/prepare.py          # CLINC150 splits, as in the first post
  $PY scripts/check_data.py
}

# one provider through every scored set of run r1, then the repeats
gates() {
  local p=$1
  local fresh=yes
  [ -f data/fresh/labels_final.jsonl ] || { fresh=no; echo "labels_final.jsonl missing: skipping the fresh set"; }
  for cond in base scoped_v1 scoped_v2; do
    local val=val_near; [ "$cond" = base ] && val=val
    $PY -m dmc.run --provider "$p" --condition "$cond" --split "$val" --run r1
    $PY -m dmc.run --provider "$p" --condition "$cond" --split test --run r1
    if [ $fresh = yes ]; then $PY -m dmc.run --provider "$p" --condition "$cond" --split fresh --run r1; fi
  done
  $PY -m dmc.run --provider "$p" --split w2c_val --run r1
  $PY -m dmc.run --provider "$p" --split w2c_test --run r1
  $PY -m dmc.run --provider "$p" --split test --variant reversed --run r1
  $PY -m dmc.run --provider "$p" --split reworded --variant reworded --run r1
  $PY -m dmc.run --provider "$p" --split planted --run r1
  for run in r2 r3; do
    $PY -m dmc.run --provider "$p" --split test --run "$run"
    if [ $fresh = yes ]; then
      for cond in base scoped_v1 scoped_v2; do
        $PY -m dmc.run --provider "$p" --condition "$cond" --split fresh --run "$run"
      done
    fi
  done
}

case "$WHAT" in
  openrouter) data; gates openrouter ;;
  anthropic)  data; gates anthropic ;;
  latency)    $PY -m dmc.latency --budget-seconds 1e9 ;;
  analysis)   $PY -m dmc.evaluate ;;
  all)        data; gates openrouter; gates anthropic; $PY -m dmc.latency --budget-seconds 1e9; $PY -m dmc.evaluate ;;
  *) echo "unknown step: $WHAT"; exit 2 ;;
esac
