"""
The MetricMind agent: a local LLM (LM Studio / qwen3) orchestrating a single
governed tool.

The model never writes SQL. It is given exactly one tool — query_semantic_layer —
whose arguments are constrained (by enum) to the whitelisted measures and
dimensions the semantic layer exposes. The model picks *which governed metric to
ask for*; the semantic layer owns *how it is computed*. The agent loops: call the
model, run any tool calls against the semantic layer, feed results back, until the
model produces a final natural-language answer. Every tool call is captured in a
trace for the UI's "View API call" transparency panel.
"""

from __future__ import annotations

import json
import os
import re
import time

from openai import OpenAI

from . import config
from .semantic_client import get_meta, load as semantic_load

# Reasoning models (nemotron, qwen3) spend tokens thinking before the tool call,
# so give generous headroom or they finish with reason="length" and no output.
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

SYSTEM_PROMPT = """You are MetricMind, an analytics agent for a corporate sales dataset.

You answer business questions ONLY by calling the `query_semantic_layer` tool.
You cannot and must not write SQL. You must never invent or estimate numbers —
report only values returned by the tool.

Available measures: {measures}
Available dimensions: {dimensions}
Available time dimensions: {time_dimensions}

Query notes:
- A time dimension with a `granularity` (quarter/month/year) groups by period;
  without one, its `dateRange` is just a filter.
- `dateRange` accepts: "last quarter", a quarter label like "2025-Q3", a year
  like "2025", or an explicit ["2025-07-01","2025-09-30"].
- Measures from `sales` (revenue, cost, margin, ...) and from `order_costs`
  (cost_amount, broken out by `order_costs.cost_type`) cannot be mixed in one
  query — query them separately.
- The data covers 2024-01 through 2025-09; "last quarter" is 2025-Q3.

When asked WHY a metric moved, decompose it: first measure the change, then drill
into its drivers (e.g. break cost down by `order_costs.cost_type` to compare
shipping vs material). After gathering the data, give a concise, specific answer
that cites the actual numbers.

/no_think
"""


def _tool_def(meta: dict) -> dict:
    measures = [m["name"] for m in meta["measures"]]
    dimensions = [d["name"] for d in meta["dimensions"]]
    time_dims = [t["name"] for t in meta["timeDimensions"]]
    return {
        "type": "function",
        "function": {
            "name": "query_semantic_layer",
            "description": (
                "Run a governed metric query against the semantic layer and get "
                "back aggregated rows. You CANNOT write SQL; only name whitelisted "
                "measures and dimensions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "measures": {"type": "array", "items": {"type": "string", "enum": measures}},
                    "dimensions": {"type": "array", "items": {"type": "string", "enum": dimensions}},
                    "timeDimensions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "dimension": {"type": "string", "enum": time_dims},
                                "granularity": {
                                    "type": "string",
                                    "enum": ["day", "week", "month", "quarter", "year"],
                                },
                                "dateRange": {
                                    "description": "'last quarter' | '2025-Q3' | '2025' | ['2025-07-01','2025-09-30']"
                                },
                            },
                            "required": ["dimension"],
                        },
                    },
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "member": {"type": "string", "enum": dimensions + time_dims},
                                "operator": {
                                    "type": "string",
                                    "enum": ["equals", "notEquals", "contains", "gt", "gte", "lt", "lte"],
                                },
                                "values": {"type": "array"},
                            },
                            "required": ["member", "operator", "values"],
                        },
                    },
                    "limit": {"type": "integer"},
                },
                "required": ["measures"],
            },
        },
    }


def _clean(text: str | None) -> str:
    # qwen3 can emit <think>...</think> reasoning; keep only the final answer.
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def _chat(client: OpenAI, **kwargs):
    """Call the LLM, retrying transient LM Studio load hiccups (a local model
    server can abort an engine start under memory pressure and recover on retry)."""
    last_error = None
    for attempt in range(3):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - surface after retries
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise last_error


def run_agent(question: str, max_steps: int = 5) -> dict:
    meta = get_meta()
    tool = _tool_def(meta)
    client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

    system = SYSTEM_PROMPT.format(
        measures=", ".join(m["name"] for m in meta["measures"]),
        dimensions=", ".join(d["name"] for d in meta["dimensions"]),
        time_dimensions=", ".join(t["name"] for t in meta["timeDimensions"]),
    )
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    trace: list[dict] = []

    for step in range(max_steps):
        resp = _chat(
            client,
            model=config.LLM_MODEL,
            messages=messages,
            tools=[tool],
            tool_choice="auto",
            temperature=0,
            max_tokens=MAX_TOKENS,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return {"answer": _clean(msg.content), "trace": trace, "steps": step}

        messages.append(
            {
                "role": "assistant",
                "content": _clean(msg.content),
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                args, result = {}, {"error": f"invalid tool arguments JSON: {exc}"}
            else:
                result = (
                    semantic_load(args)
                    if tc.function.name == "query_semantic_layer"
                    else {"error": f"unknown tool {tc.function.name}"}
                )
            trace.append({"tool": tc.function.name, "query": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str)[:4000],
                }
            )

    # Out of steps — ask for a final answer from the data already gathered.
    resp = _chat(
        client,
        model=config.LLM_MODEL,
        messages=messages + [{"role": "user", "content": "Give your final answer now using the data gathered."}],
        temperature=0,
        max_tokens=MAX_TOKENS,
    )
    return {"answer": _clean(resp.choices[0].message.content), "trace": trace, "steps": max_steps}
