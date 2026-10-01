# Cube.dev model (production swap)

This directory holds a [Cube.dev](https://cube.dev) semantic model that is an
alternative to the default local Python semantic layer (`semantic/`). Both expose
the **same member names** (`sales.margin`, `geography.region`,
`order_costs.cost_type`, …) and the same governed definition of every metric, so
the agent's tool schema works against either backend.

| | Default (local) | This (Cube.dev) |
|---|---|---|
| Runtime | `semantic/` Python service | Cube.dev OSS container |
| Start | `uvicorn semantic.server:app --port 4000` | `docker compose up cube` |
| Contract | `/meta`, `/load` | Cube REST `/meta`, `/load` |

## Run

```bash
docker compose up cube
```

Cube reads the models in `cube/model/` and queries `data/warehouse.duckdb`
(mounted read-only). Open the Playground at http://localhost:4000, then point the
agent at Cube by setting `SEMANTIC_API_URL` to the Cube REST API base.

## Governance

`margin` is defined once, as `{revenue} - {cost}` — in `model/cubes/sales.yml`
here, and identically in `semantic/model.py` for the local layer. Keep the two in
sync if you edit a metric definition.
