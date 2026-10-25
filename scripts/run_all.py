"""Run every experiment of the project in order, unattended.

Usage (from the repo root, with Ollama running):
    python -m scripts.run_all

 1. judge v1 on dev                 judge vs human labels
 2. system v1 on dev                baseline system, graded by the judge
 3. bias on dev                     position and verbosity checks (uses run 2)
 4. system v2 on dev                improved prompt
 5. judge v1 on test                final judge numbers
 6. system on test                  the better prompt on dev (ties go to v1), run once

Every call is cached, so rerunning after an interruption continues where it stopped.
Output is also appended to results/run_all.log.
"""
import subprocess
import sys
from datetime import datetime

from harness.config import RESULTS
from harness.data import load_jsonl
from harness.run import models_label, models_used

LOG = RESULTS / "run_all.log"


def run(*args):
    cmd = [sys.executable, "-m", "harness.run", *args]
    line = f"\n=== {datetime.now():%H:%M:%S}  {' '.join(args)}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as log:
        log.write(line + "\n")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace")
        for out in proc.stdout:
            print(out, end="", flush=True)
            log.write(out)
        if proc.wait() != 0:
            sys.exit(f"step failed: {' '.join(args)} (see {LOG})")


def dev_score(system_prompt):
    runs = [r for r in load_jsonl(RESULTS / "runs.jsonl")
            if r["kind"] == "system" and r["split"] == "dev" and r["prompts"].get("system") == system_prompt
            and models_label(r) == models_label({"models": models_used()})]
    return runs[-1]["score"] if runs else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    RESULTS.mkdir(exist_ok=True)
    run("judge", "--prompt", "v1", "--split", "dev")
    run("system", "--prompt", "v1", "--judge-prompt", "v1", "--split", "dev")
    run("bias", "--judge-prompt", "v1", "--pairwise-prompt", "v1", "--split", "dev")
    run("system", "--prompt", "v2", "--judge-prompt", "v1", "--split", "dev")
    run("judge", "--prompt", "v1", "--split", "test")
    v1, v2 = dev_score("v1"), dev_score("v2")
    final = "v2" if v1 is not None and v2 is not None and v2 > v1 else "v1"
    print(f"\nDev pass rate: v1 {v1}%, v2 {v2}%  ->  final prompt for test: {final}", flush=True)
    run("system", "--prompt", final, "--judge-prompt", "v1", "--split", "test")
    print("\nAll experiments done. Summaries are in results/*.summary.json; see prompts/CHANGELOG.md.")


if __name__ == "__main__":
    main()
