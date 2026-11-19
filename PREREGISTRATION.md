# Pre-registration: Decision Models, Compared

Written on November 18, 2026, before any scored run. The signed, tagged commit that adds this file
(`prereg-v1`) freezes everything below: the lineup, the prompts and option texts, the scope
sentences, the data sets, the label rules, the threshold rule, the metrics, the comparisons and the
hypotheses. Any change after that commit is listed under **Deviations** at the bottom, with the
date and the reason.

## 1. Question

Which decision models give an agent's gate the right answer and an honest probability on requests
they have never seen, and at what latency and cost?

## 2. Models

`config/lineup.json`, frozen on November 18, 2026: 12 models through OpenRouter's Decisions endpoint
(`https://openrouter.ai/api/alpha/decisions`), the newest version of each family listed there that
day (snapshot: `data/openrouter_decision_models_2026-11-18.json`). Jev 1.13 is the first post's version and
stays as an anchor. Claude Haiku 5.5 (`claude-haiku-5-5`) is the general-model baseline, run as in
the first post: stated confidence, structured output, thinking off (`dmc/anthropic_client.py`).

Local models (Nimble, d1-3B, Kev, GLiNER2.5-Decide, and the Qwen3.5 4B and 9B backbones read
through label log-probabilities) are a secondary arm. They run on my Mac if time allows;
the post reports them only if they finish on the same sets.

## 3. Gates and data

| Set | Split name | Items | What it tests | Source |
|---|---|---|---|---|
| Routing, validation | `val` / `val_near` | 640 / 700 | picking each model's threshold | the first post (CLINC150, CC BY 3.0) |
| Routing, test | `test` | 1,350: 450 in-scope, 450 near-miss, 450 unrelated | accuracy, calibration, threshold transfer | the first post |
| Fresh set | `fresh` | 296 written for this post, minus dropped ones | the same on text no model has seen | `data/fresh/` |
| Tool-call gate | `w2c_val` / `w2c_test` | 300 / 900, balanced over 3 correct answers | a second kind of gate decision | When2Call (NVIDIA, Apache-2.0) |
| Option order | `test`, options reversed | 1,350 | answer flips | built from `test` |
| Option names | `reworded` | 300: 100 per kind | answer flips | `data/stress/build_stress.py` |
| Planted policy | `planted` | 200 in-scope + 200 near-miss | a counterfeit policy line in the customer message | `data/stress/build_stress.py` |

SHA-256 of the frozen data files:

```
98ad27c934d19912ac770a1ceaac03423647ddd281f8bac3961c6e673e23196f  data/test.jsonl
a3deeff2fe80bd2a90d38c834f901b44e49b5473f4addabb2a21eef8a76d2f3d  data/val.jsonl
3134f5f1e18da5304e55cd32a16227b8533f5f76be91f114ec76bf5b47c16165  data/val_near.jsonl
351459a144e02b160fc7fbc0e01fb94542b9834d5b07205d61c485342d6e3607  data/fresh/messages.jsonl
68364c89c30c0f9c84efcc78650ae708319361a8921f2a6819a1fb3f9c47ef4e  data/fresh/fresh_set.jsonl      (withheld, see 4)
f50a36af90c41bce7af6274ad7cde4a8fea839f4d6a93d8e39e83cb61da0d917  data/fresh/build_fresh_set.py   (withheld, see 4)
fb482087e98eb3c5e7458ad103b989a676ea6e987dca2dc7196f94cb6e3146d4  data/stress/planted.jsonl
d6fde20dfd9100cf3de5c43bd1009045265cceb3846a614c70e7ee35534e70ad  data/stress/reworded.jsonl
6df728e3a107434923db8bdcfe393d05bd7b69145ba6a80b2c469d45ac960547  data/when2call/sample.jsonl
```

