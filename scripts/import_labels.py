"""Import labels that labellers pasted back to you.

Paste everything you received (any number of labellers, in any order, chat
timestamps and all) into one text file, then run from the repo root:
    python -m scripts.import_labels data/labels/inbox.txt

Every line containing a label is picked out and written to
data/labels/<labeller>.jsonl, merged with what is already there (for an item
labelled twice by the same person, the newest label wins).
"""
import argparse
import json
import re
import sys
from pathlib import Path

from harness.data import ROOT, load_items, load_jsonl

LABELS_DIR = ROOT / "data" / "labels"
REQUIRED = {"id", "labeller", "dropped", "labelled_at"}


def extract(text):
    rows = []
    for line in text.splitlines():
        match = re.search(r"\{.*\}", line)
        if not match:
            continue
        try:
            row = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and REQUIRED <= row.keys():
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path, help="text files containing pasted labels")
    args = parser.parse_args()

    rows = [row for f in args.files for row in extract(f.read_text(encoding="utf-8"))]
    if not rows:
        sys.exit("no labels found in the given files")
    valid_ids = {it["id"] for it in load_items()}
    unknown = sorted({r["id"] for r in rows} - valid_ids)
    if unknown:
        sys.exit(f"labels for unknown item ids {unknown[:5]}: were they made from an older page?")

    by_labeller = {}
    for row in rows:
        by_labeller.setdefault(row["labeller"], []).append(row)
    for labeller, new_rows in sorted(by_labeller.items()):
        path = LABELS_DIR / f"{labeller}.jsonl"
        merged = {r["id"]: r for r in load_jsonl(path)} if path.exists() else {}
        for row in new_rows:
            old = merged.get(row["id"])
            if old is None or row["labelled_at"] >= old["labelled_at"]:
                merged[row["id"]] = row
        LABELS_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for item_id in sorted(merged):
                f.write(json.dumps(merged[item_id]) + "\n")
        print(f"{labeller}: {len(merged)} items -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
