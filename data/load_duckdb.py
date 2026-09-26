"""
Load the mock CSV seeds into a DuckDB warehouse under the `raw` schema.

This is the raw (landing) layer of the MetricMind warehouse. dbt then shapes it
into a `marts` star schema (fct_sales + dim_* tables) that the Cube.dev semantic
layer reads.

Usage:
    python data/load_duckdb.py

Env:
    DUCKDB_PATH   path to the DuckDB file (default: ./data/warehouse.duckdb)
"""

from __future__ import annotations

import glob
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
SEEDS_DIR = os.path.join(HERE, "seeds")
DEFAULT_DB = os.path.join(HERE, "warehouse.duckdb")

# Load .env if python-dotenv is available; otherwise fall back to os.environ.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(REPO_ROOT, ".env"))
except Exception:
    pass


def db_path() -> str:
    raw = os.getenv("DUCKDB_PATH", DEFAULT_DB)
    return raw if os.path.isabs(raw) else os.path.normpath(os.path.join(REPO_ROOT, raw))


def main() -> None:
    seeds = sorted(glob.glob(os.path.join(SEEDS_DIR, "raw_*.csv")))
    if not seeds:
        raise SystemExit(
            "No seed CSVs found. Run `python data/generate_mock_data.py` first."
        )

    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = duckdb.connect(path)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")

    for csv_path in seeds:
        table = os.path.splitext(os.path.basename(csv_path))[0]  # raw_orders, ...
        con.execute(
            f"CREATE OR REPLACE TABLE raw.{table} AS "
            f"SELECT * FROM read_csv_auto(?, header=true, sample_size=-1);",
            [csv_path],
        )
        (rows,) = con.execute(f"SELECT count(*) FROM raw.{table};").fetchone()
        print(f"  loaded raw.{table:<16} {rows:>7,} rows")

    # Sanity check: European margin by quarter should show a dip in Q3 2025.
    print("\nEuropean margin by quarter (sanity check - expect a Q3 2025 dip):")
    result = con.execute(
        """
        WITH order_cost AS (
            SELECT order_id, SUM(cost_amount) AS cost
            FROM raw.raw_costs GROUP BY order_id
        )
        SELECT
            date_trunc('quarter', o.order_date)::DATE AS quarter,
            ROUND(SUM(o.revenue), 0)                  AS revenue,
            ROUND(SUM(oc.cost), 0)                    AS cost,
            ROUND(SUM(o.revenue) - SUM(oc.cost), 0)   AS margin,
            ROUND(100 * (SUM(o.revenue) - SUM(oc.cost)) / SUM(o.revenue), 1) AS margin_pct
        FROM raw.raw_orders o
        JOIN order_cost oc USING (order_id)
        JOIN raw.raw_geography g USING (geo_id)
        WHERE g.continent = 'Europe'
        GROUP BY 1 ORDER BY 1;
        """
    ).fetchall()
    print(f"  {'quarter':<12}{'revenue':>12}{'cost':>12}{'margin':>12}{'margin_%':>10}")
    for q, rev, cost, margin, mpct in result:
        print(f"  {str(q):<12}{rev:>12,.0f}{cost:>12,.0f}{margin:>12,.0f}{mpct:>10}")

    con.close()
    print(f"\nWarehouse ready at {path}")


if __name__ == "__main__":
    main()
