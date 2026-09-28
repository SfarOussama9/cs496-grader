"""Inter-annotator agreement between two or more labellers.

Usage (from the repo root):
    python -m scripts.agreement alice bob carol dave

Every item labelled by exactly two people (neither of whom dropped it) is
compared. Prints coverage, pooled percent agreement and Fleiss' kappa per
criterion and for the verdict, agreement for each pair of labellers, and the
dropped items. Writes the disagreements to data/labels/disagreements.jsonl for
adjudication.
"""
import argparse
import json
import sys
from itertools import combinations

from harness.data import ROOT, load_items, load_jsonl

LABELS_DIR = ROOT / "data" / "labels"
FIELDS = ["correct", "complete", "grounded", "verdict"]


def fleiss_kappa(pairs):
    """Fleiss' kappa for items that each have two ratings: [(a, b), ...]."""
    n_items, raters = len(pairs), 2
    categories = {v for pair in pairs for v in pair}
    share = {c: sum(pair.count(c) for pair in pairs) / (n_items * raters) for c in categories}
    expected = sum(p * p for p in share.values())
    observed = sum(
        (sum(pair.count(c) ** 2 for c in categories) - raters) / (raters * (raters - 1))
        for pair in pairs
    ) / n_items
    if expected == 1:
        return float("nan")  # everyone used one identical label: kappa undefined
    return (observed - expected) / (1 - expected)


def load_labels(name):
    path = LABELS_DIR / f"{name}.jsonl"
    if not path.exists():
        sys.exit(f"no labels found at {path.relative_to(ROOT)}")
    return {row["id"]: row for row in load_jsonl(path)}  # last entry per id wins


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="+", help="labeller names (files in data/labels/)")
    args = parser.parse_args()
    if len(args.names) < 2:
        sys.exit("need at least two labellers")
    sys.stdout.reconfigure(encoding="utf-8")

    labels = {name: load_labels(name) for name in args.names}
    items = load_items()
    questions = {it["id"]: it["question"] for it in items}

    by_item = {}
    for name, rows in labels.items():
        for item_id, row in rows.items():
            by_item.setdefault(item_id, []).append((name, row))

    dropped = {i: rs for i, rs in by_item.items() if any(r["dropped"] for _, r in rs)}
    compared = {i: rs for i, rs in by_item.items() if i not in dropped and len(rs) == 2}
    missing = [it["id"] for it in items if len(by_item.get(it["id"], [])) < 2 and it["id"] not in dropped]
    extra = [i for i, rs in by_item.items() if len(rs) > 2]

    print(f"Items in golden set:          {len(items)}")
    print(f"Compared (2 labels each):     {len(compared)}")
    print(f"Dropped by a labeller:        {len(dropped)} ({len(dropped) / len(items):.1%})")
    print(f"Still missing a second label: {len(missing)}")
    if extra:
        print(f"Labelled by more than two (ignored): {len(extra)}")
    if not compared:
        return

    ids = sorted(compared)
    print(f"\n{'field':<10}{'agree':>12}{'%':>9}{'kappa':>9}   yes/pass share")
    for field in FIELDS:
        pairs = [tuple(r[field] for _, r in compared[i]) for i in ids]
        agree = sum(a == b for a, b in pairs)
        pos = "pass" if field == "verdict" else True
        share = sum(v == pos for p in pairs for v in p) / (2 * len(pairs))
        print(f"{field:<10}{agree:>6}/{len(pairs):<5}{agree / len(pairs):>9.1%}"
              f"{fleiss_kappa(pairs):>9.2f}   {share:.1%}")

    print(f"\n{'pair':<28}{'items':>6}{'verdict agree':>16}")
    for a, b in combinations(args.names, 2):
        shared = [i for i in ids if {n for n, _ in compared[i]} == {a, b}]
        if shared:
            agree = sum(labels[a][i]["verdict"] == labels[b][i]["verdict"] for i in shared)
            print(f"{a + ' / ' + b:<28}{len(shared):>6}{agree:>9}/{len(shared)} {agree / len(shared):6.1%}")

    if dropped:
        print("\nDropped items:")
        for i in sorted(dropped):
            for name, r in dropped[i]:
                if r["dropped"]:
                    print(f"  {i}  {name}: {r['drop_reason']}")

    out = LABELS_DIR / "disagreements.jsonl"
    disagreements = [i for i in ids
                     if any(compared[i][0][1][f] != compared[i][1][1][f] for f in FIELDS)]
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for i in disagreements:
            (na, ra), (nb, rb) = compared[i]
            f.write(json.dumps({
                "id": i,
                "question": questions.get(i, ""),
                "differs_on": [fld for fld in FIELDS if ra[fld] != rb[fld]],
                na: {fld: ra[fld] for fld in FIELDS} | {"note": ra.get("note", "")},
                nb: {fld: rb[fld] for fld in FIELDS} | {"note": rb.get("note", "")},
            }) + "\n")
    print(f"\n{len(disagreements)} items with any disagreement -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
