# MetricMind web

A Next.js chat interface for the MetricMind agent. Ask a business question in
plain English; the agent answers via the governed semantic layer and the UI shows
the answer, an automatically chosen **chart** of the result, and a **View API
call** panel with the exact governed queries it ran.

## Run

```bash
cd web
npm install
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_URL at the agent API
npm run dev                         # http://localhost:3001
```

Requires the backend running first:
- semantic layer — `uvicorn semantic.server:app --port 4000`
- agent API — `uvicorn api.main:app --port 8001`
- LM Studio serving a model on :1234

## Charts (Phase 9)

The UI never decides which chart to draw. The agent attaches a renderer-agnostic
`viz` spec to each governed query in the trace, chosen in Python from the
result's **annotation** (`api/viz.py`, unit-tested in `tests/test_viz.py`). The
rules follow the data's shape:

| Result shape                                   | Chart |
|------------------------------------------------|-------|
| one aggregate value, no breakdown              | KPI number |
| grouped by a time granularity                  | line  |
| one categorical breakdown                      | bar   |
| small, non-negative, additive breakdown        | pie   |
| anything else                                  | (table only) |

A percentage measure (e.g. `margin %`) or a negative value never becomes a pie —
you cannot sum percentages into a whole, and a pie slice cannot be negative.
`app/chart.js` is a thin [ECharts](https://echarts.apache.org/) renderer: it maps
the spec onto a chart and formats values by the measure's type (currency /
percent / number). ECharts is loaded with a dynamic `import()`, so it stays out
of the initial bundle and off the server render.

## Security note

`npm audit` flags Next.js server-side advisories (Image Optimizer, Server
Components/Actions, middleware/rewrites). This app uses **none** of those — it is
entirely client-rendered (`'use client'`), with no image optimization, server
actions, middleware, or rewrites — so the flagged surfaces are not reachable here.

## Roadmap

Phases 8 (chat) and 9 (dynamic charts) are done. Next:
- **Phase 10** — the full transparency panel (compiled SQL alongside the API call).
