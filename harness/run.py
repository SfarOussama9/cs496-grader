"""Run the system, the judge, or the judge bias checks over the golden set.

Usage (from the repo root):
    python -m harness.run judge  --prompt v1 --split dev
    python -m harness.run system --prompt v1 --judge-prompt v1 --split dev
    python -m harness.run bias   --judge-prompt v1 --pairwise-prompt v1 --system-run <run id> --split dev

judge   grades every golden answer and compares the judge with the human labels.
system  lets the system answer every golden question, then the judge grades it.
bias    position bias (swap two answers) and verbosity bias (pad an answer).

Each run writes results/<run id>.jsonl (one row per item) and
results/<run id>.summary.json, and updates prompts/CHANGELOG.md.
Add --limit N for a quick smoke test (not logged in the changelog).
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from harness import llm
from harness.config import GOLD_LABELS, JUDGE_MODEL, JUDGE_THINKING, META, PROMPTS, RESULTS, SPLIT, SYSTEM_MODEL
from harness.data import load_items, load_jsonl, load_sections, policy_context
from harness.metrics import agreement, breakdown, usage_summary
from harness.schema import JudgeGrade, PairwiseChoice, SystemAnswer

RUNS_INDEX = RESULTS / "runs.jsonl"
CHANGELOG = PROMPTS / "CHANGELOG.md"
PAD_BEFORE = ("Thank you for contacting Corvina Airways. We understand that travel plans can be complex, "
              "and we are always happy to help you make sense of our policies so that your journey is as "
              "smooth and stress-free as possible. Here is the information you asked for.\n\n")
PAD_AFTER = ("\n\nWe hope this information is helpful. If you have any further questions about your trip, "
             "please do not hesitate to reach out to us at any time. We wish you a pleasant flight and look "
             "forward to welcoming you on board.")


# ---------- loading ----------

def load_prompt(kind, version):
    path = PROMPTS / kind / f"{version}.md"
    if not path.exists():
        sys.exit(f"no prompt at {path.relative_to(PROMPTS.parent)}")
    header, _, body = path.read_text(encoding="utf-8").partition("\n")
    return body.strip(), header.lstrip("# ").strip()


def load_golden(split, limit):
    items = {it["id"]: it for it in load_items()}
    gold = {r["id"]: r for r in load_jsonl(GOLD_LABELS)}
    meta = {m["id"]: m for m in load_jsonl(META)}
    ids = json.loads(SPLIT.read_text(encoding="utf-8"))[split] if split != "all" else sorted(items)
    rows = []
    for item_id in ids[:limit] if limit else ids:
        it, m = items[item_id], meta[item_id]
        rows.append({**it, "human_verdict": gold[item_id]["verdict"], "category": m["category"],
                     "flaw": m["flaw"], "style": m["style"]})
    return rows


def judge_input(policy, question, answer):
    return f"POLICY:\n{policy}\n\nQUESTION:\n{question}\n\nANSWER TO GRADE:\n{answer}"


def pairwise_input(policy, question, answer_a, answer_b):
    return f"POLICY:\n{policy}\n\nQUESTION:\n{question}\n\nANSWER A:\n{answer_a}\n\nANSWER B:\n{answer_b}"


def usage_fields(record, prefix):
    return {f"{prefix}tokens": record["tokens"], f"{prefix}latency_s": record["latency_s"],
            f"{prefix}cost_usd": record["cost_usd"], f"{prefix}cached": record["cached"],
            f"{prefix}error": record["error"]}


def grade(judge_prompt, policy, question, answer, prefix="judge_"):
    rec = llm.call(JUDGE_MODEL, judge_prompt, judge_input(policy, question, answer), JudgeGrade, JUDGE_THINKING)
    g = rec["parsed"]
    out = {f"{prefix}verdict": g.verdict if g else "error"}
    if g:
        out.update({f"{prefix}correct": g.correct, f"{prefix}complete": g.complete,
                    f"{prefix}grounded": g.grounded, f"{prefix}reason": g.reason})
    return {**out, **usage_fields(rec, prefix)}


def run_parallel(fn, rows, workers):
    done = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, result in enumerate(pool.map(fn, rows), 1):
            done.append(result)
            if n % 10 == 0 or n == len(rows):
                print(f"  {n}/{len(rows)}", flush=True)
    return done


# ---------- commands ----------

def cmd_judge(args):
    prompt, change = load_prompt("judge", args.prompt)
    sections = load_sections()
    rows = load_golden(args.split, args.limit)

    def one(it):
        g = grade(prompt, policy_context(it, sections), it["question"], it["answer"])
        return {"id": it["id"], "split": args.split, "category": it["category"], "flaw": it["flaw"],
                "style": it["style"], "input": {"question": it["question"], "sections": it["sections"]},
                "output": it["answer"], "human_verdict": it["human_verdict"], **g,
                "score": int(g["judge_verdict"] == it["human_verdict"])}

    results = run_parallel(one, rows, args.workers)
    summary = {
        "agreement_with_humans": agreement(results),
        "errors": sum(r["judge_verdict"] == "error" for r in results),
        "by_flaw": breakdown(results, "flaw"),
        "by_category": breakdown(results, "category"),
        "by_style": breakdown(results, "style"),
        "judge_usage": usage_summary(results, "judge_"),
    }
    a = summary["agreement_with_humans"]
    headline = f"{a['agree']}/{a['n']} ({a['agree_pct']}%), kappa {a['kappa']}"
    finish(args, "judge", {"judge": args.prompt}, change, results, summary, "agreement with humans", headline,
           a["agree_pct"])


def cmd_system(args):
    prompt, change = load_prompt("system", args.prompt)
    judge_prompt, _ = load_prompt("judge", args.judge_prompt)
    sections = load_sections()
    rows = load_golden(args.split, args.limit)

    def one(it):
        policy = policy_context(it, sections)
        user = f"POLICY EXCERPT:\n{policy}\n\nCUSTOMER QUESTION:\n{it['question']}"
        rec = llm.call(SYSTEM_MODEL, prompt, user, SystemAnswer)
        ans = rec["parsed"]
        row = {"id": it["id"], "split": args.split, "category": it["category"],
               "input": {"question": it["question"], "sections": it["sections"]},
               "output": ans.answer if ans else None,
               "policy_covers_question": ans.policy_covers_question if ans else None,
               **usage_fields(rec, "system_")}
        if ans:
            row.update(grade(judge_prompt, policy, it["question"], ans.answer))
        else:
            row["judge_verdict"] = "error"
        row["score"] = int(row["judge_verdict"] == "pass")
        return row

    results = run_parallel(one, rows, args.workers)
    passed = sum(r["judge_verdict"] == "pass" for r in results)
    graded = sum(r["judge_verdict"] in ("pass", "fail") for r in results)
    by_cat = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r["judge_verdict"] == "pass")
    summary = {
        "pass": passed, "graded": graded, "errors": len(results) - graded,
        "pass_pct": round(100 * passed / graded, 1) if graded else None,
        "by_category": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by_cat.items())},
        "system_usage": usage_summary(results, "system_"),
        "judge_usage": usage_summary(results, "judge_"),
    }
    headline = f"{passed}/{graded} pass ({summary['pass_pct']}%)"
    finish(args, "system", {"system": args.prompt, "judge": args.judge_prompt}, change, results, summary,
           "pass rate (judged)", headline, summary["pass_pct"])


def cmd_bias(args):
    judge_prompt, _ = load_prompt("judge", args.judge_prompt)
    pair_prompt, change = load_prompt("judge_pairwise", args.pairwise_prompt)
    sections = load_sections()
    rows = load_golden(args.split, args.limit)
    system_rows = {r["id"]: r for r in load_jsonl(RESULTS / f"{args.system_run}.jsonl")}

    def one(it):
        policy = policy_context(it, sections)
        row = {"id": it["id"], "split": args.split, "flaw": it["flaw"], "style": it["style"],
               "human_verdict": it["human_verdict"], "input": {"question": it["question"]}}
        # Position bias: golden answer vs system answer, shown in both orders.
        sys_answer = (system_rows.get(it["id"]) or {}).get("output")
        if sys_answer:
            first = llm.call(JUDGE_MODEL, pair_prompt, pairwise_input(policy, it["question"], it["answer"], sys_answer),
                             PairwiseChoice, JUDGE_THINKING)
            second = llm.call(JUDGE_MODEL, pair_prompt, pairwise_input(policy, it["question"], sys_answer, it["answer"]),
                              PairwiseChoice, JUDGE_THINKING)
            if first["parsed"] and second["parsed"]:
                who = {"A": "golden", "B": "system", "tie": "tie"}
                who_swapped = {"A": "system", "B": "golden", "tie": "tie"}
                row["position"] = {
                    "order1_choice": first["parsed"].better, "order2_choice": second["parsed"].better,
                    "order1_winner": who[first["parsed"].better],
                    "order2_winner": who_swapped[second["parsed"].better],
                }
                row["position"]["consistent"] = row["position"]["order1_winner"] == row["position"]["order2_winner"]
            row["pairwise_cost_usd"] = first["cost_usd"] + second["cost_usd"]
        # Verbosity bias: the same answer with content-free padding around it.
        if it["style"] == "concise":
            original = grade(judge_prompt, policy, it["question"], it["answer"], prefix="orig_")
            padded = grade(judge_prompt, policy, it["question"], PAD_BEFORE + it["answer"] + PAD_AFTER, prefix="pad_")
            row["verbosity"] = {"original": original["orig_verdict"], "padded": padded["pad_verdict"],
                                "cost_usd": original["orig_cost_usd"] + padded["pad_cost_usd"]}
        return row

    results = run_parallel(one, rows, args.workers)
    pos = [r["position"] for r in results if "position" in r]
    choices = [c for p in pos for c in (p["order1_choice"], p["order2_choice"]) if c != "tie"]
    verb = [r["verbosity"] for r in results if "verbosity" in r
            and {r["verbosity"]["original"], r["verbosity"]["padded"]} <= {"pass", "fail"}]
    summary = {
        "position": {
            "pairs": len(pos),
            "consistent": sum(p["consistent"] for p in pos),
            "flipped": sum(not p["consistent"] for p in pos),
            "flip_pct": round(100 * sum(not p["consistent"] for p in pos) / len(pos), 1) if pos else None,
            "non_tie_choices": len(choices),
            "chose_first_shown": choices.count("A"),
            "chose_first_pct": round(100 * choices.count("A") / len(choices), 1) if choices else None,
        },
        "verbosity": {
            "items": len(verb),
            "unchanged": sum(v["original"] == v["padded"] for v in verb),
            "fail_to_pass": sum(v["original"] == "fail" and v["padded"] == "pass" for v in verb),
            "pass_to_fail": sum(v["original"] == "pass" and v["padded"] == "fail" for v in verb),
        },
    }
    v = summary["verbosity"]
    v["changed_pct"] = round(100 * (v["items"] - v["unchanged"]) / v["items"], 1) if v["items"] else None
    p = summary["position"]
    headline = (f"order flips {p['flipped']}/{p['pairs']} ({p['flip_pct']}%); "
                f"padding changes {v['items'] - v['unchanged']}/{v['items']} ({v['changed_pct']}%)")
    finish(args, "bias", {"judge": args.judge_prompt, "pairwise": args.pairwise_prompt, "system_run": args.system_run},
           change, results, summary, "flip rate", headline, p["flip_pct"])


# ---------- output ----------

def finish(args, kind, prompts, change, results, summary, metric, headline, score):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    versions = "-".join(f"{k[0]}{v}" for k, v in prompts.items() if k != "system_run")
    run_id = f"{kind}-{versions}-{args.split}-{stamp}" + ("-smoke" if args.limit else "")
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / f"{run_id}.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in sorted(results, key=lambda r: r["id"]):
            f.write(json.dumps(r) + "\n")
    meta = {"run_id": run_id, "kind": kind, "split": args.split, "items": len(results), "prompts": prompts,
            "models": {"system": SYSTEM_MODEL, "judge": JUDGE_MODEL, "judge_thinking": JUDGE_THINKING}, "change": change,
            "metric": metric, "score": score, "headline": headline,
            "cost_usd_total": round(sum(total_cost(r) for r in results), 6),
            "fresh_calls_cost_usd": round(sum(total_cost(r, fresh_only=True) for r in results), 6),
            "created_at": stamp}
    (RESULTS / f"{run_id}.summary.json").write_text(json.dumps({**meta, **summary}, indent=1) + "\n",
                                                     encoding="utf-8")
    print(f"\n{run_id}\n{metric}: {headline}")
    print(json.dumps(summary, indent=1))
    if not args.limit:
        log_run(meta)


def total_cost(row, fresh_only=False):
    cost = 0.0
    for prefix in ("system_", "judge_", "orig_", "pad_"):
        if row.get(prefix + "cost_usd") and not (fresh_only and row.get(prefix + "cached")):
            cost += row[prefix + "cost_usd"]
    if not fresh_only:
        cost += row.get("pairwise_cost_usd", 0.0) + (row.get("verbosity") or {}).get("cost_usd", 0.0)
    return cost


def log_run(meta):
    runs = load_jsonl(RUNS_INDEX) if RUNS_INDEX.exists() else []
    same = [r for r in runs if (r["kind"], r["split"]) == (meta["kind"], meta["split"])]
    if same and same[-1]["prompts"] == meta["prompts"] and same[-1]["score"] == meta["score"]:
        print("(same prompts and score as the last logged run: changelog unchanged)")
        return
    with RUNS_INDEX.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(meta) + "\n")
    write_changelog(runs + [meta])


def write_changelog(runs):
    lines = ["# Prompt changelog", "",
             "Generated by `harness.run` from `results/runs.jsonl`: every logged run, with the score before "
             "and after each prompt change. Prompts live in `prompts/<kind>/vN.md`; the first line of each "
             "file says what changed.", ""]
    titles = {"system": "System (pass rate, graded by the judge)", "judge": "Judge (agreement with human labels)",
              "bias": "Judge bias checks (position flip rate)"}
    for kind in ("system", "judge", "bias"):
        for split in ("dev", "test", "all"):
            rows = [r for r in runs if r["kind"] == kind and r["split"] == split]
            if not rows:
                continue
            lines += [f"## {titles[kind]}: {split} split", "",
                      "| Date (UTC) | Prompts | Change | Result | Before -> after | Run |", "|---|---|---|---|---|---|"]
            prev = None
            for r in rows:
                prompts = ", ".join(f"{k} {v}" for k, v in r["prompts"].items() if k != "system_run")
                delta = "first run" if prev is None else f"{prev} -> {r['score']}"
                lines.append(f"| {r['created_at'][:8]} | {prompts} | {r['change']} | {r['headline']} | {delta} "
                             f"| `{r['run_id']}` |")
                prev = r["score"]
            lines.append("")
    CHANGELOG.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("judge", "system", "bias"):
        p = sub.add_parser(name)
        p.add_argument("--split", choices=["dev", "test", "all"], default="dev")
        p.add_argument("--limit", type=int, default=0, help="only the first N items (smoke test, not logged)")
        p.add_argument("--workers", type=int, default=4, help="parallel calls")
    sub.choices["judge"].add_argument("--prompt", default="v1")
    sub.choices["system"].add_argument("--prompt", default="v1")
    sub.choices["system"].add_argument("--judge-prompt", default="v1")
    sub.choices["bias"].add_argument("--judge-prompt", default="v1")
    sub.choices["bias"].add_argument("--pairwise-prompt", default="v1")
    sub.choices["bias"].add_argument("--system-run", required=True, help="run id of a system run on the same split")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    {"judge": cmd_judge, "system": cmd_system, "bias": cmd_bias}[args.command](args)


if __name__ == "__main__":
    main()
