#!/usr/bin/env bash
# Rebuild the DuckDB warehouse from scratch: mock data -> raw DuckDB -> dbt marts.
# Deterministic — the generated data is seeded, so you get the same warehouse
# (including the injected Q3-2025 European shipping spike) every time.
#
#   ./scripts/rebuild_warehouse.sh
#
# Run from the repo root with the project venv active (or on PATH).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# Absolute path so every layer (loader, dbt, semantic layer) hits one file.
export DUCKDB_PATH="${DUCKDB_PATH:-$REPO/data/warehouse.duckdb}"
echo "Rebuilding warehouse at: $DUCKDB_PATH"

python data/generate_mock_data.py
python data/load_duckdb.py
dbt run  --project-dir dbt --profiles-dir dbt
dbt test --project-dir dbt --profiles-dir dbt

echo "Done. Warehouse ready at $DUCKDB_PATH"
