"""
Multi-step reasoning: deterministic root-cause decomposition.

The flagship question — "Why did European margins drop last quarter?" — needs the
agent to go past the number and find the *driver*. Rather than hope a small local
LLM reliably chains the right follow-up queries, the decomposition itself is
governed, deterministic code here; the agent calls it as one tool and narrates the
result. (The agent can still chain raw queries via query_semantic_layer for
open-ended drill-downs.)

margin = revenue - cost, and cost = material + shipping, so a margin change
attributes cleanly to three contributions to margin:
    +revenue_change, -material_cost_change, -shipping_cost_change
The most negative contribution is the dominant reason margin fell.
"""

from __future__ import annotations

from .semantic_client import load as _http_load

_MEASURES = [
    "sales.revenue",
    "sales.cost",
    "sales.margin",
    "sales.material_cost",
    "sales.shipping_cost",
]


def _metrics_for(continent: str, period: str, load_fn) -> dict:
    query = {
        "measures": _MEASURES,
        "timeDimensions": [{"dimension": "sales.order_date", "dateRange": period}],
        "filters": [{"member": "geography.continent", "operator": "equals", "values": [continent]}],
    }
    data = load_fn(query).get("data") or [{}]
    return data[0]


def decompose_margin_change(continent: str, period_a: str, period_b: str, load_fn=_http_load) -> dict:
    """Attribute the change in margin for `continent` from period_a -> period_b to
    revenue / material-cost / shipping-cost drivers, and name the dominant one."""
    a = _metrics_for(continent, period_a, load_fn)
    b = _metrics_for(continent, period_b, load_fn)

    def delta(key: str) -> float:
        return round((b.get(key) or 0) - (a.get(key) or 0), 2)

    revenue_change = delta("sales.revenue")
    material_change = delta("sales.material_cost")
    shipping_change = delta("sales.shipping_cost")

    # A positive contribution helps margin; rising costs hurt it.
    contributions = {
        "revenue": revenue_change,
        "material_cost": -material_change,
        "shipping_cost": -shipping_change,
    }
    dominant = min(contributions, key=contributions.get)

    return {
        "continent": continent,
        "period_a": period_a,
        "period_b": period_b,
        "margin_change": delta("sales.margin"),
        "revenue_change": revenue_change,
        "material_cost_change": material_change,
        "shipping_cost_change": shipping_change,
        "contributions_to_margin": contributions,
        "dominant_driver": dominant,
    }
