"""Models, cost assumptions and paths used by the harness."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
RESULTS = ROOT / "results"
CACHE = RESULTS / ".cache"
GOLD_LABELS = ROOT / "data" / "golden" / "labels.jsonl"
SPLIT = ROOT / "data" / "golden" / "split.json"
META = ROOT / "data" / "golden" / "generation_meta.jsonl"

# Models run locally through Ollama (https://ollama.com): `ollama pull qwen3:8b`.
SYSTEM_MODEL = "qwen3:8b"
SYSTEM_THINKING = False      # the system answers directly
JUDGE_MODEL = "qwen3:8b"
JUDGE_THINKING = True        # the judge reasons before grading

OLLAMA_URL = "http://localhost:11434"
# Fixed seed for repeatable sampling; 8k context so long reasoning never truncates the input.
OLLAMA_OPTIONS = {"num_ctx": 8192, "seed": 496}

# Local models have no per-token price: cost is the electricity used while the
# GPU works on a request. Assumptions (change them to your own numbers):
GPU_WATTS = 120          # laptop RTX 4070 under load, whole-system draw ~120 W
USD_PER_KWH = 0.10       # household electricity price


def cost_usd(latency_s):
    return (latency_s or 0) * GPU_WATTS / 3_600_000 * USD_PER_KWH
