"""Checks every frozen data file against data/SHA256SUMS (works on macOS and Linux)."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = 0
for line in (ROOT / "data" / "SHA256SUMS").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    path = ROOT / name
    ok = path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest
    bad += not ok
    print(f"{'OK ' if ok else 'BAD'} {name}")
sys.exit(1 if bad else 0)
