# The Grader: Corvina Airways policy QA

CS496 AI Engineering, Project 1. An evaluation harness and an LLM judge for a task with no single correct answer: answering customer questions about an airline's policy.

The task: given a section of the (fictional) Corvina Airways policy handbook and a customer question, write an answer. A good answer is correct, complete and grounded in the policy. Many different wordings are equally good, so exact match cannot score it.

## Setup

```
pip install -r requirements.txt
```

Put a Gemini API key in a file named `.env` at the repo root (never commit it):

```
GEMINI_API_KEY=your-key-here
```

Every model call is cached in `results/.cache/`, so rerunning an experiment that already ran needs no key and costs nothing.

## Run

```
python -m harness.run judge  --prompt v1 --split dev
python -m harness.run system --prompt v1 --judge-prompt v1 --split dev
python -m harness.run bias   --judge-prompt v1 --pairwise-prompt v1 --system-run <system run id> --split dev
```

- `judge`: grades every golden answer and compares the judge with the human labels.
- `system`: the system answers every golden question; the judge grades each answer.
- `bias`: position bias (two answers shown in both orders) and verbosity bias (an answer padded with content-free filler).

Each run writes `results/<run id>.jsonl` (one row per item: input, output, score, reason, tokens, latency, cost) and `results/<run id>.summary.json`, and updates `prompts/CHANGELOG.md`.

## Models

| Role | Model | Reasoning | Paid price per 1M tokens (in / out) |
|---|---|---|---|
| System under test | `gemini-3.1-flash-lite` | off | $0.25 / $1.50 |
| Judge | `gemini-3.5-flash-lite` | high | $0.30 / $2.50 |

The judge is a different, newer model than the system, so it never grades its own answers, and it reasons before grading. Development ran on the Gemini free tier; the Flash models were ruled out because their free tier allows only 20 requests per day.

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
| `harness/` | Runner, model calls, schemas, metrics. |
| `prompts/` | Versioned prompts and `CHANGELOG.md`. |
| `results/` | Per-item results and summaries for every run. |
| `scripts/` | Labelling page, label import, agreement, split, final labels. |
| `labelling/` | The labelling page used by the four labellers. |

## Results

To be filled in from the final runs.

## Contributions

- **Oussama**: to be filled in.
- **Feriel**: labeller 2.
- **Faten**: labeller 3.
- **Ines**: labeller 4.
