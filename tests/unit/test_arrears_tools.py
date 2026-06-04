"""Legacy arrears tools tests — kept for regression, superseded by test_arrears_prediction_agent.py."""
import pytest
from collection_assistant.tools.arrears_tools import (
    analyse_payment_pattern,
    calculate_arrears_trajectory,
    identify_risk_factors,
    predict_default_probability,
)


def _months(flags):
    return [{"month": f"2026-{12-i:02d}", "amount_due": 500.0,
             "amount_paid": 500.0 if f else 0.0, "on_time": bool(f)}
            for i, f in enumerate(flags)]


def test_analyse_payment_pattern_deteriorating():
    result = analyse_payment_pattern(_months([0, 0, 0, 1, 1, 1]))
    assert result["trend"] == "deteriorating"
    assert result["consecutive_missed"] == 3


def test_analyse_payment_pattern_improving():
    result = analyse_payment_pattern(_months([1, 1, 1, 0, 0, 0]))
    assert result["trend"] == "improving"


def test_calculate_trajectory_critical():
    assert calculate_arrears_trajectory(95, "deteriorating", 4) == "critical"


def test_calculate_trajectory_improving():
    assert calculate_arrears_trajectory(10, "improving", 0) == "improving"


def test_predict_default_probability_range():
    prob = predict_default_probability(60, "deteriorating", "high", 0.5)
    assert 0.0 <= prob <= 1.0


def test_predict_default_probability_high_dpd():
    assert predict_default_probability(90, "critical", "high", 0.3) > \
           predict_default_probability(0, "improving", "low", 0.95)


def test_identify_risk_factors():
    factors = identify_risk_factors(70, "deteriorating", True, "unemployed", 0.4, 4)
    assert len(factors) > 2
    # New format: list of dicts
    assert all(isinstance(f, dict) for f in factors)
    names = [f["name"] for f in factors]
    assert any("DPD" in n or "trajectory" in n.lower() for n in names)
    assert any("hardship" in n.lower() for n in names)
