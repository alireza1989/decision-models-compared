"""Build the routing-gate dataset from CLINC150 (CC BY 3.0, Larson et al. 2019).

The agent in this lab is a banking support agent with 15 skills, one per
CLINC150 banking intent. Every incoming message must either go to one of those
skills or be marked out_of_scope and escalated to a person.

Splits written to data/*.jsonl, one JSON object per line:
  train  banking train + out-of-scope examples (CLINC oos_train + 8 unrelated domains)
  val    banking val   + out-of-scope examples (CLINC oos_val + 8 unrelated domains)
  test   banking test (kind="in")
         + credit_cards test (kind="near": a related domain the agent was not built for)
         + a sample of CLINC oos_test (kind="far": unrelated requests)

credit_cards never appears in train or val, so "near" measures how a gate
handles look-alike requests it has never seen.
"""

import json
import random
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/clinc/oos-eval/master/data/"
HERE = Path(__file__).parent
OOS = "out_of_scope"
SEED = 7


def fetch(name: str) -> dict:
    path = HERE / name
    if not path.exists():
        urllib.request.urlretrieve(BASE + name, path)
    return json.loads(path.read_text())


def main() -> None:
    rng = random.Random(SEED)
    full = fetch("data_full.json")
    domains = fetch("domains.json")

    skills = set(domains["banking"])
    near = set(domains["credit_cards"])
    unrelated = {i for d, intents in domains.items()
                 if d not in ("banking", "credit_cards") for i in intents}

    def pick(split: str, intents: set, per_intent: int) -> list:
        by_intent: dict = {}
        for text, intent in full[split]:
            if intent in intents:
                by_intent.setdefault(intent, []).append(text)
        out = []
        for intent in sorted(by_intent):
            texts = by_intent[intent]
            out += rng.sample(texts, min(per_intent, len(texts)))
        return out

    def rows(texts, label, kind):
        return [{"text": t, "label": label, "kind": kind} for t in texts]

    train = [{"text": t, "label": i, "kind": "in"} for t, i in full["train"] if i in skills]
    train += rows([t for t, _ in full["oos_train"]], OOS, "far")
    train += rows(pick("train", unrelated, 5), OOS, "far")

    val = [{"text": t, "label": i, "kind": "in"} for t, i in full["val"] if i in skills]
    val += rows([t for t, _ in full["oos_val"]], OOS, "far")
    val += rows(pick("val", unrelated, 2), OOS, "far")

    test = [{"text": t, "label": i, "kind": "in"} for t, i in full["test"] if i in skills]
    test += rows([t for t, i in full["test"] if i in near], OOS, "near")
    test += rows(rng.sample([t for t, _ in full["oos_test"]], 450), OOS, "far")

    # The fix: collect a few labelled look-alike requests and add them as out_of_scope.
    # They come from credit_cards train/val, which never overlap with the test split.
    train_near = train + rows(pick("train", near, 10), OOS, "near")
    val_near = val + rows(pick("val", near, 4), OOS, "near")

    for name, data in [("train", train), ("val", val), ("test", test),
                       ("train_near", train_near), ("val_near", val_near)]:
        for n, row in enumerate(data):
            row["id"] = f"{name}-{n:04d}"
        with open(HERE / f"{name}.jsonl", "w") as f:
            for row in data:
                f.write(json.dumps(row) + "\n")
        kinds = {k: sum(r["kind"] == k for r in data) for k in ("in", "near", "far")}
        print(f"{name:5s} {len(data):5d} rows  {kinds}")

    (HERE / "skills.json").write_text(json.dumps(sorted(skills), indent=2) + "\n")


if __name__ == "__main__":
    main()
