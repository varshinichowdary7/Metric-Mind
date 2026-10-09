# MetricMind web

A Next.js chat interface for the MetricMind agent. Ask a business question in
plain English; the agent answers via the governed semantic layer and the UI shows
the answer plus a **View API call** panel with the exact governed queries it ran.

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

## Security note

`npm audit` flags Next.js server-side advisories (Image Optimizer, Server
Components/Actions, middleware/rewrites). This app uses **none** of those — it is
entirely client-rendered (`'use client'`), with no image optimization, server
actions, middleware, or rewrites — so the flagged surfaces are not reachable here.

## Roadmap

This is the chat scaffolding (Phase 8). Later phases add:
- **Phase 9** — dynamic charts (ECharts) chosen from the query's annotation types.
- **Phase 10** — the full transparency panel (compiled SQL alongside the API call).
