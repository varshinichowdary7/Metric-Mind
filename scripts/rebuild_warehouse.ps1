<#
.SYNOPSIS
  Rebuild the DuckDB warehouse from scratch: mock data -> raw DuckDB -> dbt marts.

.DESCRIPTION
  Deterministic — the generated data is seeded, so you get the same warehouse
  (including the injected Q3-2025 European shipping spike) every time.

  Run from the repo root with the project venv active (or python on PATH):
      ./scripts/rebuild_warehouse.ps1
#>
$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repo

# Absolute path so every layer (loader, dbt, semantic layer) hits one file.
if (-not $env:DUCKDB_PATH) {
    $env:DUCKDB_PATH = Join-Path $repo "data\warehouse.duckdb"
}
Write-Host "Rebuilding warehouse at: $($env:DUCKDB_PATH)"

python data/generate_mock_data.py
python data/load_duckdb.py
dbt run  --project-dir dbt --profiles-dir dbt
dbt test --project-dir dbt --profiles-dir dbt

Write-Host "Done. Warehouse ready at $($env:DUCKDB_PATH)"
