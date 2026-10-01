"""
MetricMind semantic layer — the governance core.

Every business metric (revenue, cost, margin, ...) is defined exactly once here,
as code. The LLM agent never writes SQL; it emits a structured JSON query that
names *whitelisted* measures and dimensions, and this module compiles that query
into governed SQL over the DuckDB marts. That is what makes the numbers
reproducible and keeps Finance and Sales on the same definition of "margin".

The query shape is Cube.dev-compatible (measures / dimensions / timeDimensions /
filters / limit), so the equivalent Cube model under cube/ is a drop-in swap for
production. Governance guarantees enforced here:

  * Whitelist    — any member not defined below is rejected (no rogue columns).
  * No raw SQL   — the agent supplies only member *names*; their SQL lives here.
  * Injection    — all user-supplied filter/date values are passed as bound
                   parameters, never string-formatted into SQL.
  * Determinism  — a stable ORDER BY means identical input -> identical output.
  * Cost cap     — the row limit is clamped (see MAX_LIMIT).
"""

from __future__ import annotations

import os
import re
from datetime import date

import duckdb

MARTS = "marts"
DEFAULT_LIMIT = 500
MAX_LIMIT = 5000

# ── Join graph (from the base fact, aliased `f`) ─────────────────────────────
# alias -> (marts table, ON condition)
JOINS = {
    "date":      ("dim_date",      "f.date_id = date.date_id"),
    "geography": ("dim_geography", "f.geo_id = geography.geo_id"),
    "product":   ("dim_product",   "f.product_id = product.product_id"),
}
# Deterministic join order.
JOIN_ORDER = ["date", "geography", "product"]

FACTS = {
    "sales":       "fct_sales",
    "order_costs": "fct_order_costs",
}

# ── Measures: the one definition of each metric ──────────────────────────────
# name -> dict(fact, sql aggregate, type, title)
MEASURES: dict[str, dict] = {
    "sales.revenue":       dict(fact="sales", sql="SUM(f.revenue)",        type="currency", title="Revenue"),
    "sales.cost":          dict(fact="sales", sql="SUM(f.cost)",           type="currency", title="Cost"),
    # The single, shared definition of margin — nobody downstream can redefine it.
    "sales.margin":        dict(fact="sales", sql="SUM(f.revenue) - SUM(f.cost)", type="currency", title="Margin"),
    "sales.margin_pct":    dict(fact="sales", sql="100.0 * (SUM(f.revenue) - SUM(f.cost)) / NULLIF(SUM(f.revenue), 0)", type="percent", title="Margin %"),
    "sales.material_cost": dict(fact="sales", sql="SUM(f.material_cost)",  type="currency", title="Material cost"),
    "sales.shipping_cost": dict(fact="sales", sql="SUM(f.shipping_cost)",  type="currency", title="Shipping cost"),
    "sales.order_count":   dict(fact="sales", sql="COUNT(*)",              type="number",   title="Orders"),
    # Cost broken out by type lives at a finer grain (fct_order_costs).
    "order_costs.cost_amount": dict(fact="order_costs", sql="SUM(f.cost_amount)", type="currency", title="Cost amount"),
}

# ── Dimensions ───────────────────────────────────────────────────────────────
# name -> dict(sql, join(optional), type, fact(optional restriction))
DIMENSIONS: dict[str, dict] = {
    "geography.country":     dict(sql="geography.country",   join="geography", type="string"),
    "geography.region":      dict(sql="geography.region",    join="geography", type="string"),
    "geography.continent":   dict(sql="geography.continent", join="geography", type="string"),
    "product.product":       dict(sql="product.product",     join="product",   type="string"),
    "product.category":      dict(sql="product.category",    join="product",   type="string"),
    "date.quarter_label":    dict(sql="date.quarter_label",  join="date",      type="string"),
    "date.month":            dict(sql="date.month",          join="date",      type="number"),
    "date.year":             dict(sql="date.year",           join="date",      type="number"),
    # cost_type only exists on the order_costs fact itself.
    "order_costs.cost_type": dict(sql="f.cost_type",         type="string",    fact="order_costs"),
}

# ── Time dimensions (one per fact; both resolve to dim_date.date) ─────────────
TIME_DIMENSIONS: dict[str, dict] = {
    "sales.order_date":       dict(fact="sales",       sql="date.date", join="date", type="time"),
    "order_costs.order_date": dict(fact="order_costs", sql="date.date", join="date", type="time"),
}

VALID_GRANULARITIES = {"day", "week", "month", "quarter", "year"}
FILTER_OPERATORS = {"equals", "notEquals", "contains", "set", "notSet", "gt", "gte", "lt", "lte"}


