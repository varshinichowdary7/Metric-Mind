"""
The governance guarantee, as a test.

MetricMind's promise is that a metric is defined once and returns the *same
number every time* — this is what lets Finance and Sales trust it. We test the
semantic layer directly (not the agent): the LLM's wording is non-deterministic,
but the governed number it reports must not be.
"""

from semantic.model import load

Q3_REVENUE = {
    "measures": ["sales.revenue"],
    "timeDimensions": [{"dimension": "sales.order_date", "dateRange": "2025-Q3"}],
}


def test_q3_revenue_identical_across_20_runs():
    values = {load(Q3_REVENUE)["data"][0]["sales.revenue"] for _ in range(20)}
    assert len(values) == 1, f"Q3 revenue was not deterministic: {values}"
    assert next(iter(values)) > 0


def test_margin_by_region_is_byte_identical():
    query = {
        "measures": ["sales.margin", "sales.margin_pct"],
        "dimensions": ["geography.region"],
        "timeDimensions": [{"dimension": "sales.order_date", "dateRange": "last quarter"}],
        "filters": [{"member": "geography.continent", "operator": "equals", "values": ["Europe"]}],
    }
    first = load(query)["data"]
    for _ in range(5):
        assert load(query)["data"] == first


def test_compiled_sql_uses_bound_parameters_not_string_interpolation():
    # A filter value with a quote must not break the query (proves parameterization).
    out = load(
        {
            "measures": ["sales.revenue"],
            "filters": [{"member": "geography.country", "operator": "equals", "values": ["O'Brien's Land"]}],
        }
    )
    assert "?" in out["sql"]  # placeholder, not the literal value
    assert len(out["data"]) == 1  # ran cleanly despite the quote in the value
    assert out["data"][0]["sales.revenue"] is None  # no such country -> empty aggregate
