"""
Chart-selection determinism (Phase 9).

`recommend_chart` turns a semantic-layer annotation into a chart spec. It is a
pure function, so these tests need no warehouse — they assert that each result
*shape* maps to the expected chart, that the choice is stable, and that it only
ever names members the annotation exposes.
"""

from api.viz import recommend_chart


def _ann(measures=None, dimensions=None, time_dimensions=None) -> dict:
    """Build an annotation like semantic.model.build_sql emits."""
    return {
        "measures": measures or {},
        "dimensions": dimensions or {},
        "timeDimensions": time_dimensions or {},
    }


def test_single_aggregate_is_a_kpi():
    ann = _ann(measures={"sales.revenue": {"type": "currency", "title": "Revenue"}})
    spec = recommend_chart(ann, [{"sales.revenue": 1000}])
    assert spec["chart"] == "kpi"
    assert spec["series"] == ["sales.revenue"]


def test_time_grouping_is_a_line():
    ann = _ann(
        measures={"sales.margin_pct": {"type": "percent", "title": "Margin %"}},
        time_dimensions={"sales.order_date": {"type": "time", "granularity": "quarter"}},
    )
    data = [{"sales.order_date": "2025-01-01", "sales.margin_pct": 30.0}]
    spec = recommend_chart(ann, data)
    assert spec["chart"] == "line"
    assert spec["x"] == "sales.order_date"
    assert spec["xType"] == "time"
    assert spec["series"] == ["sales.margin_pct"]


def test_filter_only_time_dimension_is_not_an_axis():
    # A time dimension WITHOUT a granularity is just a dateRange filter, so the
    # result is a single value -> KPI, not a line.
    ann = _ann(
        measures={"sales.revenue": {"type": "currency", "title": "Revenue"}},
        time_dimensions={"sales.order_date": {"type": "time", "granularity": None}},
    )
    spec = recommend_chart(ann, [{"sales.revenue": 5000}])
    assert spec["chart"] == "kpi"


def test_small_nonnegative_breakdown_is_a_pie():
    ann = _ann(
        measures={"order_costs.cost_amount": {"type": "currency", "title": "Cost amount"}},
        dimensions={"order_costs.cost_type": {"type": "string"}},
    )
    data = [
        {"order_costs.cost_type": "material", "order_costs.cost_amount": 700},
        {"order_costs.cost_type": "shipping", "order_costs.cost_amount": 300},
    ]
    spec = recommend_chart(ann, data)
    assert spec["chart"] == "pie"
    assert spec["x"] == "order_costs.cost_type"
    assert spec["measure"] == "order_costs.cost_amount"


def test_many_categories_is_a_bar_not_a_pie():
    ann = _ann(
        measures={"sales.revenue": {"type": "currency", "title": "Revenue"}},
        dimensions={"geography.country": {"type": "string"}},
    )
    data = [{"geography.country": f"C{i}", "sales.revenue": 100 + i} for i in range(10)]
    spec = recommend_chart(ann, data)
    assert spec["chart"] == "bar"
    assert spec["x"] == "geography.country"
    assert spec["series"] == ["sales.revenue"]


def test_negative_values_never_become_a_pie():
    # Margin can be negative; a pie slice cannot. Fall back to a bar.
    ann = _ann(
        measures={"sales.margin": {"type": "currency", "title": "Margin"}},
        dimensions={"geography.region": {"type": "string"}},
    )
    data = [
        {"geography.region": "North", "sales.margin": 500},
        {"geography.region": "South", "sales.margin": -200},
    ]
    spec = recommend_chart(ann, data)
    assert spec["chart"] == "bar"


def test_percent_measure_never_becomes_a_pie():
    # Percentages are not additive, so they cannot compose a whole.
    ann = _ann(
        measures={"sales.margin_pct": {"type": "percent", "title": "Margin %"}},
        dimensions={"geography.region": {"type": "string"}},
    )
    data = [
        {"geography.region": "North", "sales.margin_pct": 30.0},
        {"geography.region": "South", "sales.margin_pct": 25.0},
    ]
    spec = recommend_chart(ann, data)
    assert spec["chart"] == "bar"


def test_multi_measure_breakdown_is_a_grouped_bar():
    ann = _ann(
        measures={
            "sales.revenue": {"type": "currency", "title": "Revenue"},
            "sales.cost": {"type": "currency", "title": "Cost"},
        },
        dimensions={"geography.region": {"type": "string"}},
    )
    data = [{"geography.region": "North", "sales.revenue": 900, "sales.cost": 400}]
    spec = recommend_chart(ann, data)
    assert spec["chart"] == "bar"
    assert spec["series"] == ["sales.revenue", "sales.cost"]


def test_time_split_by_category_is_a_multi_series_line():
    ann = _ann(
        measures={"sales.margin_pct": {"type": "percent", "title": "Margin %"}},
        dimensions={"geography.continent": {"type": "string"}},
        time_dimensions={"sales.order_date": {"type": "time", "granularity": "quarter"}},
    )
    data = [{"sales.order_date": "2025-01-01", "geography.continent": "Europe", "sales.margin_pct": 30.0}]
    spec = recommend_chart(ann, data)
    assert spec["chart"] == "line"
    assert spec["seriesBy"] == "geography.continent"
    assert spec["measure"] == "sales.margin_pct"


def test_no_measures_has_no_chart():
    ann = _ann(dimensions={"geography.region": {"type": "string"}})
    spec = recommend_chart(ann, [{"geography.region": "North"}])
    assert spec["chart"] == "none"


def test_recommendation_is_deterministic():
    ann = _ann(
        measures={"sales.revenue": {"type": "currency", "title": "Revenue"}},
        dimensions={"geography.country": {"type": "string"}},
    )
    data = [{"geography.country": "DE", "sales.revenue": 100}]
    assert recommend_chart(ann, data) == recommend_chart(ann, data)


def test_spec_only_names_annotated_members():
    ann = _ann(
        measures={"sales.revenue": {"type": "currency", "title": "Revenue"}},
        dimensions={"geography.region": {"type": "string"}},
    )
    data = [{"geography.region": "North", "sales.revenue": 900}]
    spec = recommend_chart(ann, data)
    members = set(ann["measures"]) | set(ann["dimensions"]) | set(ann["timeDimensions"])
    named = {spec.get("x"), spec.get("measure"), *(spec.get("series") or [])} - {None}
    assert named <= members
