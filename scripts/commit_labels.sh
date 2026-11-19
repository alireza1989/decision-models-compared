#!/usr/bin/env bash
# Reveal and labels commit: must happen before any model sees a fresh-set message.
# Checks that the withheld files still match the hashes in PREREGISTRATION.md, then makes a signed commit and tag.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import hashlib, sys
want = {"data/fresh/fresh_set.jsonl": "68364c89c30c0f9c84efcc78650ae708319361a8921f2a6819a1fb3f9c47ef4e",
        "data/fresh/build_fresh_set.py": "f50a36af90c41bce7af6274ad7cde4a8fea839f4d6a93d8e39e83cb61da0d917"}
bad = [p for p, h in want.items() if hashlib.sha256(open(p, "rb").read()).hexdigest() != h]
print("hashes match the pre-registration" if not bad else f"HASH MISMATCH: {bad}")
sys.exit(1 if bad else 0)
PY
if GIT_OPTIONAL_LOCKS=0 git ls-files --error-unmatch data/fresh/labels_final.jsonl >/dev/null 2>&1; then
  echo "labels_final.jsonl is already committed; nothing to do."; exit 0
fi
git add .gitignore PREREGISTRATION.md README.md run_all.sh dmc scripts tests \
        data/fresh/fresh_set.jsonl data/fresh/build_fresh_set.py data/fresh/labels_blind.jsonl \
        data/fresh/labels_final.jsonl data/fresh/agreement.json data/fresh/disagreements.md
if git diff --cached --name-only | grep -E '(^|/)\.env$'; then echo "STOP: .env is staged"; exit 1; fi
git commit -S -m "Fresh set: reveal proposed labels, blind pass, final labels; harness fixes and Sonnet baseline (see Deviations)"
git tag -s labels-v1 -m "Final fresh-set labels, committed before any model saw the fresh set"
git tag -v labels-v1 2>&1 | grep -i "good" >/dev/null && echo "Committed and tagged: labels-v1"
