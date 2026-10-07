"""Governance: the semantic layer refuses anything outside its whitelist."""

import pytest

from semantic.model import SemanticError, load


def test_unknown_measure_rejected():
    with pytest.raises(SemanticError):
        load({"measures": ["sales.profit"]})


def test_unknown_dimension_rejected():
    with pytest.raises(SemanticError):
        load({"measures": ["sales.revenue"], "dimensions": ["geography.planet"]})


def test_unknown_filter_member_rejected():
    with pytest.raises(SemanticError):
        load(
            {
                "measures": ["sales.revenue"],
                "filters": [{"member": "geography.galaxy", "operator": "equals", "values": ["x"]}],
            }
        )


def test_fact_mix_rejected():
    # margin lives on `sales`; cost_type lives on `order_costs` — cannot combine.
    with pytest.raises(SemanticError):
        load({"measures": ["sales.margin"], "dimensions": ["order_costs.cost_type"]})


def test_empty_query_rejected():
    with pytest.raises(SemanticError):
        load({})
