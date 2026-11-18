"""Every number in the post, computed from saved results only (results/raw/...).

    python -m dmc.evaluate        # writes results/summary.json and results/tables/*.csv

The analysis follows PREREGISTRATION.md: ranking on in-scope plus near-miss messages, tie groups
instead of strict ranks, two comparison families with Holm's correction, thresholds picked on
validation for at most 2% wrong automatic actions and checked once on test and on the fresh set.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter

import numpy as np

from dmc.common import (CONDITIONS, OOS, RESULTS, W2C_LABELS, brier_item, ece, nll, pick_threshold,
                        policy_outcome, read_jsonl, top_prob, validation_split)

RAW = RESULTS / "raw"
TABLES = RESULTS / "tables"
ALPHA = 0.05
B = 2000
JEV = "typesafe/jev-1.14"
HAIKU = "claude-haiku-5-5"


def model_ids() -> list[str]:
    lineup = json.load(open("config/lineup.json"))
    return [m["id"] for m in lineup["models"]] + [HAIKU]


def names() -> dict:
    lineup = json.load(open("config/lineup.json"))
    return {**{m["id"]: m["name"] for m in lineup["models"]}, HAIKU: "Claude Haiku 5.5"}


def rows_of(run: str, model: str, tag: str) -> list[dict]:
    return read_jsonl(RAW / run / f"{model.replace('/', '__')}.{tag}.jsonl")


# ---- statistics -------------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(pvals: dict) -> dict:
    order = sorted(pvals, key=pvals.get)
    m, out, running = len(order), {}, 0.0
    for i, key in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvals[key]))
        out[key] = running
    return out


def paired(a: list[dict], b: list[dict]) -> list[tuple[dict, dict]]:
    by_id = {r["id"]: r for r in b}
    return [(r, by_id[r["id"]]) for r in a if r["id"] in by_id]


def acc_compare(a: list[dict], b: list[dict]) -> dict:
    pairs = paired(a, b)
    only_a = sum(1 for x, y in pairs if x["pred"] == x["label"] and y["pred"] != y["label"])
    only_b = sum(1 for x, y in pairs if x["pred"] != x["label"] and y["pred"] == y["label"])
    n = len(pairs)
    return {"n": n, "diff": (only_a - only_b) / n if n else float("nan"), "only_a": only_a, "only_b": only_b,
            "discordant_share": (only_a + only_b) / n if n else float("nan"), "p": mcnemar_exact(only_a, only_b)}


def brier_compare(a: list[dict], b: list[dict], seed: int = 0) -> dict:
    """Paired difference in Brier score on the chosen answer (a minus b): bootstrap CI and sign-flip p-value."""
    d = np.array([brier_item(x) - brier_item(y) for x, y in paired(a, b)
                  if brier_item(x) is not None and brier_item(y) is not None])
    if len(d) == 0:
        return {"n": 0}
    rng = np.random.default_rng(seed)
    boots = rng.choice(d, size=(B, len(d)), replace=True).mean(axis=1)
    signs = rng.choice([-1.0, 1.0], size=(10000, len(d)))
    null = np.abs((signs * d).mean(axis=1))
    p = (np.sum(null >= abs(d.mean())) + 1) / (len(null) + 1)
    return {"n": int(len(d)), "diff": float(d.mean()), "ci": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))], "p": float(p)}


def boot_ci(rows: list[dict], fn, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    n = len(rows)
    vals = [fn([rows[i] for i in rng.integers(0, n, n)]) for _ in range(500)]
    vals = [v for v in vals if v is not None]
    return [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))] if vals else [None, None]


# ---- per-set metrics --------------------------------------------------------------------------

SUBSETS = {"all": None, "in": ("in",), "near": ("near",), "far": ("far",), "in_near": ("in", "near")}


def subset(rows: list[dict], name: str) -> list[dict]:
    kinds = SUBSETS[name]
    return rows if kinds is None else [r for r in rows if r["kind"] in kinds]


def metrics(rows: list[dict], with_ece_ci: bool = False) -> dict:
    if not rows:
        return {"n": 0}
    k = sum(r["pred"] == r["label"] for r in rows)
    briers = [b for b in map(brier_item, rows) if b is not None]
    out = {"n": len(rows), "accuracy": k / len(rows), "accuracy_ci": wilson(k, len(rows)),
           "errors": sum(1 for r in rows if r.get("error")),
           "brier": sum(briers) / len(briers) if briers else None,
           "ece": ece(rows) if briers else None, "nll": nll(rows),
           "confident_mistakes": sum(1 for r in rows if r["pred"] != r["label"] and (top_prob(r) or 0) >= 0.9),
           "mean_cost": statistics.mean(r.get("cost") or 0.0 for r in rows),
           "mean_input_tokens": statistics.mean(r.get("input_tokens") or 0 for r in rows)}
    if out["brier"] is not None:
        out["decision_score"] = 50 * (1 + out["accuracy"] - out["brier"])
    if with_ece_ci and briers:
        out["ece_ci"] = boot_ci(rows, lambda rs: ece(rs) if any(top_prob(r) is not None for r in rs) else None)
    return out


def tie_groups(rows_by_model: dict, sub: str) -> list[list[str]]:
    """Leader first; models not distinguishable from the leader (McNemar, Holm, alpha 0.05) join its group.
    Remove that group and repeat on the rest."""
    remaining = {m: subset(r, sub) for m, r in rows_by_model.items() if r}
    groups = []
    while remaining:
        acc = {m: sum(x["pred"] == x["label"] for x in r) / len(r) for m, r in remaining.items()}
        leader = max(acc, key=acc.get)
        p = {m: acc_compare(remaining[leader], r)["p"] for m, r in remaining.items() if m != leader}
        adj = holm(p) if p else {}
        group = [leader] + sorted((m for m in adj if adj[m] >= ALPHA), key=lambda m: -acc[m])
        groups.append(group)
        for m in group:
            remaining.pop(m)
    return groups


def flips(a: list[dict], b: list[dict]) -> dict:
    pairs = paired(a, b)
    n = len(pairs)
    f = sum(1 for x, y in pairs if x["pred"] != y["pred"])
    return {"n": n, "flip_rate": f / n if n else None, "flip_ci": wilson(f, n),
            "acc_a": sum(x["pred"] == x["label"] for x, _ in pairs) / n if n else None,
            "acc_b": sum(y["pred"] == y["label"] for _, y in pairs) / n if n else None}


# ---- sections ---------------------------------------------------------------------------------

def routing_section(models: list[str]) -> dict:
    out = {"test": {}, "fresh": {}, "thresholds": {}, "tie_groups": {}, "vs_jev": {}, "contamination": {}}
    for cond in CONDITIONS:
        test = {m: rows_of("r1", m, f"{cond}.test") for m in models}
        fresh = {m: rows_of("r1", m, f"{cond}.fresh") for m in models}
        val = {m: rows_of("r1", m, f"{cond}.{validation_split(cond)}") for m in models}
        out["test"][cond] = {m: {s: metrics(subset(r, s), with_ece_ci=s == "in_near") for s in SUBSETS} for m, r in test.items() if r}
        out["fresh"][cond] = {m: {s: metrics(subset(r, s), with_ece_ci=s == "in_near") for s in ("all", "in", "near")}
                              for m, r in fresh.items() if r}
        out["tie_groups"][cond] = {"test_in_near": tie_groups(test, "in_near"), "fresh": tie_groups(fresh, "all")}
        th = {}
        for m in models:
            if not val[m]:
                continue
            t = pick_threshold(val[m])
            entry = {"threshold": t, "validation": policy_outcome(val[m], t)}
            for name, rows in (("test_all_traffic", test[m]), ("fresh", fresh[m])):
                if rows:
                    o = policy_outcome(rows, t)
                    o["wrong_auto_ci"] = wilson(o["n_wrong"], o["n_auto"])
                    entry[name] = o
            th[m] = entry
        out["thresholds"][cond] = th
        vj = {}
        for split, data in (("test_in_near", {m: subset(r, "in_near") for m, r in test.items()}), ("fresh", fresh)):
            if not data.get(JEV):
                continue
            cmp = {m: acc_compare(data[m], data[JEV]) for m in models if m != JEV and data.get(m)}
            adj = holm({m: c["p"] for m, c in cmp.items()})
            vj[split] = {m: {**c, "p_holm": adj[m], "brier": brier_compare(data[m], data[JEV])} for m, c in cmp.items()}
        out["vs_jev"][cond] = vj
        cont = {}
        for m in models:
            t_in = subset(test[m], "in_near")
            if fresh[m] and t_in:
                bf = [brier_item(r) for r in fresh[m] if brier_item(r) is not None]
                bt = [brier_item(r) for r in t_in if brier_item(r) is not None]
                if bf and bt:
                    rng = np.random.default_rng(1)
                    d = [rng.choice(bf, len(bf)).mean() - rng.choice(bt, len(bt)).mean() for _ in range(B)]
                    cont[m] = {"brier_fresh": float(np.mean(bf)), "brier_test_in_near": float(np.mean(bt)),
                               "diff": float(np.mean(bf) - np.mean(bt)), "ci": [float(np.quantile(d, .025)), float(np.quantile(d, .975))],
                               "acc_fresh": metrics(fresh[m])["accuracy"], "acc_test_in_near": metrics(t_in)["accuracy"]}
        out["contamination"][cond] = cont
    # Jev 1.14 against Jev 1.13 (post 1's version) on the same test messages
    return out


def stress_section(models: list[str]) -> dict:
    out = {"reversed": {}, "reworded": {}, "planted": {}}
    for m in models:
        base = rows_of("r1", m, "base.test")
        if not base:
            continue
        rev = rows_of("r1", m, "base.reversed.test")
        if rev:
            out["reversed"][m] = {"all": flips(base, rev), "in_near": flips(subset(base, "in_near"), subset(rev, "in_near"))}
        rew = rows_of("r1", m, "base.reworded.reworded")
        if rew:
            out["reworded"][m] = {"all": flips(base, rew), "in_near": flips(subset(base, "in_near"), subset(rew, "in_near"))}
        pl = rows_of("r1", m, "base.planted")
        if pl:
            clean = {r["id"]: r for r in base}
            res = {}
            for kind in ("in", "near"):
                items = [r for r in pl if r["kind"] == kind]
                targets = {r["id"]: r for r in read_jsonl(RESULTS.parent / "data" / "stress" / "planted.jsonl")}
                hit = sum(1 for r in items if r["pred"] == targets[r["id"]]["target"])
                clean_rows = [clean[targets[r["id"]]["orig_id"]] for r in items]
                clean_hit = sum(1 for r, c in zip(items, clean_rows) if c["pred"] == targets[r["id"]]["target"])
                res[kind] = {"n": len(items), "target_rate": hit / len(items), "target_ci": wilson(hit, len(items)),
                             "target_rate_clean": clean_hit / len(items),
                             "accuracy_planted": sum(r["pred"] == r["label"] for r in items) / len(items),
                             "accuracy_clean": sum(c["pred"] == c["label"] for c in clean_rows) / len(items)}
                if kind == "near":
                    res[kind]["automated_rate"] = sum(r["pred"] != OOS for r in items) / len(items)
                    res[kind]["automated_rate_clean"] = sum(c["pred"] != OOS for c in clean_rows) / len(items)
            out["planted"][m] = res
    return out


def repeats_section(models: list[str]) -> dict:
    out = {}
    for m in models:
        entry = {}
        for tag in ["base.test"] + [f"{c}.fresh" for c in CONDITIONS]:
            runs = [rows_of(r, m, tag) for r in ("r1", "r2", "r3")]
            runs = [r for r in runs if r]
            if len(runs) < 2:
                continue
            ids = set.intersection(*({x["id"] for x in r} for r in runs))
            preds = [{x["id"]: x["pred"] for x in r} for r in runs]
            same = sum(1 for i in ids if len({p[i] for p in preds}) == 1)
            accs = [sum(x["pred"] == x["label"] for x in r if x["id"] in ids) / len(ids) for r in runs]
            entry[tag] = {"runs": len(runs), "n": len(ids), "all_runs_agree": same / len(ids), "accuracy_by_run": accs,
                          "accuracy_range": max(accs) - min(accs)}
        if entry:
            out[m] = entry
    return out


def w2c_section(models: list[str]) -> dict:
    out = {}
    acts = ("tool_call",)
    for m in models:
        test, val = rows_of("r1", m, "w2c.test"), rows_of("r1", m, "w2c.val")
        if not test:
            continue
        gold = ["tool_call", "request_for_info", "cannot_answer"]
        f1s = {}
        for c in gold:
            tp = sum(1 for r in test if r["pred"] == c and r["label"] == c)
            fp = sum(1 for r in test if r["pred"] == c and r["label"] != c)
            fn = sum(1 for r in test if r["pred"] != c and r["label"] == c)
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            f1s[c] = {"precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0}
        not_tool = [r for r in test if r["label"] != "tool_call"]
        tool = [r for r in test if r["label"] == "tool_call"]
        entry = {**metrics(test, with_ece_ci=True), "macro_f1": statistics.mean(v["f1"] for v in f1s.values()), "per_class": f1s,
                 "unwarranted_tool_call": sum(r["pred"] == "tool_call" for r in not_tool) / len(not_tool),
                 "missed_tool_call": sum(r["pred"] != "tool_call" for r in tool) / len(tool),
                 "direct_rate": sum(r["pred"] == "direct" for r in test) / len(test),
                 "confusion": {g: dict(Counter(r["pred"] for r in test if r["label"] == g)) for g in gold}}
        if val:
            t = pick_threshold(val, act_labels=acts)
            o = policy_outcome(test, t, act_labels=acts)
            o["wrong_auto_ci"] = wilson(o["n_wrong"], o["n_auto"])
            entry["threshold"] = {"threshold": t, "validation": policy_outcome(val, t, act_labels=acts), "test": o}
        out[m] = entry
    return out


def latency_section() -> dict:
    rows = read_jsonl(RAW / "latency" / "latency.jsonl")
    out = {}
    for key in sorted({(r["route"], r["model"]) for r in rows}):
        lat = sorted(r["latency_ms"] for r in rows if (r["route"], r["model"]) == key and not r.get("error"))
        if lat:
            out[f"{key[0]}:{key[1]}"] = {"n": len(lat), "p50": statistics.median(lat), "p95": lat[int(0.95 * (len(lat) - 1))],
                                          "errors": sum(1 for r in rows if (r["route"], r["model"]) == key and r.get("error"))}
    return out


def cost_section(models: list[str], routing: dict) -> dict:
    out = {}
    for m in models:
        test = rows_of("r1", m, "base.test")
        th = routing["thresholds"].get("base", {}).get(m)
        if not test or not th:
            continue
        correct_auto = th["test_all_traffic"]["n_auto"] - th["test_all_traffic"]["n_wrong"]
        total = sum(r.get("cost") or 0.0 for r in test)
        out[m] = {"cost_per_1000_decisions": 1000 * total / len(test),
                  "cost_per_1000_correct_auto": 1000 * total / correct_auto if correct_auto else None,
                  "mean_input_tokens": statistics.mean(r.get("input_tokens") or 0 for r in test)}
    return out


# ---- tables -----------------------------------------------------------------------------------

def fmt(x, digits: int = 4) -> str:
    return "" if x is None else f"{x:.{digits}f}"


def write_tables(summary: dict, nm: dict) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    for cond, per in summary["routing"]["test"].items():
        with open(TABLES / f"routing_test_{cond}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["model", "acc_in_near", "ci_lo", "ci_hi", "acc_in", "acc_near", "acc_far", "brier_in_near", "ece_in_near",
                        "nll_in_near", "decision_score_in_near", "errors"])
            for m, s in sorted(per.items(), key=lambda kv: -(kv[1]["in_near"].get("accuracy") or 0)):
                a = s["in_near"]
                w.writerow([nm.get(m, m), fmt(a.get("accuracy")), fmt((a.get("accuracy_ci") or [None])[0]), fmt((a.get("accuracy_ci") or [None, None])[1]),
                            fmt(s["in"].get("accuracy")), fmt(s["near"].get("accuracy")), fmt(s["far"].get("accuracy")),
                            fmt(a.get("brier")), fmt(a.get("ece")), fmt(a.get("nll")), fmt(a.get("decision_score"), 2), s["all"]["errors"]])
    for cond, per in summary["routing"]["fresh"].items():
        with open(TABLES / f"fresh_{cond}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["model", "acc", "ci_lo", "ci_hi", "acc_in", "acc_near", "brier", "ece", "nll", "decision_score"])
            for m, s in sorted(per.items(), key=lambda kv: -kv[1]["all"]["accuracy"]):
                a = s["all"]
                w.writerow([nm.get(m, m), fmt(a.get("accuracy")), fmt(a["accuracy_ci"][0]), fmt(a["accuracy_ci"][1]),
                            fmt(s["in"].get("accuracy")), fmt(s["near"].get("accuracy")), fmt(a.get("brier")), fmt(a.get("ece")),
                            fmt(a.get("nll")), fmt(a.get("decision_score"), 2)])
    for cond, per in summary["routing"]["thresholds"].items():
        with open(TABLES / f"thresholds_{cond}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["model", "threshold", "val_wrong_auto", "test_wrong_auto", "test_ci_lo", "test_ci_hi", "test_handled",
                        "fresh_wrong_auto", "fresh_handled"])
            for m, e in per.items():
                t, fr = e.get("test_all_traffic", {}), e.get("fresh", {})
                w.writerow([nm.get(m, m), fmt(e["threshold"], 2), fmt(e["validation"]["wrong_auto"]), fmt(t.get("wrong_auto")),
                            fmt((t.get("wrong_auto_ci") or [None])[0]), fmt((t.get("wrong_auto_ci") or [None, None])[1]), fmt(t.get("handled")),
                            fmt(fr.get("wrong_auto")), fmt(fr.get("handled"))])


def main() -> None:
    models = model_ids()
    nm = names()
    routing = routing_section(models)
    summary = {"routing": routing, "stress": stress_section(models), "repeats": repeats_section(models),
               "w2c": w2c_section(models), "latency": latency_section(), "cost": cost_section(models, routing),
               "spent_usd": sum(r.get("cost") or 0.0 for r in read_jsonl(RESULTS / "cost_ledger.jsonl"))}
    jev13, jev14 = rows_of("r1", "typesafe/jev-1.13", "base.test"), rows_of("r1", JEV, "base.test")
    if jev13 and jev14:
        summary["jev_versions"] = {"in_near": acc_compare(subset(jev14, "in_near"), subset(jev13, "in_near")),
                                   "brier_in_near": brier_compare(subset(jev14, "in_near"), subset(jev13, "in_near"))}
    with open(RESULTS / "summary.json", "w") as f:
        json.dump(summary, f, indent=1, default=float)
    write_tables(summary, nm)
    print(f"wrote results/summary.json and results/tables/; spent ${summary['spent_usd']:.4f}")


if __name__ == "__main__":
    main()
