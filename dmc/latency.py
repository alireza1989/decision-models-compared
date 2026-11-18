"""Latency runs: 200 sequential calls per endpoint, one at a time, interleaved across endpoints.

Each message goes to every endpoint in turn before the next message, so a slow minute hits every
model rather than one. Routes: every lineup model through OpenRouter, plus Jev direct through
TypeSafe's /v1/systemone (the only vendor key this test has), so the OpenRouter hop can be measured.

    python -m dmc.latency            # resumes where it stopped
"""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from dmc.common import INSTRUCTIONS, RESULTS, descriptions, load, read_jsonl
from dmc.openrouter import DecisionError, DecisionsClient, load_env

OUT = RESULTS / "raw" / "latency" / "latency.jsonl"
TYPESAFE = "https://api.typesafe.ai/v1/systemone"


class TypeSafeDirect:
    def __init__(self):
        self.key = load_env()["TYPESAFE_API_KEY"]

    def decide(self, model, state, questions, attempts=4):
        body = json.dumps({"model": model, "state": state, "questions": questions}).encode()
        last = None
        for attempt in range(attempts):
            req = urllib.request.Request(TYPESAFE, data=body, headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
            start = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.load(resp), (time.perf_counter() - start) * 1000, None, attempt + 1
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
                if e.code not in (408, 429, 500, 502, 503, 504):
                    return None, 0.0, last, attempt + 1
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = str(e)
            time.sleep(min(2 ** attempt, 20))
        return None, 0.0, last, attempts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--budget-seconds", type=float, default=160, help="stop after this long, so a caller can resume")
    args = ap.parse_args()
    lineup = json.load(open("config/lineup.json"))
    endpoints = [("openrouter", m["id"]) for m in lineup["models"]] + [("typesafe_direct", "jev-latest")]
    rows = random.Random(200).sample(load("val"), args.n)
    q = {"skill": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": descriptions("base")}}
    clients = {"openrouter": DecisionsClient(), "typesafe_direct": TypeSafeDirect()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["route"], r["model"], r["id"]) for r in read_jsonl(OUT)}
    t0 = time.time()
    for row in rows:
        for route, model in endpoints:
            if (route, model, row["id"]) in done:
                continue
            if time.time() - t0 > args.budget_seconds:
                print(f"paused after {time.time() - t0:.0f}s; {len(done)} calls so far")
                return
            resp, latency, err, tries = clients[route].decide(model, row["state"], q)
            rec = {"route": route, "model": model, "id": row["id"], "latency_ms": round(latency, 1), "attempts": tries,
                   "error": err, "version": resp.get("model") if resp else None,
                   "provider": resp.get("provider") if resp else None,
                   "cost": ((resp or {}).get("usage") or {}).get("cost"),
                   "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            with open(OUT, "a") as f:
                f.write(json.dumps(rec) + "\n")
            with open(RESULTS / "cost_ledger.jsonl", "a") as f:
                f.write(json.dumps({"run": "latency", "model": f"{route}:{model}", "id": row["id"], "tag": "latency", "cost": rec["cost"] or 0.0}) + "\n")
            done.add((route, model, row["id"]))
    print(f"done: {len(done)} calls")


if __name__ == "__main__":
    main()
