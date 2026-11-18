#!/usr/bin/env bash
# One-time freeze: signed commit + signed tag prereg-v1, before any scored run.
# Safe to rerun: it skips whatever is already done.
set -euo pipefail
cd "$(dirname "$0")/.."

git config user.name "Alireza Darbehani"
git config user.email "alireza1989@users.noreply.github.com"
git config gpg.format ssh
git config user.signingkey ~/.ssh/id_ed25519_signing.pub
git config gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
git config commit.gpgsign true
git config tag.gpgsign true

python3 scripts/check_data.py

git add -A
if git diff --cached --name-only | grep -E '(^|/)\.env$|fresh_set\.jsonl$|build_fresh_set\.py$'; then
  echo "STOP: a secret or withheld file is staged. Nothing was committed."; exit 1
fi

if ! git rev-parse --verify -q HEAD >/dev/null; then
  git commit -S -m "Pre-registration: lineup, prompts, data, label rules and analysis plan, frozen before any scored run"
else
  echo "A commit already exists; not committing again."
fi
if ! git rev-parse --verify -q prereg-v1 >/dev/null; then
  git tag -s prereg-v1 -m "Frozen before any scored run"
fi

git log --show-signature -1 | head -5
git tag -v prereg-v1 2>&1 | grep -i "good" || { echo "Tag signature not verified"; exit 1; }
echo "Frozen: prereg-v1"
