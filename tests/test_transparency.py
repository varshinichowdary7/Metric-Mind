"""
Transparency: the "compiled SQL" preview (Phase 10).

`inline_sql` renders the semantic layer's parameterized SQL into a readable,
copy-pasteable form. These tests pin the literal formatting (so display is
deterministic) and prove the preview is *faithful*: the inlined SQL, run against
the warehouse, returns exactly what the parameterized query returns — the UI
isn't showing something different from what executed.
"""

from datetime import date

from api.transparency import inline_sql
from semantic.model import build_sql, connect


def test_string_param_is_quoted():
    assert inline_sql("WHERE c = ?", ["Europe"]) == "WHERE c = 'Europe'"


def test_numbers_are_not_quoted():
    assert inline_sql("LIMIT ?", [500]) == "LIMIT 500"


def test_single_quotes_are_escaped():
    assert inline_sql("WHERE c = ?", ["O'Brien"]) == "WHERE c = 'O''Brien'"


def test_none_becomes_null():
    assert inline_sql("WHERE x = ?", [None]) == "WHERE x = NULL"


def test_date_is_quoted_iso():
    assert inline_sql("d >= ?", [date(2025, 7, 1)]) == "d >= '2025-07-01'"


def test_multiple_placeholders_fill_in_order():
    out = inline_sql("? AND ? AND ?", ["a", 2, "c"])
    assert out == "'a' AND 2 AND 'c'"


def test_extra_placeholders_are_left_untouched():
    # Fewer params than ? -> remaining placeholders stay literal.
    assert inline_sql("? ?", ["a"]) == "'a' ?"


def test_no_params_returns_sql_unchanged():
    assert inline_sql("SELECT 1", []) == "SELECT 1"


def test_preview_has_no_remaining_placeholders_for_real_query():
    sql, params, _ = build_sql(
        {
            "measures": ["sales.revenue"],
            "filters": [{"member": "geography.continent", "operator": "equals", "values": ["Europe"]}],
            "timeDimensions": [{"dimension": "sales.order_date", "dateRange": "2025-Q3"}],
        }
    )
    preview = inline_sql(sql, params)
    assert "?" not in preview
    assert "'Europe'" in preview


def test_inlined_sql_matches_parameterized_result():
    # The preview must be faithful: running the inlined SQL gives the same rows
    # as executing the parameterized form the agent actually ran.
    query = {
        "measures": ["order_costs.cost_amount"],
        "dimensions": ["order_costs.cost_type"],
        "filters": [{"member": "geography.continent", "operator": "equals", "values": ["Europe"]}],
        "timeDimensions": [{"dimension": "order_costs.order_date", "dateRange": "2025-Q3"}],
    }
    sql, params, _ = build_sql(query)
    preview = inline_sql(sql, params)

    con = connect(read_only=True)
    try:
        parameterized = con.execute(sql, params).fetchall()
        inlined = con.execute(preview).fetchall()
    finally:
        con.close()
    assert inlined == parameterized
    assert len(inlined) > 0
