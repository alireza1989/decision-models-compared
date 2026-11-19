"""Checks that every planned run is complete: one row per item, per model, per set. Prints what's missing."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dmc.common import RESULTS, is_network_error, load, read_jsonl  # noqa: E402

lineup = [m["id"] for m in json.load(open("config/lineup.json"))["models"]]
HAIKU, SONNET = "claude-haiku-5-5", "claude-sonnet-5-5"
R1 = [("base.val", "val"), ("base.test", "test"), ("scoped_v1.val_near", "val_near"), ("scoped_v1.test", "test"),
      ("scoped_v2.val_near", "val_near"), ("scoped_v2.test", "test"), ("base.fresh", "fresh"), ("scoped_v1.fresh", "fresh"),
      ("scoped_v2.fresh", "fresh"), ("w2c.val", "w2c_val"), ("w2c.test", "w2c_test"), ("base.reversed.test", "test"),
      ("base.reworded.reworded", "reworded"), ("base.planted", "planted")]
REP = [("base.test", "test"), ("base.fresh", "fresh"), ("scoped_v1.fresh", "fresh"), ("scoped_v2.fresh", "fresh")]
plan = [(m, "r1", t, s) for m in lineup + [HAIKU] for t, s in R1]
plan += [(m, r, t, s) for m in lineup + [HAIKU] for r in ("r2", "r3") for t, s in REP]
plan += [(SONNET, "r1", t, s) for t, s in R1 if s == "fresh"]

ids = {s: {r["id"] for r in load(s)} for s in {s for *_, s in plan}}
problems, total, errors = 0, 0, 0
for m, run, tag, split in plan:
    rows = read_jsonl(RESULTS / "raw" / run / f"{m.replace('/', '__')}.{tag}.jsonl")
    good = {r["id"] for r in rows if not is_network_error(r)}
    missing = ids[split] - good
    extra = {r["id"] for r in rows} - ids[split]
    kept = [r["id"] for r in rows if not is_network_error(r)]
    dups = len(kept) - len(set(kept))  # a failed connection or rate limit replaced by its retry is not a duplicate
    errs = sum(1 for r in rows if r.get("error") and not is_network_error(r))
    total += len(good)
    errors += errs
    if missing or extra or dups:
        problems += 1
        print(f"{m:42s} {run} {tag:26s} missing={len(missing)} extra={len(extra)} duplicate_rows={dups}")
lat = read_jsonl(RESULTS / "raw" / "latency" / "latency.jsonl")
lat_keys = {(r["route"], r["model"], r["id"]) for r in lat}
print(f"latency: {len(lat_keys)} of {13 * 200} calls")
print(f"{len(plan)} model x set files planned, {problems} incomplete; {total} scored rows; {errors} provider errors kept as escalations")
