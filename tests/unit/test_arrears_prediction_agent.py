"""UC-004: Arrears Prediction Agent — unit tests covering AC-004-01 through AC-004-08."""
import pytest
from collection_assistant.models.arrears import ArrearsPrediction, RiskFactor
from collection_assistant.tools.arrears_tools import (
    analyse_payment_pattern,
    calculate_arrears_trajectory,
    estimate_future_arrears,
    identify_risk_factors,
    predict_default_probability,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _months(pattern: list[int]) -> list[dict]:
    """Build payment_months from a list of on_time flags (1=paid, 0=missed)."""
    return [
        {"month": f"2026-{12-i:02d}", "amount_due": 500.0,
         "amount_paid": 500.0 if on_time else 0.0, "on_time": bool(on_time)}
        for i, on_time in enumerate(pattern)
    ]


# ── AC-004-01: Trajectory Literal constraint ───────────────────────────────────

class TestAC00401TrajectoryLiteral:
    """AC-004-01: arrears_trajectory accepts only the 4 valid values."""

    @pytest.mark.parametrize("traj", ["improving", "stable", "deteriorating", "critical"])
    def test_valid_trajectories_accepted(self, traj):
        p = ArrearsPrediction(
            current_arrears_band="current", arrears_trajectory=traj,
            predicted_dpd_30=0, predicted_dpd_60=0, predicted_dpd_90=0,
            default_probability=0.1, predicted_arrears_amount=1000.0,
            confidence_score=0.8, summary="test",
        )
        assert p.arrears_trajectory == traj

    def test_invalid_trajectory_coerced_to_stable(self):
        p = ArrearsPrediction(
            current_arrears_band="current", arrears_trajectory="UNKNOWN",
            predicted_dpd_30=0, predicted_dpd_60=0, predicted_dpd_90=0,
            default_probability=0.1, predicted_arrears_amount=1000.0,
            confidence_score=0.8, summary="test",
        )
        assert p.arrears_trajectory == "stable"

    def test_trajectory_case_insensitive(self):
        p = ArrearsPrediction(
            current_arrears_band="current", arrears_trajectory="CRITICAL",
            predicted_dpd_30=90, predicted_dpd_60=120, predicted_dpd_90=150,
            default_probability=0.9, predicted_arrears_amount=15000.0,
            confidence_score=0.85, summary="test",
        )
        assert p.arrears_trajectory == "critical"


# ── AC-004-02: Default probability bounds ─────────────────────────────────────

class TestAC00402DefaultProbability:
    """AC-004-02: default_probability is always within [0.0, 1.0]."""

    @pytest.mark.parametrize("dpd,traj,seg,rate", [
        (0, "improving", "low", 1.0),
        (45, "stable", "medium", 0.8),
        (92, "critical", "high", 0.3),
        (120, "critical", "hardship", 0.1),
    ])
    def test_probability_in_range(self, dpd, traj, seg, rate):
        prob = predict_default_probability(dpd, traj, seg, rate)
        assert 0.0 <= prob <= 1.0

    def test_model_clamps_probability(self):
        p = ArrearsPrediction(
            current_arrears_band="90+", arrears_trajectory="critical",
            predicted_dpd_30=100, predicted_dpd_60=130, predicted_dpd_90=160,
            default_probability=1.5,  # over 1.0 — should clamp
            predicted_arrears_amount=20000.0, confidence_score=0.9, summary="test",
        )
        assert p.default_probability == 1.0

    def test_model_clamps_confidence(self):
        p = ArrearsPrediction(
            current_arrears_band="current", arrears_trajectory="stable",
            predicted_dpd_30=0, predicted_dpd_60=0, predicted_dpd_90=0,
            default_probability=0.05, predicted_arrears_amount=1000.0,
            confidence_score=-0.1,  # below 0 — should clamp
            summary="test",
        )
        assert p.confidence_score == 0.0


# ── AC-004-03: Deteriorating DPD forecast increases ───────────────────────────

class TestAC00403DeterioratingForecast:
    """AC-004-03: 3 consecutive missed payments → increasing DPD forecast."""

    def test_deteriorating_dpd_forecast_increases(self):
        # 3 missed, then 9 on-time
        months = _months([0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1])
        pattern = analyse_payment_pattern(months)
        assert pattern["consecutive_missed"] == 3
        trajectory = calculate_arrears_trajectory(45, pattern["trend"], pattern["consecutive_missed"])
        forecast = estimate_future_arrears(45, trajectory, 12000.0)
        assert forecast["predicted_dpd_30"] >= 45
        assert forecast["predicted_dpd_60"] >= forecast["predicted_dpd_30"]
        assert forecast["predicted_dpd_90"] >= forecast["predicted_dpd_60"]

    def test_deteriorating_trajectory_assigned_for_3_consecutive_missed(self):
        trajectory = calculate_arrears_trajectory(45, "deteriorating", 3)
        assert trajectory == "deteriorating"

    def test_critical_assigned_for_4_or_more_consecutive_missed(self):
        trajectory = calculate_arrears_trajectory(30, "deteriorating", 4)
        assert trajectory == "critical"


# ── AC-004-04: Improving DPD forecast stable or decreasing ────────────────────

class TestAC00404ImprovingForecast:
    """AC-004-04: improving pattern → trajectory="improving", forecast DPD ≤ current."""

    def test_improving_trajectory_assigned(self):
        months = _months([1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        pattern = analyse_payment_pattern(months)
        assert pattern["trend"] == "improving"
        trajectory = calculate_arrears_trajectory(20, pattern["trend"], 0)
        assert trajectory == "improving"

    def test_improving_dpd_forecast_does_not_increase(self):
        forecast = estimate_future_arrears(20, "improving", 5000.0)
        assert forecast["predicted_dpd_30"] <= 20
        assert forecast["predicted_dpd_60"] <= 20
        assert forecast["predicted_dpd_90"] <= 20

    def test_improving_default_probability_below_threshold(self):
        prob = predict_default_probability(20, "improving", "low", 0.95)
        assert prob < 0.3


# ── AC-004-05: Critical trajectory for 90+ DPD ────────────────────────────────

class TestAC00405CriticalTrajectory:
    """AC-004-05: Michael Okonkwo CUST-003 personal_loan DPD 92 → critical + prob > 0.85."""

    def test_critical_trajectory_for_90_plus_dpd(self):
        trajectory = calculate_arrears_trajectory(92, "deteriorating", 3)
        assert trajectory == "critical"

    def test_default_probability_above_85_for_critical_high_risk(self):
        prob = predict_default_probability(92, "critical", "high", 0.3)
        assert prob > 0.85

    def test_critical_probability_range(self):
        prob = predict_default_probability(92, "critical", "high", 0.3)
        assert 0.0 <= prob <= 1.0


# ── AC-004-06: Risk factors as ranked dicts ───────────────────────────────────

class TestAC00406RiskFactors:
    """AC-004-06: identify_risk_factors returns list of {name, weight} sorted by weight desc."""

    def test_returns_list_of_dicts(self):
        factors = identify_risk_factors(75, "critical", True, "unemployed", 0.4, 4)
        assert isinstance(factors, list)
        assert len(factors) >= 1
        for f in factors:
            assert "name" in f
            assert "weight" in f
            assert isinstance(f["name"], str)
            assert isinstance(f["weight"], float)

    def test_sorted_by_weight_descending(self):
        factors = identify_risk_factors(75, "critical", True, "unemployed", 0.4, 4)
        weights = [f["weight"] for f in factors]
        assert weights == sorted(weights, reverse=True)

    def test_weights_in_valid_range(self):
        factors = identify_risk_factors(75, "critical", True, "unemployed", 0.4, 4)
        for f in factors:
            assert 0.0 <= f["weight"] <= 1.0

    def test_no_factors_returns_placeholder(self):
        factors = identify_risk_factors(0, "stable", False, "employed", 1.0, 0)
        assert len(factors) == 1
        assert "No significant" in factors[0]["name"]

    def test_high_dpd_factor_has_high_weight(self):
        factors = identify_risk_factors(95, "critical", False, "employed", 0.9, 0)
        top = factors[0]
        assert top["weight"] >= 0.7
        assert "DPD" in top["name"] or "trajectory" in top["name"].lower()

    def test_risk_factor_model_validates(self):
        rf = RiskFactor(name="High DPD: 92 days past due", weight=0.90)
        assert rf.name == "High DPD: 92 days past due"
        assert rf.weight == 0.90


# ── AC-004-07: Low history reduces confidence ─────────────────────────────────

class TestAC00407LowHistoryConfidence:
    """AC-004-07: < 3 months of history → confidence_score < 0.5."""

    def test_two_months_history_low_confidence(self):
        forecast = estimate_future_arrears(30, "stable", 5000.0, months_available=2)
        assert forecast["confidence_score"] < 0.5

    def test_zero_months_history_very_low_confidence(self):
        forecast = estimate_future_arrears(0, "stable", 5000.0, months_available=0)
        assert forecast["confidence_score"] < 0.5

    def test_six_months_history_moderate_confidence(self):
        forecast = estimate_future_arrears(30, "stable", 5000.0, months_available=6)
        assert forecast["confidence_score"] >= 0.5

    def test_twelve_months_history_high_confidence(self):
        forecast = estimate_future_arrears(30, "stable", 5000.0, months_available=12)
        assert forecast["confidence_score"] >= 0.8


# ── AC-004-08 (structural): estimate_future_arrears returns all required fields ─

class TestAC00408ForecastFields:
    """AC-004-08: estimate_future_arrears returns all 5 required fields."""

    def test_all_fields_present(self):
        result = estimate_future_arrears(45, "deteriorating", 8000.0)
        assert "predicted_dpd_30" in result
        assert "predicted_dpd_60" in result
        assert "predicted_dpd_90" in result
        assert "predicted_arrears_amount" in result
        assert "confidence_score" in result

    def test_dpd_values_are_non_negative(self):
        result = estimate_future_arrears(0, "improving", 5000.0)
        assert result["predicted_dpd_30"] >= 0
        assert result["predicted_dpd_60"] >= 0
        assert result["predicted_dpd_90"] >= 0

    def test_predicted_amount_greater_than_balance(self):
        result = estimate_future_arrears(60, "deteriorating", 10000.0)
        assert result["predicted_arrears_amount"] >= 10000.0


# ── Backward-compatible tests from original test_arrears_tools.py ─────────────

class TestArrearsToolsBackwardsCompat:
    """Regression: original tool behaviours still correct after refactor."""

    def test_analyse_payment_pattern_deteriorating(self):
        months = _months([0, 0, 0, 1, 1, 1])
        result = analyse_payment_pattern(months)
        assert result["trend"] == "deteriorating"
        assert result["consecutive_missed"] == 3

    def test_analyse_payment_pattern_improving(self):
        months = _months([1, 1, 1, 0, 0, 0])
        result = analyse_payment_pattern(months)
        assert result["trend"] == "improving"

    def test_calculate_trajectory_critical(self):
        assert calculate_arrears_trajectory(95, "deteriorating", 4) == "critical"

    def test_calculate_trajectory_improving(self):
        assert calculate_arrears_trajectory(10, "improving", 0) == "improving"

    def test_predict_default_probability_range(self):
        prob = predict_default_probability(60, "deteriorating", "high", 0.5)
        assert 0.0 <= prob <= 1.0

    def test_predict_default_probability_high_dpd(self):
        prob_high = predict_default_probability(90, "critical", "high", 0.3)
        prob_low = predict_default_probability(0, "improving", "low", 0.95)
        assert prob_high > prob_low

    def test_identify_risk_factors_returns_list(self):
        factors = identify_risk_factors(70, "deteriorating", True, "unemployed", 0.4, 4)
        assert len(factors) > 0
        assert isinstance(factors[0], dict)
