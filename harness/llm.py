"""One structured Gemini call, with retries, a disk cache and cost/latency logging.

Every call is cached under results/.cache/ keyed by model, prompt, input and
schema. Re-running an unchanged experiment costs nothing and reproduces the
same results, even without an API key (the cache is committed).
"""
import hashlib
import json
import os
import threading
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from harness.config import CACHE, REQUESTS_PER_MINUTE, ROOT, cost_usd

RETRYABLE = {429, 500, 503, 504}
BACKOFF_SECONDS = [5, 10, 20, 40, 60, 60]
_client = None
_client_lock = threading.Lock()
_pace_lock = threading.Lock()
_next_slot = {}  # model -> earliest time the next request may start


def _get_client():
    # One shared client: a second client created by a racing thread would replace
    # the first, which then gets closed while other threads are still using it.
    global _client
    with _client_lock:
        if _client is None:
            load_dotenv(ROOT / ".env")
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise SystemExit("GEMINI_API_KEY is not set: put it in .env (see README).")
            _client = genai.Client(api_key=key)
    return _client


def _wait_for_slot(model):
    """Space requests to one model evenly so the per-minute quota is never exceeded."""
    interval = 60 / REQUESTS_PER_MINUTE.get(model, 10)
    with _pace_lock:
        now = time.monotonic()
        start = max(now, _next_slot.get(model, now))
        _next_slot[model] = start + interval
    time.sleep(start - now)


def _cache_key(model, system_prompt, user_content, schema, thinking):
    blob = json.dumps([model, system_prompt, user_content, schema.model_json_schema(), thinking], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def call(model, system_prompt, user_content, schema, thinking=None):
    """Return a dict: parsed (schema instance or None), error, tokens, latency_s, cost_usd, cached.

    thinking: None for the model's default, or a level such as "high".
    """
    key = _cache_key(model, system_prompt, user_content, schema, thinking)
    path = CACHE / f"{key}.json"
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        record["cached"] = True
    else:
        record = _call_api(model, system_prompt, user_content, schema, thinking)
        if record["error"] is None:  # never cache failures
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record), encoding="utf-8")
        record["cached"] = False
    try:
        record["parsed"] = schema.model_validate_json(record["raw"]) if record["raw"] else None
    except ValidationError as e:
        record["parsed"], record["error"] = None, f"schema: {e.errors()[0]['msg']}"
    return record


def _call_api(model, system_prompt, user_content, schema, thinking):
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=schema,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=thinking) if thinking else None,
    )
    last_error = None
    for wait in [0] + BACKOFF_SECONDS:
        time.sleep(wait)
        _wait_for_slot(model)
        start = time.perf_counter()
        try:
            resp = _get_client().models.generate_content(model=model, contents=user_content, config=config)
        except errors.APIError as e:
            last_error = f"{e.code} {e.status}"
            if e.code in RETRYABLE:
                continue
            break
        latency = time.perf_counter() - start
        usage = resp.usage_metadata
        tokens = {
            "input": usage.prompt_token_count or 0,
            "output": usage.candidates_token_count or 0,
            "thinking": usage.thoughts_token_count or 0,
        }
        return {
            "model": model, "raw": resp.text, "error": None if resp.text else "empty response",
            "tokens": tokens, "latency_s": round(latency, 3),
            "cost_usd": cost_usd(model, tokens["input"], tokens["output"] + tokens["thinking"]),
        }
    return {"model": model, "raw": None, "error": last_error, "tokens": {"input": 0, "output": 0, "thinking": 0},
            "latency_s": None, "cost_usd": 0.0}
