"""Builds the When2Call sample for the tool-call gate. Run once; frozen by the pre-registration commit.

When2Call (NVIDIA, NAACL 2025, Apache-2.0) has 3,652 multiple-choice test items. Each has a user
message, the tools the assistant has, and one correct next step: tool_call, request_for_info or
cannot_answer. A fourth option, direct (answer without a tool), is never correct in this file; it
is the hallucination trap. This script downloads the file if needed, checks its hash, and draws
300 items per correct answer for test and 100 per correct answer for validation, with no overlap.
"""
import hashlib
import json
import random
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
URL = "https://raw.githubusercontent.com/NVIDIA/When2Call/main/data/test/when2call_test_mcq.jsonl"
SHA256 = "8c3694e583eeeb8dbc297e6cd90da70efc68efa4b6adb7227523e828c6b7b14c"
KEEP = ("uuid", "source", "source_id", "question", "correct_answer", "tools")


def main() -> None:
    path = HERE / "when2call_test_mcq.jsonl"
    if not path.exists():
        urllib.request.urlretrieve(URL, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == SHA256, f"When2Call file changed upstream: {digest}"
    rows = [json.loads(line) for line in open(path)]

    rng = random.Random(1118)
    out = []
    for answer in ("tool_call", "request_for_info", "cannot_answer"):
        pool = sorted((r for r in rows if r["correct_answer"] == answer), key=lambda r: r["uuid"])
        picked = rng.sample(pool, 400)
        out += [{**{k: r[k] for k in KEEP}, "split": "test"} for r in picked[:300]]
        out += [{**{k: r[k] for k in KEEP}, "split": "val"} for r in picked[300:]]
    with open(HERE / "sample.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print(len(out), "items written")


if __name__ == "__main__":
    main()
