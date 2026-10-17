# MetricMind

MetricMind is a local, governed business intelligence assistant. Ask a question in plain English and get a reproducible answer, a chart, the semantic query, and the SQL compiled by the governed semantic layer.

The language model does not write SQL. It selects from approved metrics and dimensions; the semantic layer validates the request and compiles the query against the local DuckDB warehouse.

## How it works

```text
Browser (Next.js, port 3001)
        |
        v
FastAPI agent (port 8001) ------> LM Studio OpenAI-compatible API (port 1234)
        |
        v
Semantic service (port 4000)
        |
        v
DuckDB warehouse (data/warehouse.duckdb)
```

The agent has governed tools for querying semantic metrics and explaining margin changes. Every semantic query is checked against the catalog and query guardrails before execution. The browser shows the result, a chart recommendation, and a trace of the semantic request and compiled SQL.

## Features

- Local inference through LM Studio; no hosted model API key is required.
- A governed semantic layer with whitelisted measures and dimensions, query limits, and deterministic metric definitions.
- DuckDB storage and dbt transformations for the sample sales warehouse.
- Multi-step analysis for margin changes.
- Dynamic charts and a query/SQL transparency panel.
- An optional Cube.dev semantic-layer deployment with a parity check against the Python semantic layer.

## Requirements

- Windows, macOS, or Linux.
- Python 3.12 recommended. Install a Python version supported by the packages in `requirements.txt`.
- Node.js 20 or later and npm.
- LM Studio with a chat model loaded and its local server enabled.
- Docker only if you want to run the optional Cube.dev service.

The example configuration uses Gemma 4 12B QAT. On a machine with 16 GB RAM and integrated graphics, use a 4,096-token context, CPU placement, and a single parallel request to reduce KV-cache memory use. Lower the context further if model loading still runs out of memory.

## Setup

Run commands below from the repository root unless noted otherwise.

### 1. Get the project and create a Python environment

```powershell
git clone https://github.com/varshinichowdary7/Metric-Mind.git
cd Metric-Mind
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal and activate again. On macOS/Linux, create and activate the environment with:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a local `.env` from the template:

```powershell
Copy-Item .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

The default settings use LM Studio at `http://localhost:1234/v1`, the semantic service at `http://localhost:4000`, and the warehouse at `data/warehouse.duckdb`. `.env` is local and ignored by Git. Change `LLM_MODEL` to the model ID returned by LM Studio if your model uses a different ID. Restart the API after changing `.env`.

Important settings:

| Variable | Purpose | Example |
| --- | --- | --- |
| `LLM_BASE_URL` | LM Studio OpenAI-compatible API URL | `http://localhost:1234/v1` |
| `LLM_API_KEY` | Placeholder required by the OpenAI SDK; LM Studio local server usually ignores it | `lm-studio` |
| `LLM_MODEL` | Exact model ID served by LM Studio | `google/gemma-4-12b-qat` |
| `LLM_MAX_TOKENS` | Maximum response tokens per model call | `1024` |
| `SEMANTIC_API_URL` | Semantic service URL used by the agent | `http://localhost:4000` |
| `DUCKDB_PATH` | Local warehouse file | `./data/warehouse.duckdb` |
| `NEXT_PUBLIC_API_URL` | API URL used by the browser | `http://localhost:8001` |

### 3. Prepare the sample warehouse

The repository includes sample data seeds. If the warehouse has not been built yet, generate and load it:

```powershell
python data/generate_mock_data.py
python data/load_duckdb.py
```

For a complete rebuild including dbt models and dbt checks, run one of:

```powershell
.\scripts\rebuild_warehouse.ps1
```

```bash
./scripts/rebuild_warehouse.sh
```

The seeded data is repeatable and includes an injected European shipping-cost increase in Q3 2025 for margin-analysis examples.

### 4. Load Gemma and start the LM Studio server

In LM Studio, download **Gemma 4 12B QAT** (`google/gemma-4-12b-qat`). Load it with a context length of 4,096. On a RAM-limited machine, disable GPU offload and set parallel requests to 1. With the LM Studio CLI installed, the equivalent commands are:

```powershell
lms load google/gemma-4-12b-qat --context-length 4096 --gpu off --parallel 1
lms server start --port 1234 --bind 127.0.0.1
```

You can also start the local server from LM Studio's Developer/Local Server panel. Confirm that the configured ID is served:

```powershell
Invoke-RestMethod http://localhost:1234/v1/models
```

Use the exact model `id` shown in the response as `LLM_MODEL`. If loading reports `failed to allocate buffer for kv cache`, lower the model context length (for example, to 2,048), close other memory-heavy applications, and retry. The KV cache grows with context length.