# ── Catalog for the agent ────────────────────────────────────────────────────
def meta() -> dict:
    """What the LLM is allowed to ask for. Fed into the agent's tool schema."""
    return {
        "measures": [
            {"name": n, "type": d["type"], "title": d["title"], "fact": d["fact"]}
            for n, d in MEASURES.items()
        ],
        "dimensions": [{"name": n, "type": d["type"]} for n, d in DIMENSIONS.items()],
        "timeDimensions": [{"name": n, "type": "time"} for n in TIME_DIMENSIONS],
    }


# ── DB access ────────────────────────────────────────────────────────────────
def db_path() -> str:
    p = os.getenv("DUCKDB_PATH", "data/warehouse.duckdb")
    return p if os.path.isabs(p) else os.path.abspath(p)


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(db_path(), read_only=read_only)


# ── Query compilation ────────────────────────────────────────────────────────
class SemanticError(ValueError):
    """Raised when a query references unknown members or is otherwise invalid."""


def _resolve_fact(measures, dimensions, time_dims) -> str:
    facts = set()
    for m in measures:
        facts.add(MEASURES[m]["fact"])
    for t in time_dims:
        facts.add(TIME_DIMENSIONS[t["dimension"]]["fact"])
    for d in dimensions:
        if "fact" in DIMENSIONS[d]:
            facts.add(DIMENSIONS[d]["fact"])
    if len(facts) > 1:
        raise SemanticError(
            f"Query mixes measures/dimensions from different facts ({sorted(facts)}). "
            "Margin lives on `sales`; cost-by-type lives on `order_costs` — query them separately."
        )
    return facts.pop() if facts else "sales"


def _date_range_condition(dr) -> tuple[str, list]:
    """Return (sql_fragment on date.date, bound params)."""
    if isinstance(dr, (list, tuple)) and len(dr) == 2:
        return "date.date BETWEEN ? AND ?", [str(dr[0]), str(dr[1])]
    if isinstance(dr, str):
        s = dr.strip().lower()
        m = re.match(r"^(\d{4})-q([1-4])$", s)
        if m:
            y, q = int(m.group(1)), int(m.group(2))
            start = date(y, 3 * (q - 1) + 1, 1).isoformat()
            return "date.date >= ? AND date.date < (?::DATE + INTERVAL 3 MONTH)", [start, start]
        if s in ("last quarter", "this quarter", "latest quarter"):
            q = "(SELECT date_trunc('quarter', max(date)) FROM {m}.dim_date)".format(m=MARTS)
            return f"date.date >= {q} AND date.date < ({q} + INTERVAL 3 MONTH)", []
        mm = re.match(r"^last (\d+) quarters?$", s)
        if mm:
            months = 3 * (int(mm.group(1)) - 1)  # int from regex -> safe to inline
            q = "(SELECT date_trunc('quarter', max(date)) FROM {m}.dim_date)".format(m=MARTS)
            return f"date.date >= ({q} - INTERVAL {months} MONTH) AND date.date < ({q} + INTERVAL 3 MONTH)", []
        if re.match(r"^\d{4}$", s):
            y = int(s)
            return "date.date >= ? AND date.date < ?", [f"{y}-01-01", f"{y + 1}-01-01"]
    raise SemanticError(f"Unsupported dateRange: {dr!r}")


def _filter_condition(f) -> tuple[str, list]:
    member = f.get("member")
    op = f.get("operator", "equals")
    values = f.get("values", [])
    if member not in DIMENSIONS and member not in TIME_DIMENSIONS:
        raise SemanticError(f"Unknown filter member: {member!r}")
    if op not in FILTER_OPERATORS:
        raise SemanticError(f"Unsupported filter operator: {op!r}")
    col = (DIMENSIONS.get(member) or TIME_DIMENSIONS.get(member))["sql"]
    if op in ("set", "notSet"):
        return f"{col} IS {'NOT NULL' if op == 'set' else 'NULL'}", []
    if not values:
        raise SemanticError(f"Filter on {member!r} with operator {op!r} needs values.")
    if op == "equals":
        ph = ", ".join("?" for _ in values)
        return f"{col} IN ({ph})", list(values)
    if op == "notEquals":
        ph = ", ".join("?" for _ in values)
        return f"{col} NOT IN ({ph})", list(values)
    if op == "contains":
        parts = " OR ".join(f"{col} ILIKE ?" for _ in values)
        return f"({parts})", [f"%{v}%" for v in values]
    cmp = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
    return f"{col} {cmp} ?", [values[0]]


