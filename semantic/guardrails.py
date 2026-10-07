"""
Cost-governance guardrails for the semantic layer.

The semantic layer already refuses unknown members (the whitelist in model.py).
These guardrails add the other half of governance: they stop the agent from
running *unbounded or expensive* queries — capping the row limit and rejecting
queries that would group by too many dimensions or pull too many measures at once.

They are enforced centrally in `model.load()`, so neither the LLM agent nor a
direct `/load` caller can bypass them. Limits are configurable via env so a
reviewer can tighten them without touching code.
"""

from __future__ import annotations

import os

DEFAULT_LIMIT = int(os.getenv("SEMANTIC_DEFAULT_LIMIT", "500"))
MAX_LIMIT = int(os.getenv("SEMANTIC_MAX_LIMIT", "5000"))
MAX_GROUPING = int(os.getenv("SEMANTIC_MAX_GROUPING", "4"))  # dimensions + granular time dims
MAX_MEASURES = int(os.getenv("SEMANTIC_MAX_MEASURES", "6"))


class GuardrailError(ValueError):
    """Raised when a query exceeds a cost-governance limit."""


def clamp_limit(limit) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


def apply(query: dict) -> dict:
    """Validate and sanitize a query. Returns a new query with a clamped limit;
    raises GuardrailError if the query is too expensive to run."""
    measures = query.get("measures") or []
    dimensions = query.get("dimensions") or []
    time_dims = query.get("timeDimensions") or []

    if len(measures) > MAX_MEASURES:
        raise GuardrailError(
            f"Too many measures requested ({len(measures)} > {MAX_MEASURES}). "
            "Ask for fewer measures per query."
        )

    grouping = len(dimensions) + sum(1 for t in time_dims if t.get("granularity"))
    if grouping > MAX_GROUPING:
        raise GuardrailError(
            f"Too many grouping dimensions ({grouping} > {MAX_GROUPING}); this would "
            "produce an unbounded cross-product. Narrow the breakdown."
        )

    return {**query, "limit": clamp_limit(query.get("limit"))}
