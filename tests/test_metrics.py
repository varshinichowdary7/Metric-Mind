"""Metric correctness: margin math, and the injected European Q3-2025 anomaly."""

from datetime import date

from semantic.model import load


def test_margin_equals_revenue_minus_cost():
    row = load({"measures": ["sales.revenue", "sales.cost", "sales.margin"]})["data"][0]
    assert abs(row["sales.margin"] - (row["sales.revenue"] - row["sales.cost"])) < 1e-6


def test_european_margin_is_lowest_in_q3_2025():
    rows = load(
        {
            "measures": ["sales.margin_pct"],
            "timeDimensions": [{"dimension": "sales.order_date", "granularity": "quarter"}],
            "filters": [{"member": "geography.continent", "operator": "equals", "values": ["Europe"]}],
        }
    )["data"]
    by_quarter = {r["sales.order_date"]: r["sales.margin_pct"] for r in rows}
    q1, q2, q3 = by_quarter[date(2025, 1, 1)], by_quarter[date(2025, 4, 1)], by_quarter[date(2025, 7, 1)]
    assert q3 < q2 and q3 < q1, f"expected Q3 margin% lowest in 2025, got {q1=}, {q2=}, {q3=}"


def _european_cost_by_type(date_range: str) -> dict:
    rows = load(
        {
            "measures": ["order_costs.cost_amount"],
            "dimensions": ["order_costs.cost_type"],
            "timeDimensions": [{"dimension": "order_costs.order_date", "dateRange": date_range}],
            "filters": [{"member": "geography.continent", "operator": "equals", "values": ["Europe"]}],
        }
    )["data"]
    return {r["order_costs.cost_type"]: r["order_costs.cost_amount"] for r in rows}


def test_shipping_cost_spiked_relative_to_material_in_q3():
    q2 = _european_cost_by_type("2025-Q2")
    q3 = _european_cost_by_type("2025-Q3")
    shipping_growth = q3["shipping"] / q2["shipping"]
    material_growth = q3["material"] / q2["material"]
    # The injected anomaly: shipping grew much faster than material.
    assert shipping_growth > material_growth + 0.15
