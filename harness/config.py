"""Models, prices and paths used by the harness."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
RESULTS = ROOT / "results"
CACHE = RESULTS / ".cache"
GOLD_LABELS = ROOT / "data" / "golden" / "labels.jsonl"
SPLIT = ROOT / "data" / "golden" / "split.json"
META = ROOT / "data" / "golden" / "generation_meta.jsonl"

SYSTEM_MODEL = "gemini-3.1-flash-lite"   # the system under test
JUDGE_MODEL = "gemini-3.5-flash-lite"    # a different, newer model grades it
JUDGE_THINKING = "high"                  # the judge reasons before grading; the system does not
# The Flash models were the first choice for the judge, but their free tier allows
# only 20 requests per day per model (GenerateRequestsPerDayPerProjectPerModel-FreeTier),
# far too few for this project. Development runs on the free tier.

# Paid-tier (Standard) USD per 1M tokens, from ai.google.dev/gemini-api/docs/pricing
# on 2026-09-28. Thinking tokens are billed as output. The free tier costs $0;
# these prices are what the same traffic costs when paid.
PRICES = {
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
}

# Requests per minute the harness allows itself per model, kept under the free
# tier's limits so runs don't stall in retry loops.
REQUESTS_PER_MINUTE = {
    "gemini-3.1-flash-lite": 10,
    "gemini-3.5-flash-lite": 10,
}


def cost_usd(model, input_tokens, output_tokens):
    price = PRICES[model]
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
