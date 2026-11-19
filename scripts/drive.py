"""Runs the scored OpenRouter steps in order, inside a time budget, resuming where the last call stopped.

Used where a shell call can only last a few minutes; run_all.sh does the same steps without a budget.
    python3 scripts/drive.py --budget 150 [--phase r1|repeats|all]
"""
import argparse
import subprocess
import sys
import time

R1 = [
    "--condition base --split val", "--condition base --split test",
    "--condition scoped_v1 --split val_near", "--condition scoped_v1 --split test",
    "--condition scoped_v2 --split val_near", "--condition scoped_v2 --split test",
    "--split w2c_val", "--split w2c_test",
    "--split test --variant reversed", "--split reworded --variant reworded", "--split planted",
]
REPEATS = ["--split test --run r2", "--split test --run r3"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=150)
    ap.add_argument("--phase", default="all", choices=["r1", "repeats", "all"])
    ap.add_argument("--workers", default="64")
    ap.add_argument("--batch", default="80")
    args = ap.parse_args()
    steps = [s + " --run r1" for s in R1] if args.phase in ("r1", "all") else []
    steps += REPEATS if args.phase in ("repeats", "all") else []
    t0 = time.time()
    for step in steps:
        left = args.budget - (time.time() - t0)
        if left < 15:
            print("budget used; call again to resume")
            return
        cmd = [sys.executable, "-u", "-m", "dmc.run", *step.split(), "--workers", args.workers, "--batch", args.batch, "--budget-seconds", str(int(left - 12))]
        out = subprocess.run(cmd, capture_output=True, text=True)
        lines = out.stdout.strip().splitlines()
        print(lines[0] if lines else "", "|", lines[-1] if lines else "", out.stderr.strip()[-300:])
        if out.returncode == 3:
            print("budget used; call again to resume")
            return
        if out.returncode != 0:
            print("step failed; stopping")
            return
    print("ALL STEPS DONE")


if __name__ == "__main__":
    main()
