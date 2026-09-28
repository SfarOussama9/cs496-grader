"""Load the policy handbook and the golden set."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDBOOK = ROOT / "data" / "policy" / "corvina_handbook.md"
ITEMS = ROOT / "data" / "golden" / "items.jsonl"

_SECTION_RE = re.compile(r"^## (S\d\d) .*?(?=^## |\Z)", re.M | re.S)


def load_sections(path=HANDBOOK):
    """Return {section_id: full section text including its heading}."""
    text = path.read_text(encoding="utf-8")
    return {m.group(1): m.group(0).strip() for m in _SECTION_RE.finditer(text)}


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_items(path=ITEMS):
    return load_jsonl(path)


def policy_context(item, sections):
    """The policy text shown with an item: its cited sections, in handbook order."""
    return "\n\n".join(sections[s] for s in sorted(item["sections"]))
