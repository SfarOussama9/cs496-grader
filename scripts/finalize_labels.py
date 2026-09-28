"""Build the final golden labels from the human labels and the adjudication file.

Usage (from the repo root):
    python -m scripts.finalize_labels oussama feriel faten ines

For each item:
  - both labellers gave the same verdict -> that verdict ("agreed");
  - they disagreed -> the ruling in data/labels/adjudication.jsonl ("adjudicated").
A criterion (correct / complete / grounded) is kept when both labellers agree
on it or when it was adjudicated; otherwise it is null (disputed), since the
verdict is the gold label and the criteria are only diagnostic.

Writes data/golden/labels.jsonl and prints a summary. Fails if a disagreement
has no ruling or an item is missing labels.
"""
import argparse
import json
import sys
from collections import Counter

from harness.data import ROOT, load_items, load_jsonl

LABELS_DIR = ROOT / "data" / "labels"
ADJUDICATION = LABELS_DIR / "adjudication.jsonl"
OUT = ROOT / "data" / "golden" / "labels.jsonl"
CRITERIA = ["correct", "complete", "grounded"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="+")
    args = parser.parse_args()

    by_item = {}
    for name in args.names:
        for row in load_jsonl(LABELS_DIR / f"{name}.jsonl"):
            by_item.setdefault(row["id"], []).append(row)
    rulings = {r["id"]: r for r in load_jsonl(ADJUDICATION)} if ADJUDICATION.exists() else {}

    problems, final = [], []
    for item in load_items():
        rows = [r for r in by_item.get(item["id"], []) if not r["dropped"]]
        if len(rows) != 2:
            problems.append(f"{item['id']}: {len(rows)} usable labels")
            continue
        a, b = rows
        out = {"id": item["id"], "labellers": [a["labeller"], b["labeller"]]}
        if a["verdict"] == b["verdict"]:
            out["verdict"] = a["verdict"]
            out["source"] = "agreed"
            for c in CRITERIA:
                out[c] = a[c] if a[c] == b[c] else None
        elif item["id"] in rulings:
            ruling = rulings[item["id"]]
            out["verdict"] = ruling["verdict"]
            out["source"] = "adjudicated"
            out["reason"] = ruling["reason"]
            for c in CRITERIA:
                out[c] = ruling[c]
        else:
            problems.append(f"{item['id']}: labellers disagree and there is no ruling")
            continue
        final.append(out)

    if problems:
        sys.exit("cannot finalize:\n  " + "\n  ".join(problems))
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for row in final:
            f.write(json.dumps(row) + "\n")

    print(f"wrote {OUT.relative_to(ROOT)} ({len(final)} items)")
    print("source: ", dict(Counter(r["source"] for r in final)))
    print("verdict:", dict(Counter(r["verdict"] for r in final)))
    unused = sorted(set(rulings) - {r["id"] for r in final if r["source"] == "adjudicated"})
    if unused:
        print("rulings not needed (labellers agreed):", unused)


if __name__ == "__main__":
    main()
