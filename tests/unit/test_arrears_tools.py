"""Unit tests for arrears prediction tools."""
import pytest
from collection_assistant.tools.arrears_tools import (
    analyse_payment_pattern,
    calculate_arrears_trajectory,
    predict_default_probability,
    identify_risk_factors,
)


def test_analyse_payment_pattern_deteriorating():
    months = [
        {"amount_due": 500, "amount_paid": 0, "on_time": False},
        {"amount_due": 500, "amount_paid": 0, "on_time": False},
        {"amount_due": 500, "amount_paid": 0, "on_time": False},
        {"amount_due": 500, "amount_paid": 500, "on_time": True},
        {"amount_due": 500, "amount_paid": 500, "on_time": True},
        {"amount_due": 500, "amount_paid": 500, "on_time": True},
    ]
    result = analyse_payment_pattern(months)
    assert result["trend"] == "deteriorating"
    assert result["consecutive_missed"] == 3


def test_analyse_payment_pattern_improving():
    months = [
        {"amount_due": 500, "amount_paid": 500, "on_time": True},
        {"amount_due": 500, "amount_paid": 500, "on_time": True},
        {"amount_due": 500, "amount_paid": 500, "on_time": True},
        {"amount_due": 500, "amount_paid": 0, "on_time": False},
        {"amount_due": 500, "amount_paid": 0, "on_time": False},
        {"amount_due": 500, "amount_paid": 0, "on_time": False},
    ]
    result = analyse_payment_pattern(months)
    assert result["trend"] == "improving"


def test_calculate_trajectory_critical():
    assert calculate_arrears_trajectory(95, "deteriorating", 4) == "critical"


def test_calculate_trajectory_improving():
    assert calculate_arrears_trajectory(10, "improving", 0) == "improving"


def test_predict_default_probability_range():
    prob = predict_default_probability(60, "deteriorating", "high", 0.5)
    assert 0.0 <= prob <= 1.0


def test_predict_default_probability_high_dpd():
    prob_high = predict_default_probability(90, "critical", "high", 0.3)
    prob_low = predict_default_probability(0, "improving", "low", 0.95)
    assert prob_high > prob_low


def test_identify_risk_factors():
    factors = identify_risk_factors(70, "deteriorating", True, "unemployed", 0.4, 4)
    assert len(factors) > 2
    assert any("DPD" in f for f in factors)
    assert any("hardship" in f.lower() for f in factors)