**Prompts and options.** The routing question, the 15 skill descriptions and the three scope
conditions are in `dmc/common.py`: `base` (the first post), `scoped_v1` (the first post's scope sentence) and
`scoped_v2` (the tighter sentence the first post proposed and never ran). The option-name rewording and the
planted-policy template are in the same file. The tool-call question and its four options are
`W2C_INSTRUCTIONS` and `W2C_DESCRIPTIONS`. Option order is the order in `dmc/common.py`, with
`out_of_scope` last, except in the reversed-order stress test.

**State.** A routing message is sent as a plain string. The 26 fresh messages that come with an
account are sent as `{"customer_message", "account"}`. A When2Call item is sent as
`{"user_message", "available_tools"}` with the tools exactly as When2Call lists them.

## 4. The fresh set and its labels

The fresh set was written for this post on November 18, 2026 to `data/fresh/LABEL_RULES.md`, which is
committed here. It is harder than CLINC150 by design: it has many look-alike pairs (a card charge
next to a card account question, the same short message with different accounts attached), because
the pilot (section 9) showed that near-miss errors cluster on such pairs. **No item was chosen or
dropped because of any model's answer**, and no subset of hard items is picked from model errors.

Labelling is blind and two-sided:

1. The draft set came with a proposed label for every message, in `data/fresh/fresh_set.jsonl` and
   in the script that built it. Both are withheld from this commit so the blind pass below can't see
   them; their SHA-256 hashes above fix them as of now. They are committed unchanged after labelling
   (the reveal step), and the hashes must match.
2. I label all 296 messages from `messages.jsonl` and the rules alone, without the proposed labels
   and without any model output.
3. Agreement is reported as raw agreement and Cohen's kappa. Disagreements are settled against the
   rules by discussion, with no model output in view. A message that can still be read two ways is
   labelled `drop` and removed before scoring. The post reports how many were dropped.
4. `data/fresh/labels_final.jsonl` is committed before any model sees a fresh-set message.

## 5. Runs

Runs alternate between models in round-robin batches of 40 items (`dmc/run.py`), so a slow hour
hits every model. Every response is stored whole, with the model version string, provider, tokens,
cost and timestamp. A request that still fails after 4 attempts counts as an escalation
(`out_of_scope`, or `cannot_answer` on the tool-call gate) and is reported.

| Run | What |
|---|---|
| `r1` | every model × 3 conditions × (validation + test); fresh × 3 conditions; tool-call validation + test; reversed options (base); reworded options (base); planted policy (base) |
| `r2`, `r3` | repeats of base test and of the fresh set in all 3 conditions, at least an hour after `r1` |
| `latency` | 200 sequential calls per model through OpenRouter, interleaved, plus Jev direct through TypeSafe |

All scored calls happen within one week. The spending cap is $15 for all API calls together
(`--cap`, checked against `results/cost_ledger.jsonl`).

## 6. Metrics

All from saved results by `dmc/evaluate.py`, using the top probability so models compare like for
like, as in the first post.

- **Accuracy**, with Wilson 95% intervals.
- **Brier score on the chosen answer**: (top probability − correct)², averaged. Plus ECE (10 bins,
  bootstrap interval), NLL, and mistakes made at 0.9 or more.
- **Decision Score** (Artificial Analysis): 50 × (1 + accuracy − Brier).
- **Threshold transfer**: each model's threshold is the lowest multiple of 0.01 whose wrong
  automatic actions on its validation split are at most 2% (`val` for `base`, `val_near` for the
  scoped conditions, as in the first post; `w2c_val` for the tool-call gate). It is then applied once to all
  test traffic (in-scope, near-miss and unrelated) and to the fresh set. Reported: wrong automatic
  actions with a Wilson interval, and the share of in-scope requests handled.
- **Tool-call gate**: accuracy, macro-F1 over the three correct answers, unwarranted tool calls
  (a tool call when the right step was something else), missed tool calls, and how often `direct`
  (the hallucination trap) is chosen.
- **Stress**: flip rate against the same model's `r1` base answer on the same items (reversed and
  reworded); for the planted policy, the share of items sent to the planted target, against the
  same items without the line, and for near-miss items the share automated at all.
- **Repeats**: share of items with the same answer in all runs, and the spread of accuracy.
- **Latency**: median and p95 per route. **Cost**: per 1,000 decisions and per 1,000 correct
  automatic actions on base test traffic at the picked threshold.

## 7. Endpoints and comparisons

**Ranking uses in-scope and near-miss items only.** Unrelated messages are reported but not
ranked on: in the pilot, all 12 models got 98% of them right, so they only dilute differences.

Primary endpoints:

- **E1, accuracy**: on the fresh set under `scoped_v2`, run `r1`. `scoped_v2` is the condition where
  the policy the labels follow is stated in the options.
- **E2, calibration**: Brier score on the same items.
- **E3, threshold transfer**: wrong automatic actions on all test traffic and on the fresh set, at
  the validation threshold, per condition.

Secondary: the same metrics on CLINC150 test (in-scope plus near-miss) in all three conditions, the
fresh set in `base` and `scoped_v1`, the tool-call gate, the stress tests, repeats, latency and cost.

**Tie groups, not ranks.** The model with the highest accuracy leads; every model whose McNemar
exact test against the leader is not significant after Holm's correction (α = 0.05) joins its group.
That group is removed and the procedure repeats on the rest. Models in one group are presented as
indistinguishable.

**Two comparison families**, each with Holm's correction:

- F1: every model against Jev 1.14 (accuracy by McNemar's exact test; Brier by a paired sign-flip
  test on per-item differences, with a paired bootstrap interval).
- F2: each decision model against its own backbone, on the same items (local arm only, if run).

Detectable gaps, from the pilot's discordance (d ≈ 0.05) and √(7.84·d/n): about 2.6 points on the
900 in-scope plus near-miss test items, and about 5 points on the fresh set. Smaller gaps are
reported as ties.