def build_sql(query: dict) -> tuple[str, list, dict]:
    """Compile a semantic query into (sql, params, annotation). Validates members."""
    measures = list(query.get("measures") or [])
    dimensions = list(query.get("dimensions") or [])
    time_dims = list(query.get("timeDimensions") or [])
    filters = list(query.get("filters") or [])

    # Whitelist every requested member.
    for m in measures:
        if m not in MEASURES:
            raise SemanticError(f"Unknown measure: {m!r}")
    for d in dimensions:
        if d not in DIMENSIONS:
            raise SemanticError(f"Unknown dimension: {d!r}")
    for t in time_dims:
        if t.get("dimension") not in TIME_DIMENSIONS:
            raise SemanticError(f"Unknown time dimension: {t.get('dimension')!r}")
        g = t.get("granularity")
        if g is not None and g not in VALID_GRANULARITIES:
            raise SemanticError(f"Unsupported granularity: {g!r}")

    if not measures and not dimensions and not time_dims:
        raise SemanticError("Query must request at least one measure or dimension.")

    fact = _resolve_fact(measures, dimensions, time_dims)
    needed_joins: set[str] = set()
    select_cols: list[str] = []
    group_positions: list[int] = []
    params: list = []
    annotation: dict = {"measures": {}, "dimensions": {}, "timeDimensions": {}}

    pos = 0
    # Dimensions first.
    for d in dimensions:
        spec = DIMENSIONS[d]
        if spec.get("join"):
            needed_joins.add(spec["join"])
        pos += 1
        select_cols.append(f'{spec["sql"]} AS "{d}"')
        group_positions.append(pos)
        annotation["dimensions"][d] = {"type": spec["type"]}

    # Time dimensions. A granularity turns the time dimension into a grouping
    # column; without one it is filter-only (its dateRange is applied in WHERE),
    # so e.g. "Q3 revenue" returns a single total rather than one row per day.
    for t in time_dims:
        name = t["dimension"]
        spec = TIME_DIMENSIONS[name]
        needed_joins.add(spec["join"])
        gran = t.get("granularity")
        annotation["timeDimensions"][name] = {"type": "time", "granularity": gran}
        if gran:
            pos += 1
            select_cols.append(f"date_trunc('{gran}', {spec['sql']})::DATE AS \"{name}\"")
            group_positions.append(pos)

    # Measures last.
    for m in measures:
        spec = MEASURES[m]
        pos += 1
        select_cols.append(f'{spec["sql"]} AS "{m}"')
        annotation["measures"][m] = {"type": spec["type"], "title": spec["title"]}

    # WHERE: filters + time ranges.
    where: list[str] = []
    for f in filters:
        member = f.get("member")
        spec = DIMENSIONS.get(member) or TIME_DIMENSIONS.get(member)
        if spec and spec.get("join"):
            needed_joins.add(spec["join"])
        frag, p = _filter_condition(f)
        where.append(frag)
        params.extend(p)
    for t in time_dims:
        dr = t.get("dateRange")
        if dr is not None:
            frag, p = _date_range_condition(dr)
            where.append(frag)
            params.extend(p)

    # Assemble.
    from_clause = f"{MARTS}.{FACTS[fact]} f"
    for alias in JOIN_ORDER:
        if alias in needed_joins:
            table, on = JOINS[alias]
            from_clause += f"\n  JOIN {MARTS}.{table} {alias} ON {on}"

    sql = "SELECT\n  " + ",\n  ".join(select_cols) + f"\nFROM {from_clause}"
    if where:
        sql += "\nWHERE " + "\n  AND ".join(where)
    if group_positions:
        cols = ", ".join(str(i) for i in group_positions)
        sql += f"\nGROUP BY {cols}\nORDER BY {cols}"  # stable order -> deterministic

    limit = query.get("limit")
    limit = DEFAULT_LIMIT if limit is None else min(int(limit), MAX_LIMIT)
    sql += f"\nLIMIT {limit}"

    return sql, params, annotation


def load(query: dict, con: duckdb.DuckDBPyConnection | None = None) -> dict:
    """Compile + run a semantic query. Returns Cube-style {data, annotation, sql}."""
    sql, params, annotation = build_sql(query)
    own = con is None
    con = con or connect(read_only=True)
    try:
        cur = con.execute(sql, params)
        columns = [c[0] for c in cur.description]
        rows = [dict(zip(columns, r)) for r in cur.fetchall()]
    finally:
        if own:
            con.close()
    return {"data": rows, "annotation": annotation, "sql": sql, "params": params}
