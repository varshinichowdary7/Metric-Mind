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

from fastapi import FastAPI
from pydantic import BaseModel

from .agent import run_agent
from .semantic_client import get_meta

app = FastAPI(title="MetricMind API", version="1.0.0")


class ChatRequest(BaseModel):
    question: str
    max_steps: int = 5


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict:
    return get_meta()


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    return run_agent(req.question, max_steps=req.max_steps)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", "8001")))