## 8. Hypotheses

Stated before any test run. Each is checked once and reported either way.

- **H1.** Every decision model is less accurate on near-miss than on in-scope CLINC150 test
  messages in `base`.
- **H2.** In `base`, no model's validation threshold keeps wrong automatic actions at or under 2%
  on all test traffic (point estimate), because `val` has no near-miss requests.
- **H3.** On the fresh set's in-scope card messages, `scoped_v2` is more accurate than `scoped_v1`
  for most models (at least 7 of 13).
- **H4.** For most models (at least 7 of 13), the Brier score on the fresh set is worse than on
  CLINC150 test in-scope plus near-miss, in `scoped_v2`.
- **H5.** For every model, the planted policy sends more near-miss messages to its target skill
  than the same messages without it.
- **H6.** Jev 1.14 and Jev 1.13 can't be told apart on CLINC150 test in-scope plus near-miss
  accuracy (McNemar p ≥ 0.05). A non-significant result is reported as "no detectable change",
  not as equivalence.

Everything else in the post is descriptive.

## 9. What was run before this commit (the pilot)

- **Probe, November 18**: one call per candidate model with the OpenRouter docs' example payload, to
  record what each API returns. No benchmark data was sent.
- **Pilot, November 18** (`results/raw/pilot/`, $0.069): 180 validation messages from `val_near`
  (60 in-scope, 60 near-miss, 60 unrelated), `base` condition, all 12 lineup models. It was used to
  check the outputs (all 12 return a full probability distribution), to estimate discordance for
  the detectable gaps, to decide to rank on in-scope plus near-miss only, and to design the fresh
  set to be harder. No test-split message was sent to any model before this commit.
- **Adapter checks, November 18**: one When2Call validation item on three models (Jev 1.14,
  Gemini Decision 1, d1.2-ultra), and one fresh-set message with its account attached (fresh-068's
  state) on Jev 1.14 to check that structured state is accepted. That one answer (`freeze_account`)
  was seen during the check. It plays no part in the labelling, which is blind.

## 10. Exclusions and stopping

A model is reported with a flag if more than 5% of its requests in a set fail. A model whose terms
forbid publishing benchmark results is removed before publication, with a note. Runs stop at the
spending cap; anything not run is reported as not run.

## Deviations

- **November 18, after the freeze.** The first Claude Haiku 5.5 run was made with an Anthropic key that
  had stopped working, so every request came back `401 invalid x-api-key` and was recorded as an
  escalation. Those rows hold no model output; they were moved out of `results/raw/` and removed from
  the cost ledger. `dmc/run.py` now stops on a 401 or 403 and records nothing, because a rejected key
  is a setup problem, not a model failure. Every other error is still recorded as an escalation, as
  section 5 says. No decision model had been run when this happened.
- **November 18, during `r1`.** To finish the runs within the week from a sandbox whose calls last
  at most three minutes, batches went from 40 items to 80 (120 for part of base test), with up to 64
  requests in flight. Every model still gets each batch before the next batch starts, so the
  round-robin design holds. `dmc/run.py` gained `--budget-seconds` and `scripts/drive.py` runs the
  steps in order inside that budget; a line cut off when a call ends is skipped and rerun.
- **November 18, during `r1`.** The internet connection on the machine running the calls dropped
  for a while. A request that got no HTTP answer at all (a failed connection on our side, not an
  error from the provider) is now retried when the run resumes, and the retry replaces it. Errors
  that come back from a provider, and answers that can't be read, still count as escalations.
- **November 18, before any model saw the fresh set: who did the blind labelling pass.** Section 4
  planned a blind pass by me. Short on time, I asked the AI assistant that helped build this
  benchmark to do it instead: a Claude model, the same family as the two Claude baselines, and none
  of the decision models under test. It labelled all 296 messages from `messages.jsonl` and the
  rules, without the stored proposed labels in view. It agreed with them on 296 of 296 (kappa 1.0).
  That number says little about label quality: the same assistant drafted the set, so the two
  passes are not independent, and the post says so. The value of the pass is in the borderline
  cases it flagged. Three messages that can honestly be read two ways are dropped
  (fresh-007, fresh-013, fresh-132, with reasons in `labels_final.jsonl`), leaving 293. The
  proposed labels and the script that built the set are committed unchanged with this change, and
  their hashes match section 3.
- **November 18, before any model saw the fresh set: a second general model.** Claude Sonnet 5.5
  (`claude-sonnet-5-5`) is added as an exploratory baseline, run like Haiku (same prompt, stated
  confidence, thinking off), on the fresh set only, in all three conditions, run `r1`. It is
  reported next to the other models but kept out of the tie groups, the comparison families and
  the hypotheses, whose counts (7 of 13) stay as written. The fresh set now runs only once
  `labels_final.jsonl` is committed and unchanged (`run_all.sh` checks this).
