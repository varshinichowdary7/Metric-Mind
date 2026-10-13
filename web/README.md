# MetricMind web

A Next.js chat interface for the MetricMind agent. Ask a business question in
plain English; the agent answers via the governed semantic layer and the UI shows
the answer, an automatically chosen **chart** of the result, and a
**View query & SQL** panel with the exact JSON query the agent sent *and* the
governed SQL it compiled to.

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

## Transparency panel (Phase 10)

Every answer carries a **View query & SQL** panel. For each governed call it
shows three stacked sections:

1. **Semantic query** — the JSON the agent emitted (measures / dimensions /
   filters). The model only ever names whitelisted members; it never writes SQL.
2. **Compiled SQL** — the SQL the semantic layer compiled that query into. The
   agent runs it parameterized (`?` placeholders bound separately); the panel
   shows a readable, copy-pasteable preview with values inlined, built in
   `api/transparency.py` and proven faithful to the parameterized result in
   `tests/test_transparency.py`.
3. **Result** — the rows returned.

This closes the loop on the core claim: the model chooses *which* governed metric
to ask for, and you can see exactly *how* the semantic layer computed it.

## Security note

`npm audit` flags Next.js server-side advisories (Image Optimizer, Server
Components/Actions, middleware/rewrites). This app uses **none** of those — it is
entirely client-rendered (`'use client'`), with no image optimization, server
actions, middleware, or rewrites — so the flagged surfaces are not reachable here.

## Roadmap

Phases 8 (chat), 9 (dynamic charts), and 10 (transparency panel) are done.
