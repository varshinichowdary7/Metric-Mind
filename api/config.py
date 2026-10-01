"""Runtime configuration for the MetricMind agent (from .env / environment)."""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# Local LLM served by LM Studio's OpenAI-compatible endpoint — no API cost.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "lm-studio")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")

# The governed semantic layer the agent is allowed to query.
SEMANTIC_API_URL = os.getenv("SEMANTIC_API_URL", "http://localhost:4000")