### 5. Start the application services

Keep each service running in its own terminal. Make sure the Python virtual environment is active in both Python terminals.

**Terminal A — semantic service** (repository root):

```powershell
python -m uvicorn semantic.server:app --host 127.0.0.1 --port 4000
```

**Terminal B — MetricMind API** (repository root):

```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

**Terminal C — web UI:**

```powershell
cd web
npm ci
npm run dev
```

`npm ci` is needed only for the first setup or after dependency changes. Open [http://localhost:3001](http://localhost:3001).

On macOS/Linux, the service commands are the same except activate `.venv` with `source .venv/bin/activate` and enter the web directory with `cd web`.

### 6. Check the services

- Web app: `http://localhost:3001`
- API docs: `http://localhost:8001/docs`
- API liveness: `http://localhost:8001/health`
- LM Studio status and model match: `http://localhost:8001/llm/status`
- Semantic catalog: `http://localhost:4000/meta`

The `/llm/status` response includes `connected`, `configured_model`, `model_available`, and `available_models`. If the model is not available, load it in LM Studio, set `LLM_MODEL` to the listed ID, and restart the API.

You can also ask a question directly:

```powershell
$body = @{ question = 'What was total revenue in 2025-Q3?' } | ConvertTo-Json
Invoke-RestMethod http://localhost:8001/chat -Method Post -ContentType 'application/json' -Body $body
```

Equivalent curl request:

```bash
curl -X POST http://localhost:8001/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"What was total revenue in 2025-Q3?"}'
```

## API endpoints

| Method and path | Description |
| --- | --- |
| `GET /health` | API liveness check |
| `GET /llm/status` | LM Studio connection and configured model check |
| `GET /meta` | Semantic catalog of available measures and dimensions |
| `POST /chat` | Ask a business question; returns an answer and governed query trace |

The semantic service exposes `GET /health`, `GET /meta`, and `POST /load`.

## Example questions

- What was total revenue in 2025-Q3?
- Show margin by region for Europe last quarter.
- Why did European margins drop last quarter?
- Break down costs by cost type for 2025-Q3.

The sample data covers 2024-01 through 2025-09. The model selects metrics and dimensions, and MetricMind obtains numbers only from semantic query results.

## Troubleshooting

### LM Studio is not reachable

Confirm that the local server is running on port 1234 and `LLM_BASE_URL` points to its `/v1` endpoint. Check `http://localhost:1234/v1/models`, then check `http://localhost:8001/llm/status`.

### Configured model is not available

The value of `LLM_MODEL` must match an ID returned by LM Studio. Update `.env` and restart the API after loading the model.

### KV cache allocation failure

The KV cache depends on the context length and available memory. Reduce context length to 2,048 or lower, set GPU offload to off on machines without dedicated VRAM, use one parallel request, and close other memory-heavy applications. A smaller Gemma variant may be needed on machines with less available memory.

### Port is already in use

Stop the process already bound to the port, or change the corresponding service port and update the matching URL in `.env`. `SEMANTIC_API_URL` must match the port used by the semantic service.

### The UI cannot reach the API

Confirm the API is running on port 8001 and `NEXT_PUBLIC_API_URL` in `web/.env.local` or the environment points to it. Restart the Next.js dev server after changing its environment.

## Run the checks

Install the project dependencies, activate the Python environment, and run:

```powershell
pytest
```

The suite covers semantic governance, deterministic metrics, margin analysis, chart recommendations, SQL transparency, and parity between the Python semantic model and Cube models.

## Optional: run Cube.dev instead of the Python semantic service

The normal local setup uses the Python semantic service and does not require Docker. Cube.dev is an optional production-style swap. Start it from the repository root:

```bash
docker compose up cube
```

Cube uses port 4000 by default, so stop the Python semantic service first. Set `SEMANTIC_API_URL` in `.env` to Cube's REST API URL (`http://localhost:4000/cubejs-api/v1`) and restart the agent API. The Cube models in `cube/model/` follow the same member names as the Python semantic layer. `tests/test_cube_parity.py` checks that the catalogs remain aligned.

## Repository layout

```text
api/       FastAPI agent, LM Studio client, analysis, charts, SQL preview
cube/      Optional Cube.dev model definitions
data/      Sample data seeds, generator, and DuckDB loader
dbt/       Staging and marts transformations
semantic/  Governed semantic catalog, query compiler, and REST service
scripts/   Warehouse rebuild scripts
tests/     Governance, determinism, visualization, and parity checks
web/       Next.js chat interface
```

## License

Educational project for the Axlero Solutions internship program.
