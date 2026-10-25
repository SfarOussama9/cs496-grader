"""Cost model: cost per 1k requests, today and at 100x, from a measured system run.

Usage (from the repo root):
    python -m scripts.cost_model <system run id> [--daily 1000] [--judge-sample 0.1]

A "request" is one customer question answered by the system. In production the
judge does not grade every answer; it monitors a sample (--judge-sample).

The models run locally, so cost is electricity (measured time x GPU power x
price per kWh, set in harness/config.py), and the real constraint is capacity:
how many requests one GPU can serve per day.

Writes results/<run id>.cost.md and prints it.
"""
import argparse
import json
import math

from harness.config import GPU_WATTS, JUDGE_MODEL, RESULTS, SYSTEM_MODEL, USD_PER_KWH


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id")
    parser.add_argument("--daily", type=int, default=1000, help="requests per day today")
    parser.add_argument("--judge-sample", type=float, default=0.1, help="share of answers the judge grades")
    args = parser.parse_args()

    summary = json.loads((RESULTS / f"{args.run_id}.summary.json").read_text(encoding="utf-8"))
    sys_u, judge_u = summary["system_usage"], summary["judge_usage"]
    sys_cost, judge_cost = sys_u["cost_per_item_usd"], judge_u["cost_per_item_usd"]
    per_request = sys_cost + args.judge_sample * judge_cost
    gpu_seconds = sys_u["latency_mean_s"] + args.judge_sample * judge_u["latency_mean_s"]

    def tokens(u):
        return (f"{u['mean_input_tokens']:.0f} in / {u['mean_output_tokens'] + u['mean_thinking_tokens']:.0f} out "
                f"(incl. {u['mean_thinking_tokens']:.0f} thinking), {u['latency_mean_s']:.1f} s")

    lines = [
        f"# Cost model ({args.run_id})", "",
        f"Measured means per call: system `{SYSTEM_MODEL}` {tokens(sys_u)}; judge `{JUDGE_MODEL}` {tokens(judge_u)}.", "",
    ]
    lines += [f"Local models: cost = GPU time x {GPU_WATTS} W x USD {USD_PER_KWH}/kWh (electricity only; "
              "hardware is already owned).", ""]
    lines += [
        "| Per 1,000 requests | USD | GPU time |", "|---|---|---|",
        f"| System only | ${1000 * sys_cost:.4f} | {1000 * sys_u['latency_mean_s'] / 3600:.2f} h |",
        f"| Judge on every answer | ${1000 * judge_cost:.4f} | {1000 * judge_u['latency_mean_s'] / 3600:.2f} h |",
        f"| **Production: system + judge on {args.judge_sample:.0%} sample** | **${1000 * per_request:.4f}** "
        f"| **{1000 * gpu_seconds / 3600:.2f} h** |", "",
        "| Volume | Requests/day | USD/day | USD/month (30 d) | GPUs needed (24/7, one request at a time) |",
        "|---|---|---|---|---|",
    ]
    for label, daily in (("Today", args.daily), ("100x", 100 * args.daily)):
        gpus = daily * gpu_seconds / 86_400
        lines.append(f"| {label} | {daily:,} | ${daily * per_request:.2f} | ${30 * daily * per_request:.2f} "
                     f"| {gpus:.2f} -> {max(1, math.ceil(gpus))} |")
    capacity = 86_400 / gpu_seconds
    lines += [
        "",
        "Notes:",
        f"- One GPU serving requests one at a time handles about {capacity:,.0f} requests/day "
        f"({gpu_seconds:.1f} s of GPU time per request including judge monitoring).",
        "- At 100x the cost stays small, but a single laptop GPU cannot keep up: the options are several GPUs, "
        "or batching requests on a server-class GPU.",
        "- Judge monitoring dominates GPU time because of the judge's reasoning tokens; grading a smaller sample "
        "or turning reasoning off (at a measured loss of agreement) are the main levers.",
    ]
    text = "\n".join(lines) + "\n"
    (RESULTS / f"{args.run_id}.cost.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
