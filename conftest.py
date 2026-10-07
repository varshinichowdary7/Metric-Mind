"""
Pytest bootstrap for MetricMind.

Being at the repo root, this file puts the repo on sys.path (so `import semantic`
/ `import api` work) and provides a session fixture that guarantees the DuckDB
marts exist before any test runs — building them from the seeds if a fresh
checkout hasn't yet.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import duckdb
import pytest

REPO = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(REPO, "data", "warehouse.duckdb")
os.environ.setdefault("DUCKDB_PATH", DB)

REQUIRED_MARTS = {"fct_sales", "fct_order_costs", "dim_date", "dim_geography", "dim_product"}


def _marts_ready() -> bool:
    if not os.path.exists(DB):
        return False
    try:
        con = duckdb.connect(DB, read_only=True)
        have = {
            t[0]
            for t in con.execute(
                "select table_name from information_schema.tables where table_schema='marts'"
            ).fetchall()
        }
        con.close()
        return REQUIRED_MARTS <= have
    except Exception:
        return False


def _dbt_cmd() -> list[str]:
    exe = shutil.which("dbt")
    if exe:
        return [exe]
    sibling = os.path.join(os.path.dirname(sys.executable), "dbt.exe" if os.name == "nt" else "dbt")
    if os.path.exists(sibling):
        return [sibling]
    return [sys.executable, "-m", "dbt.cli.main"]


@pytest.fixture(scope="session", autouse=True)
def warehouse():
    """Build the warehouse (seeds -> DuckDB raw -> dbt marts) if it's not ready."""
    if not _marts_ready():
        env = {**os.environ, "DUCKDB_PATH": DB}
        subprocess.run([sys.executable, "data/generate_mock_data.py"], cwd=REPO, check=True)
        subprocess.run([sys.executable, "data/load_duckdb.py"], cwd=REPO, check=True, env=env)
        subprocess.run(
            _dbt_cmd() + ["run", "--project-dir", "dbt", "--profiles-dir", "dbt"],
            cwd=REPO,
            check=True,
            env=env,
        )
        assert _marts_ready(), "warehouse build did not produce the expected marts"
    yield
