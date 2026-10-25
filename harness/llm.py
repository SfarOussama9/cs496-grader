"""One structured model call to a local Ollama model, with a disk cache and
token/latency/cost logging.

Every call is cached under results/.cache/ keyed by model, prompt, input, schema
and thinking setting. Re-running an unchanged experiment costs nothing and
reproduces the same results (the cache is committed).
"""
import hashlib
import json
import time
import urllib.error
import urllib.request

from pydantic import ValidationError

from harness.config import CACHE, OLLAMA_OPTIONS, OLLAMA_URL, cost_usd


def call(model, system_prompt, user_content, schema, thinking=False):
    """Return a dict: parsed (schema instance or None), error, tokens, latency_s, cost_usd, cached.

    thinking: False to answer directly, True to reason before answering.
    """
    key = _cache_key(model, system_prompt, user_content, schema, thinking)
    path = CACHE / f"{key}.json"
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        record["cached"] = True
    else:
        record = _call_ollama(model, system_prompt, user_content, schema, thinking)
        if record["error"] is None:  # never cache failures
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record), encoding="utf-8")
        record["cached"] = False
    try:
        record["parsed"] = schema.model_validate_json(record["raw"]) if record["raw"] else None
    except ValidationError as e:
        record["parsed"], record["error"] = None, f"schema: {e.errors()[0]['msg']}"
    return record


def _cache_key(model, system_prompt, user_content, schema, thinking):
    blob = json.dumps([model, system_prompt, user_content, schema.model_json_schema(), thinking], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _call_ollama(model, system_prompt, user_content, schema, thinking):
    body = {
        "model": model, "stream": False, "think": bool(thinking),
        "format": schema.model_json_schema(), "options": OLLAMA_OPTIONS,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
    }
    request = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    last_error = None
    for attempt in range(3):
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=900) as r:
                resp = json.load(r)
        except urllib.error.URLError as e:
            if isinstance(getattr(e, "reason", None), ConnectionRefusedError):
                raise SystemExit(f"Ollama is not running at {OLLAMA_URL}: start the Ollama app, then rerun.")
            last_error = f"ollama: {e}"
            time.sleep(5 * (attempt + 1))
            continue
        latency = time.perf_counter() - start
        message = resp.get("message", {})
        content, reasoning = message.get("content", ""), message.get("thinking") or ""
        # Ollama reports one count for all generated tokens; split it between
        # reasoning and answer in proportion to their length.
        generated = resp.get("eval_count", 0)
        thinking_tokens = round(generated * len(reasoning) / max(1, len(reasoning) + len(content)))
        tokens = {"input": resp.get("prompt_eval_count", 0), "output": generated - thinking_tokens,
                  "thinking": thinking_tokens}
        return {"model": model, "raw": content, "error": None if content else "empty response",
                "tokens": tokens, "latency_s": round(latency, 3), "cost_usd": cost_usd(latency)}
    return {"model": model, "raw": None, "error": last_error, "tokens": {"input": 0, "output": 0, "thinking": 0},
            "latency_s": None, "cost_usd": 0.0}
