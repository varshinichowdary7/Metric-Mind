"""Thin HTTP client for the semantic-layer REST contract (/meta, /load).

The agent talks to the semantic layer only through this boundary — never SQL.
Point SEMANTIC_API_URL at the Python layer (default) or at Cube.dev to swap.
"""

from __future__ import annotations

import httpx

from .config import SEMANTIC_API_URL


def get_meta() -> dict:
    resp = httpx.get(f"{SEMANTIC_API_URL}/meta", timeout=30)
    resp.raise_for_status()
    return resp.json()


def load(query: dict) -> dict:
    """Run a governed query. A governance rejection (HTTP 400) is returned as
    {"error": ...} so the agent can see it and correct its next call."""
    resp = httpx.post(f"{SEMANTIC_API_URL}/load", json=query, timeout=60)
    if resp.status_code == 400:
        detail = resp.json().get("detail", "rejected by semantic layer")
        return {"error": detail}
    resp.raise_for_status()
    return resp.json()
