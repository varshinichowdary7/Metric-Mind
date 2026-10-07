"""Cost-governance guardrails: clamp the limit, reject expensive queries."""

import pytest

from semantic.guardrails import DEFAULT_LIMIT, MAX_LIMIT, GuardrailError, apply


def test_limit_defaults_when_absent():
    assert apply({"measures": ["sales.revenue"]})["limit"] == DEFAULT_LIMIT


def test_limit_clamped_to_max():
    assert apply({"measures": ["sales.revenue"], "limit": 10**9})["limit"] == MAX_LIMIT


def test_limit_floor_is_one():
    assert apply({"measures": ["sales.revenue"], "limit": -5})["limit"] == 1


def test_too_many_measures_rejected():
    with pytest.raises(GuardrailError):
        apply({"measures": [f"m{i}" for i in range(7)]})


def test_too_many_grouping_dimensions_rejected():
    with pytest.raises(GuardrailError):
        apply({"dimensions": ["a", "b", "c", "d", "e"]})


def test_granular_time_dimensions_count_toward_grouping():
    with pytest.raises(GuardrailError):
        apply(
            {
                "dimensions": ["a", "b", "c", "d"],
                "timeDimensions": [{"dimension": "sales.order_date", "granularity": "quarter"}],
            }
        )
