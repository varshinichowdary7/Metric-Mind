# MetricMind — Agentic Semantic BI Engine

> Ask a business question in plain English; get a governed, reproducible answer.
> The LLM **never writes SQL** — it translates the question into a structured query
> against a **semantic layer** that owns every metric definition, so Finance and
> Sales always see the exact same numbers.

MetricMind is Project 1 of the Axlero *Advanced Data Analytics* track. It puts a
local, open LLM behind a governance boundary: the agent can only call governed
tools that query a **semantic layer**, which compiles the one true definition of
every metric (revenue, cost, **margin**) into SQL against the warehouse.

## Why this design

Giving an LLM raw `text-to-SQL` access to a warehouse ends in hallucinated joins
and revenue numbers that disagree with the finance report. MetricMind removes that
whole failure mode: the model chooses *which governed metric to ask for*, never
*how to compute it*.

## Architecture

```
 Next.js chat UI  ─────HTTP────▶  FastAPI orchestrator          (api/)
 (ECharts + SQL view)            ├─ local LLM agent (LM Studio: qwen3)  ← tool calling
                                 └─ tools: query_semantic_layer · explain_margin_change
                                          │  REST /meta and /load (JSON only)
                                          ▼
                                 Semantic layer   (semantic/ · Cube-compatible)
                                 measures · dimensions · joins · margin
                                 guardrails: member whitelist + row/complexity cap
                                          │  compiled, governed SQL
                                          ▼
                                 DuckDB warehouse                (data/, dbt/)
                                 marts.fct_sales + dim_* (dbt star schema)
```

The critical boundary is the REST arrow: **the agent speaks only the semantic
layer's JSON query API, never SQL.** Everything below that line is governed and
deterministic. The local layer is the Python service in `semantic/`; it is
Cube-compatible, so Cube.dev is a drop-in production swap (see below).

## Local, zero-cost stack

Everything runs on your machine — no cloud warehouse, no paid LLM API.

| Layer      | Spec (production)        | This repo (local)                    |
|------------|--------------------------|--------------------------------------|
| Warehouse  | Snowflake / Databricks   | **DuckDB** (embedded file)           |
| Modeling   | dbt                      | **dbt-duckdb**                       |
| Semantics  | Cube Cloud / dbt SL      | **Python layer** (Cube OSS optional) |
| LLM        | Claude API               | **LM Studio** (`qwen/qwen3.8-27b`)   |
| Agent/API  | LangChain                | FastAPI + OpenAI-compatible client   |
| UI         | Next.js + ECharts        | same                                 |

The LLM is served by **LM Studio**'s OpenAI-compatible endpoint at
`http://localhost:1234/v1`, so there is **no per-query API cost**.

## Prerequisites

