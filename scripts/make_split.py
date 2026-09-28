"""Split the golden set into dev (improve prompts) and test (report only).

Usage (from the repo root):
    python -m scripts.make_split

Stratified by gold verdict and question category, 50/50, fixed seed, so both
halves have the same mix. Writes data/golden/split.json. Run once; changing the
split later would invalidate earlier results.
"""
import json
import random

from harness.config import GOLD_LABELS, META, SPLIT
from harness.data import load_jsonl

SEED = 496


def main():
    gold = {r["id"]: r["verdict"] for r in load_jsonl(GOLD_LABELS)}
    category = {m["id"]: m["category"] for m in load_jsonl(META)}
    strata = {}
    for item_id in sorted(gold):
        strata.setdefault((gold[item_id], category[item_id]), []).append(item_id)

    rng = random.Random(SEED)
    dev, test = [], []
    for key in sorted(strata):
        ids = strata[key]
        rng.shuffle(ids)
        # alternate which half gets the odd item so the halves stay equal overall
        half = len(ids) // 2 + (len(ids) % 2 if len(dev) <= len(test) else 0)
        dev += ids[:half]
        test += ids[half:]
    SPLIT.write_text(json.dumps({"seed": SEED, "dev": sorted(dev), "test": sorted(test)}, indent=1) + "\n",
                     encoding="utf-8")
    for name, ids in (("dev", dev), ("test", test)):
        passes = sum(gold[i] == "pass" for i in ids)
        print(f"{name}: {len(ids)} items, {passes} pass / {len(ids) - passes} fail")


if __name__ == "__main__":
    main()
