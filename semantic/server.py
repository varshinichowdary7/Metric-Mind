"""
MetricMind semantic-layer REST service (Cube.dev-compatible contract).

Endpoints:
    GET  /meta    — the measures/dimensions the agent may query
    POST /load    — run a governed query, returns {data, annotation, sql}
    GET  /health  — liveness

This is the governance boundary: the agent speaks only this JSON API, never SQL.
Run it with:
    uvicorn semantic.server:app --port 4000
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from .model import GuardrailError, SemanticError, load, meta

app = FastAPI(title="MetricMind Semantic Layer", version="1.0.0")


class TimeDimension(BaseModel):
    dimension: str
    granularity: str | None = None
    dateRange: object | None = None


class Filter(BaseModel):
    member: str
    operator: str = "equals"
    values: list[object] = Field(default_factory=list)


class Query(BaseModel):
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    timeDimensions: list[TimeDimension] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    limit: int | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/meta")
def get_meta() -> dict:
    return meta()


@app.post("/load")
def post_load(query: Query) -> dict:
    try:
        return load(query.model_dump())
    except (SemanticError, GuardrailError) as exc:
        # Governance rejection — unknown member, fact mix, or an over-budget query.
        raise HTTPException(status_code=400, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("SEMANTIC_PORT", "4000")))
