"""
MetricMind agent API (FastAPI).

Endpoints:
    GET  /health  — liveness
    GET  /meta    — proxy the semantic layer's catalog (what can be asked)
    POST /chat    — ask a business question; returns the answer + the governed
                    query trace ("View API call" transparency)

Run (with the semantic layer already up on :4000):
    uvicorn api.main:app --port 8001
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openai import APIConnectionError, OpenAIError

from .agent import llm_status, run_agent
from .semantic_client import get_meta

app = FastAPI(title="MetricMind API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    question: str
    max_steps: int = 5


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/llm/status")
def local_llm_status() -> dict:
    """Check LM Studio connectivity and configured model availability."""
    return llm_status()


@app.get("/meta")
def meta() -> dict:
    return get_meta()


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    try:
        return run_agent(req.question, max_steps=req.max_steps)
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not connect to LM Studio at the configured LLM_BASE_URL. "
                "Start its local server, then check GET /llm/status."
            ),
        ) from exc
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "LM Studio returned an LLM API error. Check that the configured "
                "LLM_MODEL is loaded and matches an ID from GET /llm/status."
            ),
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", "8001")))