- Python 3.12 (`py -3.12` on Windows)
- Node 20+ (for the Next.js chat UI)
- [LM Studio](https://lmstudio.ai/) with the local server running and
  `qwen/qwen3.8-27b` loaded
- Docker — optional, only for the Cube.dev production swap

## Quickstart (Phase 1 — data warehouse)

```bash
# 1. create an isolated environment
py -3.12 -m venv .venv
.venv/Scripts/activate            # Windows
pip install -r requirements.txt

# 2. copy env template
cp .env.example .env

# 3. generate mock corporate data and build the raw warehouse
python data/generate_mock_data.py
python data/load_duckdb.py
```

`load_duckdb.py` prints European margin by quarter — you should see a clear dip in
**Q3 2025**, caused by a deliberately injected 22% shipping-cost spike. That is the
anomaly the agent will later explain when asked *"Why did European margins drop
last quarter?"*.

> Rebuilding later? `./scripts/rebuild_warehouse.sh` (or
> `./scripts/rebuild_warehouse.ps1` on Windows) runs the whole
> data → DuckDB → dbt sequence in one step. The data is seeded, so the warehouse
> — anomaly and all — is identical every time.

## Run the full stack

Three services, plus LM Studio for the local model:

```bash
# Terminal A — governed semantic layer (Cube-compatible /meta + /load)
python -m uvicorn semantic.server:app --port 4000

# LM Studio — load a model and start its server on :1234.
#   LLM_MODEL=qwen/qwen3.8-27b        best quality (heavier)
#   LLM_MODEL=nvidia/nemotron-3-nano  lighter + faster (set in .env)

# Terminal B — agent API
python -m uvicorn api.main:app --port 8001

# Terminal C — chat UI (http://localhost:3001)
cd web && npm install && npm run dev
```

Ask from the UI, or hit the API directly:

```bash
curl -X POST http://localhost:8001/chat -H "Content-Type: application/json" \
  -d '{"question":"What was total revenue in 2025-Q3?"}'
```

Every answer comes with a `trace` of the exact governed queries the agent ran.
The UI turns that into two things:
- a **chart** chosen automatically from the result's shape — a line for a trend,
  a bar for a breakdown, a pie for a composition, a headline number for a single
  value (the picker is deterministic Python in `api/viz.py`); and
- a **View query & SQL** panel showing the JSON the agent emitted *and* the
  governed SQL the semantic layer compiled it into — the model never writes SQL.

Notes:
- Reasoning models spend tokens thinking before the tool call — `LLM_MAX_TOKENS`
  defaults to 4096; lower it only for simple models.
- If LM Studio reports *"Engine protocol startup was aborted"* it ran out of
  memory loading the model; restart its server or switch to the lighter model.

## Run the tests

```bash
pytest           # governance, determinism, metrics, viz, transparency, Cube parity
```

The suite is the project's guarantee layer: identical queries return identical
numbers, out-of-whitelist members and over-budget queries are rejected, the
injected Q3-2025 anomaly is detectable, charts are chosen deterministically, the
displayed SQL matches what executed, and the Cube model stays name-for-name in
sync with the Python semantic layer (so the swap below stays drop-in). A fresh
checkout builds the warehouse automatically on first run (see `conftest.py`).

## Production swap to Cube.dev

The default semantic layer is the Python service (`semantic/`), which needs no
containers. To run the same metrics through **Cube.dev OSS** over the same DuckDB
marts:

```bash
docker compose up cube     # Cube Playground + REST API on :4000
```

Then point the agent at Cube by setting `SEMANTIC_API_URL` to its REST API and
restarting the agent. Nothing else changes: the cubes under `cube/model/` expose
the same member names (`sales.margin`, `geography.region`, …), and
`tests/test_cube_parity.py` fails if they ever drift.

## Repository layout

```
Metric-Mind/
├─ data/          mock data generator + DuckDB loader      (Phase 1)
├─ dbt/           staging → marts star schema              (Phase 2)
├─ semantic/      governed Python semantic layer + guardrails (Phase 3, 5)
├─ cube/          Cube.dev models — production swap        (Phase 3)
├─ api/           FastAPI agent + analysis + viz + SQL preview (Phase 4, 7, 9, 10)
├─ tests/         governance / determinism / parity evals  (Phase 6, 9–11)
├─ web/           Next.js chat UI + ECharts + transparency  (Phase 8–10)
├─ scripts/       warehouse rebuild helpers                (Phase 11)
└─ docker-compose.yml   optional Cube.dev swap
```

## Build roadmap

MetricMind was built backend-first, one feature branch per phase — all complete:

1. ✅ `feat/data-warehouse` — mock data + DuckDB
2. ✅ `feat/dbt-models` — dbt staging → marts star schema
3. ✅ `feat/semantic-layer` — governed layer: `margin`, `margin_pct`, dims, joins
4. ✅ `feat/agent-orchestrator` — FastAPI `/chat` + local-LLM tool-calling agent
5. ✅ `feat/guardrails` — member whitelist + row-limit cost governance
6. ✅ `feat/determinism-eval` — "Q3 revenue 20×" reproducibility test
7. ✅ `feat/multi-step-reasoning` — margin-change decomposition (drop → cost type)
8. ✅ `feat/chat-ui` — Next.js chat UI
9. ✅ `feat/dynamic-viz` — deterministic chart selection from the annotation (`api/viz.py`)
10. ✅ `feat/transparency` — "View query & SQL" panel (compiled SQL alongside the JSON)
11. ✅ `feat/polish-docs` — Cube swap wiring, rebuild scripts, parity test, docs

## License

Educational project for the Axlero Solutions internship program.
