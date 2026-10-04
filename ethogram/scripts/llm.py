"""Thin wrapper around the Claude API for ethogram coding runs.

Every call is logged to ethogram/work/llm_log/<run>/<name>.json with the full request
parameters, the output text and token usage, so runs can be audited and repeated.
The key is read from ANTHROPIC_API_KEY or ~/.keys/key.txt and never logged.
"""

import json
import os
import time
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "ethogram" / "work" / "llm_log"

# First-party list prices, $ per million tokens (input, output); from the claude-api skill, cached 2026-09-25.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
}


def client():
    key = os.environ.get("ANTHROPIC_API_KEY") or (Path.home() / ".keys" / "key.txt").read_text().strip()
    return anthropic.Anthropic(api_key=key, max_retries=4)


def call_json(run, name, model, system, user, schema, effort="high", max_tokens=64000, fallback=True):
    """Stream one request whose output must match `schema`; return (parsed_json, record)."""
    params = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    if model.startswith("claude-haiku-4-5"):
        del params["output_config"]["effort"]  # Haiku 4.5 rejects the effort setting
    if model in ("claude-opus-4-8", "claude-opus-4-7"):
        params["thinking"] = {"type": "adaptive"}  # these models run without thinking unless asked
    extra = {}
    if fallback and model in ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1"):
        # on a policy decline, the API re-runs the request on a fallback model inside the same call
        extra = dict(betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"})
    t0 = time.time()
    with client().beta.messages.stream(**params, **extra) as stream:
        msg = stream.get_final_message()
    # After a mid-stream decline the content holds the declined model's partial text, then a
    # fallback block, then the fallback model's answer: keep only what follows the last switch.
    last_switch = max((i for i, b in enumerate(msg.content) if b.type == "fallback"), default=-1)
    text = "".join(b.text for b in msg.content[last_switch + 1:] if b.type == "text")
    switches = [b.model_dump(exclude_none=True) for b in msg.content if b.type == "fallback"]
    usage = msg.usage
    price_in, price_out = PRICES.get(msg.model, PRICES.get(model, (0, 0)))
    record = {
        "run": run,
        "name": name,
        "model_requested": model,
        "model_served": msg.model,
        "fallback_switches": switches,
        "usage_detail": usage.model_dump(exclude_none=True),
        "stop_details": msg.stop_details.model_dump(exclude_none=True) if getattr(msg, "stop_details", None) else None,
        "stop_reason": msg.stop_reason,
        "seconds": round(time.time() - t0, 1),
        "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
        "est_cost_usd": round(usage.input_tokens / 1e6 * price_in + usage.output_tokens / 1e6 * price_out, 4),
        "params": {k: v for k, v in params.items() if k != "messages"} | {"user": user},
        "output": text,
    }
    out = LOG_DIR / run
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"{name}: refused ({getattr(msg, 'stop_details', None)})")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError(f"{name}: hit max_tokens; output truncated")
    return json.loads(text), record
