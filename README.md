# MetricMind — Agentic Semantic BI Engine

> Ask a business question in plain English; get a governed, reproducible answer.
> The LLM **never writes SQL** — it translates the question into a structured query
> against a **semantic layer** that owns every metric definition, so Finance and
> Sales always see the exact same numbers.

MetricMind is Project 1 of the Axlero *Advanced Data Analytics* track. It puts a
local, open LLM behind a governance boundary: the agent can only call a single
tool that queries **Cube.dev**, which compiles the one true definition of every
metric (revenue, cost, **margin**) into SQL against the warehouse.

## Why this design

Giving an LLM raw `text-to-SQL` access to a warehouse ends in hallucinated joins
and revenue numbers that disagree with the finance report. MetricMind removes that
whole failure mode: the model chooses *which governed metric to ask for*, never
*how to compute it*.

## Architecture

```
 Next.js chat UI  ──HTTP/SSE──▶  FastAPI orchestrator          (api/)
 (Tremor + ECharts)              ├─ local LLM agent (LM Studio: qwen3)  ← tool calling
                                 ├─ single tool: query_semantic_layer
                                 └─ guardrails: member whitelist + row cap
                                          │  REST /meta and /load (JSON only)
                                          ▼
                                 Cube.dev semantic layer         (cube/)
                                 measures · dimensions · joins · margin
                                          │  compiled, governed SQL
                                          ▼
                                 DuckDB warehouse                (data/, dbt/)
                                 marts.fct_sales + dim_* (dbt star schema)
```

The critical boundary is the REST arrow: **the agent speaks only Cube's JSON query
API, never SQL.** Everything below that line is governed and deterministic.

## Local, zero-cost stack

Everything runs on your machine — no cloud warehouse, no paid LLM API.

| Layer      | Spec (production)        | This repo (local)                    |
|------------|--------------------------|--------------------------------------|
| Warehouse  | Snowflake / Databricks   | **DuckDB** (embedded file)           |
| Modeling   | dbt                      | **dbt-duckdb**                       |
| Semantics  | Cube Cloud / dbt SL      | **Cube.dev OSS** (Docker)            |
| LLM        | Claude API               | **LM Studio** (`qwen/qwen3.8-27b`)   |
| Agent/API  | LangChain                | FastAPI + OpenAI-compatible client   |
| UI         | Next.js + Tremor + ECharts | same                               |

The LLM is served by **LM Studio**'s OpenAI-compatible endpoint at
`http://localhost:1234/v1`, so there is **no per-query API cost**.

## Prerequisites

- Python 3.12 (`py -3.12` on Windows)
- Node 20+ (for the Next.js UI, later phase)
- Docker (for Cube.dev, later phase)
- [LM Studio](https://lmstudio.ai/) with the local server running and
  `qwen/qwen3.8-27b` loaded

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

## Repository layout

```
Metric-Mind/
├─ data/          mock data generator + DuckDB loader   (Phase 1)
├─ dbt/           staging → marts star schema           (Phase 2)
├─ cube/          Cube.dev semantic layer (margin, …)   (Phase 3)
├─ api/           FastAPI + local-LLM agent + guardrails (Phase 4–5)
├─ tests/         governance / determinism evals         (Phase 6)
├─ web/           Next.js chat UI                         (Phase 8)
└─ docker-compose.yml
```

## Build roadmap

MetricMind is built backend-first, one feature branch per phase:

1. `feat/data-warehouse` — mock data + DuckDB *(this phase)*
2. `feat/dbt-models` — dbt staging → marts star schema
3. `feat/semantic-layer` — Cube.dev cubes: `margin`, `margin_pct`, dims, joins
4. `feat/agent-orchestrator` — FastAPI `/chat` + local-LLM tool-calling agent
5. `feat/guardrails` — member whitelist + row-limit cost governance
6. `feat/determinism-eval` — "Q3 revenue 20×" reproducibility test
7. `feat/multi-step-reasoning` — ReAct drill-down (margin drop → cost type)
8. `feat/chat-ui` — Next.js + Tremor + ECharts streaming UI
9. `feat/dynamic-viz` — chart selection from Cube annotations
10. `feat/transparency` — "View SQL / View API call" panel
11. `feat/polish-docs` — Compose wiring + docs

## License

Educational project for the Axlero Solutions internship program.
