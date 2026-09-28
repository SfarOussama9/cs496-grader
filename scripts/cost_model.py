"""Cost model: cost per 1k requests, today and at 100x, from a measured system run.

Usage (from the repo root):
    python -m scripts.cost_model <system run id> [--daily 1000] [--judge-sample 0.1]

A "request" is one customer question answered by the system. In production the
judge does not grade every answer; it monitors a sample (--judge-sample). Token
counts are the run's measured means; prices are the paid-tier prices in
harness/config.py. Writes results/<run id>.cost.md and prints it.
"""
import argparse
import json

from harness.config import JUDGE_MODEL, PRICES, REQUESTS_PER_MINUTE, RESULTS, SYSTEM_MODEL


def per_call(usage, model):
    price = PRICES[model]
    out = usage["mean_output_tokens"] + usage["mean_thinking_tokens"]
    return (usage["mean_input_tokens"] * price["input"] + out * price["output"]) / 1_000_000


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id")
    parser.add_argument("--daily", type=int, default=1000, help="requests per day today")
    parser.add_argument("--judge-sample", type=float, default=0.1, help="share of answers the judge grades")
    args = parser.parse_args()

    summary = json.loads((RESULTS / f"{args.run_id}.summary.json").read_text(encoding="utf-8"))
    sys_usage, judge_usage = summary["system_usage"], summary["judge_usage"]
    sys_call, judge_call = per_call(sys_usage, SYSTEM_MODEL), per_call(judge_usage, JUDGE_MODEL)
    per_request = sys_call + args.judge_sample * judge_call

    lines = [
        f"# Cost model ({args.run_id})", "",
        f"Measured means per call: system {sys_usage['mean_input_tokens']:.0f} in / "
        f"{sys_usage['mean_output_tokens'] + sys_usage['mean_thinking_tokens']:.0f} out tokens; "
        f"judge {judge_usage['mean_input_tokens']:.0f} in / "
        f"{judge_usage['mean_output_tokens'] + judge_usage['mean_thinking_tokens']:.0f} out tokens "
        f"(incl. {judge_usage['mean_thinking_tokens']:.0f} thinking).", "",
        "| Per 1,000 requests | USD |", "|---|---|",
        f"| System only (`{SYSTEM_MODEL}`) | ${1000 * sys_call:.3f} |",
        f"| Judge on every answer (`{JUDGE_MODEL}`) | ${1000 * judge_call:.3f} |",
        f"| **Production: system + judge on {args.judge_sample:.0%} sample** | **${1000 * per_request:.3f}** |", "",
        "| Volume | Requests/day | Requests/min (avg) | USD/day | USD/month (30 d) |", "|---|---|---|---|---|",
    ]
    for label, daily in (("Today", args.daily), ("100x", 100 * args.daily)):
        lines.append(f"| {label} | {daily:,} | {daily / 1440:.1f} | ${daily * per_request:.2f} | "
                     f"${30 * daily * per_request:.2f} |")
    peak = 100 * args.daily / 1440 * 3  # assume peak minute = 3x average
    lines += [
        "",
        "Notes:",
        f"- Development ran on the free tier, with the harness pacing itself at "
        f"{REQUESTS_PER_MINUTE[SYSTEM_MODEL]} requests/min per model. At 100x (about {peak:.0f} requests/min "
        "at a 3x peak) the paid tier is required.",
        "- The judge's cost is dominated by thinking tokens; grading a sample instead of every answer is the "
        "main saving.",
        "- Judge monitoring is not latency-sensitive, so it could run through the Batch API at a discount.",
    ]
    text = "\n".join(lines) + "\n"
    (RESULTS / f"{args.run_id}.cost.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
