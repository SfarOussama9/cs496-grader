"""Build the labelling page in labelling/.

Usage (from the repo root):
    python -m scripts.make_label_page --people 4

Writes labelling/label_app.html: open it in a browser or send it as a file.

With --people N, the items are split into N equal blocks and labeller i gets
blocks i and i+1 (wrapping around), so every item is labelled by exactly two
people. Each labeller picks their number on the page. Without --people, the
page shows every item to one labeller.

The page embeds the items, policy sections and labelling guide (never
generation_meta). Labellers copy their labels and paste them to you; run
scripts.import_labels on the pasted text. Rebuild whenever the items,
handbook or guide change.
"""
import argparse
import json

from harness.data import ROOT, load_items, load_sections

TEMPLATE = ROOT / "scripts" / "label_app_template.html"
GUIDE = ROOT / "data" / "labelling_guide.md"
OUT_DIR = ROOT / "labelling"
LOCAL_SKELETON = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                  '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                  '</head>\n<body>\n{content}\n</body>\n</html>\n')


def assignments(ids, people):
    size = -(-len(ids) // people)  # ceiling division
    blocks = [ids[i * size:(i + 1) * size] for i in range(people)]
    return [blocks[i] + blocks[(i + 1) % people] for i in range(people)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--people", type=int, default=0, help="number of labellers (>= 2)")
    args = parser.parse_args()

    items = sorted(load_items(), key=lambda it: it["id"])
    ids = [it["id"] for it in items]
    split = assignments(ids, args.people) if args.people >= 2 else None
    data = {"pageId": f"golden{len(items)}-{args.people or 1}", "items": items,
            "sections": load_sections(), "guide": GUIDE.read_text(encoding="utf-8"),
            "assignments": split}
    payload = json.dumps(data).replace("</", "<\\/")
    content = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)

    OUT_DIR.mkdir(exist_ok=True)
    for old in OUT_DIR.glob("label_app*.html"):
        old.unlink()
    (OUT_DIR / "label_app.html").write_text(LOCAL_SKELETON.format(content=content), encoding="utf-8", newline="\n")
    print(f"wrote labelling/label_app.html ({len(items)} items)")

    lines = ["# Labelling assignments", ""]
    if split:
        lines += [f"{len(items)} items, {args.people} labellers, every item labelled by exactly two people.", "",
                  "| Labeller | Items |", "|---|---|"]
        for n, mine in enumerate(split, 1):
            half = len(mine) // 2
            lines.append(f"| {n} | {mine[0]}-{mine[half - 1]}, {mine[half]}-{mine[-1]} |")
    else:
        lines.append(f"One labeller, all {len(items)} items.")
    (OUT_DIR / "assignments.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
