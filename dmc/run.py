"""Run gates on a split, round-robin across models, with resume and a cost cap.

    python -m dmc.run --split test --condition scoped_v2 --run r1
    python -m dmc.run --split test --variant reversed --run r1          # option-order stress test
    python -m dmc.run --split reworded --variant reworded --run r1      # option-name stress test
    python -m dmc.run --split planted --run r1                          # planted-policy stress test
    python -m dmc.run --split w2c_test --run r1                         # tool-call gate
    python -m dmc.run --provider anthropic --only claude-haiku-5-5 --split fresh --condition base --run r1

Every response is stored whole in results/raw/<run>/<model>.<tag>.jsonl, one JSON line per item,
so every number can be recomputed from saved results. A request that still fails after retries is
recorded as an escalation, as in post 1, and kept with its error.
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from dmc.common import (CONDITIONS, INSTRUCTIONS, LABELS, OOS, RESULTS, UNWORDED, W2C_DESCRIPTIONS,
                        W2C_INSTRUCTIONS, W2C_LABELS, descriptions, is_network_error, load, read_jsonl)

LEDGER = RESULTS / "cost_ledger.jsonl"
_lock = threading.Lock()


def spent() -> float:
    return sum(r.get("cost") or 0.0 for r in read_jsonl(LEDGER))


def task_of(split: str) -> str:
    return "w2c" if split.startswith("w2c") else "routing"


def build_question(task: str, condition: str, variant: str) -> tuple[str, dict, dict]:
    """Returns (question name, questions payload, map from shown name back to label)."""
    if task == "w2c":
        crit = dict(W2C_DESCRIPTIONS)
        if variant == "reversed":
            crit = dict(list(crit.items())[::-1])
        return "next_step", {"next_step": {"type": "choice", "instructions": W2C_INSTRUCTIONS, "criteria": crit}}, {k: k for k in crit}
    crit = descriptions(condition, reverse=variant == "reversed", reworded=variant == "reworded")
    back = {k: (UNWORDED[k] if variant == "reworded" else k) for k in crit}
    return "skill", {"skill": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": crit}}, back


def tag_of(task: str, condition: str, variant: str, split: str) -> str:
    v = "" if variant == "none" else f".{variant}"
    return f"w2c{v}.{split[4:]}" if task == "w2c" else f"{condition}{v}.{split}"


def one(client, model: str, row: dict, qname: str, q: dict, back: dict, labels: list[str], fallback: str) -> dict:
    resp, latency, err, tries = client.decide(model, row["state"], q)
    out = {"id": row["id"], "label": row["label"], "kind": row["kind"], "model": model,
           "latency_ms": round(latency, 1), "attempts": tries,
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if resp is None:
        return {**out, "pred": fallback, "probs": None, "error": err, "cost": 0.0}
    ans = (resp.get("answers") or {}).get(qname) or {}
    shown = ans.get("choice")
    pred = back.get(shown)
    probs = ans.get("probabilities")
    if probs is not None and pred is not None:
        probs = {back[k]: float(v) for k, v in probs.items() if k in back}
        probs = {label: probs.get(label, 0.0) for label in labels}
    usage = resp.get("usage") or {}
    bad = pred is None
    return {**out, "pred": fallback if bad else pred, "probs": None if bad else probs,
            "confidence": ans.get("confidence"), "error": f"unreadable answer: {shown!r}" if bad else None,
            "version": resp.get("model"), "provider": resp.get("provider"), "gen_id": resp.get("id"),
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "cost": usage.get("cost") or 0.0, "raw_answer": ans}


def make_client(provider: str):
    if provider == "anthropic":
        from dmc.anthropic_client import AnthropicClient
        return AnthropicClient()
    from dmc.openrouter import DecisionsClient
    return DecisionsClient()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="config/lineup.json")
    ap.add_argument("--provider", default="openrouter", choices=["openrouter", "anthropic"])
    ap.add_argument("--only", nargs="*", help="model ids to run (default: every model in the lineup)")
    ap.add_argument("--condition", default="base", choices=CONDITIONS)
    ap.add_argument("--variant", default="none", choices=["none", "reversed", "reworded"])
    ap.add_argument("--split", required=True, help="val, val_near, test, fresh, planted, reworded, w2c_val, w2c_test")
    ap.add_argument("--run", required=True, help="name of this run: r1, r2, r3 (repeats), pilot, ...")
    ap.add_argument("--sample", type=int, default=0, help="stratified sample of N items (equal per kind), for checks")
    ap.add_argument("--batch", type=int, default=40, help="items per model before moving to the next model")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--cap", type=float, default=15.0, help="stop when total OpenRouter spend in the ledger reaches this, in USD")
    ap.add_argument("--budget-seconds", type=float, default=0, help="stop starting new batches after this long (0: no limit); rerun to resume")
    args = ap.parse_args()

    if args.provider == "anthropic":
        models = args.only or ["claude-haiku-5-5"]
    else:
        lineup = json.load(open(args.models))
        models = [m["id"] for m in lineup["models"] if m["status"] in ("core", "optional")]
        if args.only:
            models = [m for m in models if m in args.only]
    task = task_of(args.split)
    labels, fallback = (W2C_LABELS, "cannot_answer") if task == "w2c" else (LABELS, OOS)
    rows = load(args.split)
    if args.sample:
        rng, kinds = random.Random(18), sorted({r["kind"] for r in rows})
        per = args.sample // len(kinds)
        rows = [r for k in kinds for r in rng.sample([x for x in rows if x["kind"] == k], per)]
    qname, q, back = build_question(task, args.condition, args.variant)
    tag = tag_of(task, args.condition, args.variant, args.split)
    outdir = RESULTS / "raw" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {m: outdir / f"{m.replace('/', '__')}.{tag}.jsonl" for m in models}
    for p in paths.values():  # a run killed mid-line leaves no newline; start the next record on a fresh line
        if p.exists() and p.stat().st_size and not p.read_bytes().endswith(b"\n"):
            with open(p, "a") as f:
                f.write("\n")
    # rows that failed on our own network (no HTTP answer) are retried; everything else counts as done
    done = {m: {r["id"] for r in read_jsonl(p) if not is_network_error(r)} for m, p in paths.items()}
    todo = sum(1 for m in models for r in rows if r["id"] not in done[m])
    client = make_client(args.provider)
    print(f"run={args.run} {tag}: {len(rows)} items x {len(models)} models, {todo} to do; spent so far ${spent():.4f}")
    if not todo:
        print("done")
        return

    def work(model, row):
        rec = one(client, model, row, qname, q, back, labels, fallback)
        if (rec.get("error") or "").startswith(("HTTP 401", "HTTP 403")):
            # A rejected key is a setup problem, not a model failure: stop, and record nothing.
            raise SystemExit(f"{model}: {rec['error'][:200]}\nStopped without recording anything. Fix the key in .env and rerun.")
        with _lock:
            with open(paths[model], "a") as f:
                f.write(json.dumps(rec) + "\n")
            with open(LEDGER, "a") as f:
                f.write(json.dumps({"run": args.run, "model": model, "id": row["id"], "tag": tag, "cost": rec["cost"]}) + "\n")
        return rec

    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        for start in range(0, len(rows), args.batch):
            chunk = [r for r in rows[start:start + args.batch]]
            if all(r["id"] in done[m] for m in models for r in chunk):
                continue
            if spent() >= args.cap:
                print(f"cost cap ${args.cap} reached; stopping")
                break
            if args.budget_seconds and time.time() - t0 > args.budget_seconds:
                print(f"time budget reached after {time.time() - t0:.0f}s; rerun to resume")
                raise SystemExit(3)
            futures = []
            for m in models:  # round-robin: every model gets this chunk before the next chunk starts
                futures += [pool.submit(work, m, r) for r in chunk if r["id"] not in done[m]]
            try:
                errs = sum(1 for f in futures if f.result().get("error"))
            except SystemExit:
                for f in futures:
                    f.cancel()
                raise
            print(f"  {min(start + args.batch, len(rows))}/{len(rows)}  errors={errs}  spent=${spent():.4f}  {time.time() - t0:.0f}s", flush=True)
    print("done")


if __name__ == "__main__":
    main()
