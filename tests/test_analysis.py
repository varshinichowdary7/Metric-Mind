"""Phase 7: deterministic root-cause decomposition (multi-step reasoning).

Runs against the semantic layer in-process (no LLM), so the "why did margin drop"
answer is reproducible and testable.
"""

from api.analysis import decompose_margin_change
from semantic.model import load as model_load


def test_shipping_is_dominant_driver_of_european_margin_drop():
    r = decompose_margin_change("Europe", "2025-Q2", "2025-Q3", load_fn=model_load)
    assert r["margin_change"] < 0  # margin fell
    assert r["dominant_driver"] == "shipping_cost"  # shipping is the culprit
    assert r["shipping_cost_change"] > r["material_cost_change"]  # shipping rose more than material


def test_contributions_reconcile_to_margin_change():
    r = decompose_margin_change("Europe", "2025-Q2", "2025-Q3", load_fn=model_load)
    total = sum(r["contributions_to_margin"].values())
    assert abs(total - r["margin_change"]) < 1.0  # the three drivers explain the whole change
