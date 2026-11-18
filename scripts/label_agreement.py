"""Compares the blind labels with the proposed ones and lists every disagreement for reconciliation.

    python3 scripts/label_agreement.py      # reads data/fresh/labels_blind.jsonl and data/fresh/fresh_set.jsonl

Writes data/fresh/agreement.json (raw agreement, Cohen's kappa) and data/fresh/disagreements.md.
Model outputs play no part here: none exist for the fresh set until labels_final.jsonl is committed.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "data" / "fresh"


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    return (po - pe) / (1 - pe)


def main() -> None:
    fresh = {r["id"]: r for r in map(json.loads, open(HERE / "fresh_set.jsonl"))}
    blind = {r["id"]: r["label"] for r in map(json.loads, open(HERE / "labels_blind.jsonl"))}
    missing = sorted(set(fresh) - set(blind))
    ids = sorted(set(fresh) & set(blind))
    a = [fresh[i]["proposed_label"] for i in ids]
    b = [blind[i] for i in ids]
    out = {"n": len(ids), "missing": missing, "agreement": sum(x == y for x, y in zip(a, b)) / len(ids),
           "kappa": kappa(a, b), "blind_drops": sum(x == "drop" for x in b),
           "kappa_without_drops": kappa(*zip(*[(x, y) for x, y in zip(a, b) if y != "drop"]))}
    (HERE / "agreement.json").write_text(json.dumps(out, indent=1))
    lines = ["# Fresh set: disagreements to settle", "",
             "Settle each against LABEL_RULES.md. Write the final label in labels_final.jsonl; use drop if it can honestly be read two ways.", "",
             "| ID | Message | Account | Proposed | Blind |", "|---|---|---|---|---|"]
    for i in ids:
        if fresh[i]["proposed_label"] != blind[i]:
            s = fresh[i]["state"]
            msg, acct = (s["customer_message"], s["account"]["name"]) if isinstance(s, dict) else (s, "")
            lines.append(f"| {i} | {msg} | {acct} | {fresh[i]['proposed_label']} | {blind[i]} |")
    (HERE / "disagreements.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
