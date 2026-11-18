# decision-models-compared

Companion repo for my second post on decision models. It runs 12 decision models and a Claude Haiku
5.5 baseline as agent gates, on the same tests, and scores them on more than accuracy: whether the
probabilities are honest, whether a threshold picked on validation keeps its promise on new traffic,
whether answers survive small changes and a planted policy, and what each decision costs and how
long it takes.

The first post, its lab and its data are in
[harness-decision-gates](https://github.com/alireza1989/harness-decision-gates). This repo reuses
its routing gate unchanged so the numbers compare.

## What's here

| Path | What it is |
|---|---|
| `PREREGISTRATION.md` | Everything fixed before any scored run: models, prompts, data, label rules, metrics, comparisons, hypotheses |
| `config/lineup.json` | The 12 models, frozen on November 18, 2026 |
| `dmc/common.py` | Answer options, the three scope conditions, the stress variants, data loading, metrics |
| `dmc/openrouter.py` | A small client for OpenRouter's Decisions endpoint (standard library only) |
| `dmc/anthropic_client.py` | The Claude baseline behind the same call, with the first post's prompt |
| `dmc/run.py` | Runs any set on any models, round-robin, with resume and a spending cap |
| `dmc/latency.py` | 200 sequential calls per model, interleaved |
| `dmc/evaluate.py` | Every number in the post, from saved results only |
| `data/fresh/` | The fresh set: 296 messages written for this post, the label rules, the final labels |
| `data/stress/` | The reworded-options and planted-policy sets, and the script that builds them |
| `data/when2call/` | The 1,200-item When2Call sample for the tool-call gate, and the script that draws it |
| `results/raw/` | Every response, whole, one JSON line per item |
| `results/cost_ledger.jsonl` | The cost of every call |

## Run it

You need Python 3.9 or newer. The API steps use the standard library only; the analysis needs
`pip install -r requirements.txt`.

Put your keys in a `.env` file in the repo root, one per line, `NAME=value`:

```
OPENROUTER_API_KEY=...
ANTHROPIC_API_KEY=...     # only for the Claude baseline
TYPESAFE_API_KEY=...      # only for Jev's direct latency run
```

The scripts read this file with a strict parser and never run it. Then:

```bash
./run_all.sh              # everything, about $8 of API calls at November 2026 prices
./run_all.sh analysis     # just recompute every number from results/raw/
```

`./run_all.sh` resumes: rerun it after a stop and it skips everything already saved.

## Licences

Code: MIT. CLINC150 (routing gate): CC BY 3.0, rebuilt by `data/prepare.py`. When2Call: Apache-2.0,
see `data/when2call/LICENSE.txt`. The fresh set: written for this post, MIT like the code.
