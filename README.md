# PolicyJudge: Corvina Airways policy QA

CS496 AI Engineering, Project 1. An evaluation harness and an LLM judge for a task with no single correct answer: answering customer questions about an airline's policy.

The task: given a section of the (fictional) Corvina Airways policy handbook and a customer question, write an answer. A good answer is correct, complete and grounded in the policy. Many different wordings are equally good, so exact match cannot score it.

## Setup

```
pip install -r requirements.txt
ollama pull qwen3:8b
```

Install [Ollama](https://ollama.com) and keep it running (the Ollama app, or `ollama serve`). No API key is needed. Every model call is cached in `results/.cache/`, so rerunning an experiment that already ran is instant and gives the same results, even without Ollama.

## Run

Everything, in order (about 3 hours on a laptop RTX 4070 from an empty cache):

```
python -m scripts.run_all
```

Or one experiment at a time:

```
python -m harness.run judge  --prompt v1 --split dev
python -m harness.run system --prompt v1 --judge-prompt v1 --split dev
python -m harness.run bias   --judge-prompt v1 --pairwise-prompt v1 --split dev
```

- `judge`: grades every golden answer and compares the judge with the human labels.
- `system`: the system answers every golden question; the judge grades each answer.
- `bias`: position bias (two answers shown in both orders) and verbosity bias (an answer padded with content-free filler).

Each run writes `results/<run id>.jsonl` (one row per item: input, output, score, reason, tokens, latency, cost) and `results/<run id>.summary.json`, and updates `prompts/CHANGELOG.md`. `python -m scripts.cost_model <system run id>` writes the cost model.

## Models

| Role | Model | Reasoning |
|---|---|---|
| System under test | `qwen3:8b` (local, Ollama) | off |
| Judge | `qwen3:8b` (local, Ollama) | on |

Both run locally, so there is no API key, no rate limit and no per-token cost. Models and settings are in `harness/config.py`.

## Repository

| Path | What it is |
|---|---|
| `data/policy/corvina_handbook.md` | The fictional policy handbook (15 sections). Its rules deliberately differ from real airlines, so answers from memory are caught. |
| `data/golden/items.jsonl` | The golden set: 100 questions, each with an answer to grade. |
| `data/golden/labels.jsonl` | Final labels: 87 agreed by both labellers, 13 adjudicated (reasons in `data/labels/adjudication.jsonl`). |
| `data/golden/split.json` | Dev (50) / test (50) split, stratified by verdict and question type. |
| `data/golden/generation_meta.jsonl` | How each answer was built (intended verdict, flaw type). Hidden from labellers. |
| `data/labelling_guide.md` | What "good" means, with examples. |
| `data/labels/` | Raw and imported labels from the four labellers, adjudication rulings. |
| `harness/` | Runner (`run.py`), model calls to Ollama (`llm.py`), schemas, metrics, config. |
| `prompts/` | Versioned prompts and `CHANGELOG.md`. |
| `results/` | Per-item results and summaries for every run. |
| `scripts/` | Labelling page, label import, agreement, split, final labels, cost model, `run_all`. |
| `labelling/` | The labelling page used by the four labellers. |

## Results

All on `qwen3:8b`. Counts and percentages; the test split was used once.

| Measure | Result |
|---|---|
| Human labellers' agreement (100 items, two labels each) | 87/100 (87%), Fleiss' κ 0.74, 0 dropped |
| Judge vs. human labels, **test** | **47/50 (94.0%)**, κ 0.88; bad answers caught 23/25, good answers passed 24/25 |
| Judge vs. human labels, dev | 46/50 (92.0%), κ 0.84 |
| Judge on the 87 items both labellers agreed on | 82/87 (94.3%) |
| Position bias: verdict changed after swapping order (dev) | 9/50 pairs (18%); first-shown answer won 46/89 (51.7%) |
| Verbosity bias: grade changed after padding (dev) | 0/44 |
| System v1, dev → v2, dev | 37/50 (74%) → 36/50 (72%) |
| **System v1, test** (final) | **38/50 (76.0%)** |
| Judge latency per item (test) | mean 20.0 s, median 13.8 s |
| Cost per 1,000 requests (system + judge on 10% sample, electricity) | $0.020; 100x volume needs ~8 laptop-class GPUs |

Details: `report/report.tex`, `prompts/CHANGELOG.md`, `results/*.summary.json`, `postmortem.md`.

## Contributions

- **Oussama**: labeller1.
- **Feriel**: labeller 2.
- **Faten**: labeller 3.
- **Ines**: labeller 4.
