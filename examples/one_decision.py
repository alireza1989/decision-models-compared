"""Sends one message to two decision models and prints the answer and the top three probabilities."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dmc.common import INSTRUCTIONS, descriptions
from dmc.openrouter import DecisionsClient

client = DecisionsClient()  # reads OPENROUTER_API_KEY from .env
question = {"skill": {"type": "choice",
                      "instructions": INSTRUCTIONS,
                      "criteria": descriptions("scoped_v2")}}
for model in ["liquid/d1.2-ultra", "google/gemini-decision-1"]:
    resp, latency_ms, err, tries = client.decide(
        model, "move money to my brother's checking account", question)
    answer = resp["answers"]["skill"]
    top3 = sorted(answer["probabilities"].items(), key=lambda kv: -kv[1])[:3]
    print(model, answer["choice"], [(k, round(v, 2)) for k, v in top3])
