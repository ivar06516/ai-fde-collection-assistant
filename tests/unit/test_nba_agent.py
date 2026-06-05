"""UC-006: NBA Agent — unit tests covering AC-006-01 through AC-006-09."""
import pytest
from collection_assistant.models.nba import NBARecommendation, AlternativeAction, NBA_ACTIONS
from collection_assistant.tools.nba_tools import evaluate_action_eligibility, score_action_options


# ── AC-006-01: Action always from approved catalogue ──────────────────────────

class TestAC00601ApprovedCatalogue:
    """AC-006-01: NBARecommendation.action is always one of the 9 approved actions."""

    @pytest.mark.parametrize("action", NBA_ACTIONS)
    def test_all_9_approved_actions_accepted(self, action):
        rec = NBARecommendation(
            action=action, channel="mobile", rationale="Test rationale " * 5,
            confidence_score=0.8, urgency="medium", summary="Test",
        )
        assert rec.action == action

    def test_unknown_action_coerced_to_no_action_required(self):
        rec = NBARecommendation(
            action="INVALID_ACTION", channel="none",
            rationale="Unknown action test " * 5,
            confidence_score=0.5, urgency="low", summary="Test",
        )
        assert rec.action == "no_action_required"

    def test_action_with_spaces_normalised(self):
        rec = NBARecommendation(
            action="initiate call", channel="mobile",
            rationale="Space in action name test " * 5,
            confidence_score=0.7, urgency="medium", summary="Test",
        )
        assert rec.action == "initiate_call"

    def test_action_case_insensitive(self):
        rec = NBARecommendation(
            action="PLACE_ON_HOLD", channel="none",
            rationale="Case test " * 5,
            confidence_score=0.95, urgency="high", summary="Test",
        )
        assert rec.action == "place_on_hold"

    def test_nba_actions_list_has_9_entries(self):
        assert len(NBA_ACTIONS) == 9


# ── AC-006-02: Dispute hold enforces hard constraint ──────────────────────────

class TestAC00602DisputeHoldConstraint:
    """AC-006-02: collection_hold=True → only place_on_hold or no_action_required."""

    def test_hold_filters_to_two_actions(self):
        result = evaluate_action_eligibility(True, "deteriorating", 45, "delinquent")
        assert set(result["eligible_actions"]) == {"place_on_hold", "no_action_required"}

    def test_hold_removes_all_outbound_actions(self):
        result = evaluate_action_eligibility(True, "critical", 90, "delinquent")
        outbound = {"initiate_call", "send_sms", "send_email",
                    "offer_payment_plan", "offer_settlement", "escalate_to_legal"}
        assert not set(result["eligible_actions"]) & outbound

    def test_blocked_by_dispute_flag_true_when_hold(self):
        rec = NBARecommendation(
            action="place_on_hold", channel="none",
            rationale="Collection hold active. Outbound contact not permitted " * 3,
            confidence_score=0.99, urgency="medium",
            blocked_by_dispute=True, summary="On hold.",
        )
        assert rec.blocked_by_dispute is True
        assert rec.action == "place_on_hold"

    @pytest.mark.parametrize("trajectory", ["improving", "stable", "deteriorating", "critical"])
    def test_hold_blocks_all_trajectories(self, trajectory):
        result = evaluate_action_eligibility(True, trajectory, 30, "delinquent")
        for a in result["eligible_actions"]:
            assert a in ("place_on_hold", "no_action_required")

    def test_priya_mehta_scenario_blocked(self):
        """AC-006-02 named scenario: Priya Mehta CUST-002, DPD=45, hold=True."""
        result = evaluate_action_eligibility(
            collection_hold=True, arrears_trajectory="deteriorating",
            dpd=45, account_status="delinquent"
        )
        assert result["eligible_actions"] == ["place_on_hold", "no_action_required"]


# ── AC-006-03: Critical trajectory routes to urgent actions ──────────────────

class TestAC00603CriticalTrajectory:
    """AC-006-03: Rahul Singh CUST-003 DPD=92 → escalate_to_legal or offer_settlement."""

    def test_critical_high_prob_top_actions_are_urgent(self):
        eligible = ["initiate_call", "offer_payment_plan", "escalate_to_legal",
                    "offer_settlement", "send_sms"]
        scored = score_action_options(eligible, "critical", 92, 0.98, "high")
        top_action = scored[0]["action"]
        assert top_action in ("escalate_to_legal", "offer_settlement")

    def test_critical_trajectory_scores_urgent_actions_highest(self):
        eligible = list(["initiate_call", "send_sms", "offer_settlement",
                          "escalate_to_legal", "offer_payment_plan"])
        scored = score_action_options(eligible, "critical", 95, 0.95, "high")
        top_2 = {s["action"] for s in scored[:2]}
        assert top_2 & {"escalate_to_legal", "offer_settlement"}

    def test_no_hold_allows_escalation(self):
        result = evaluate_action_eligibility(False, "critical", 92, "delinquent")
        assert "escalate_to_legal" in result["eligible_actions"]
        assert "offer_settlement" in result["eligible_actions"]


# ── AC-006-04: Improving trajectory routes to light-touch actions ─────────────

class TestAC00604ImprovingTrajectory:
    """AC-006-04: Arjun Sharma CUST-001 DPD=0 → no_action_required or send_sms."""

    def test_improving_low_dpd_favours_light_touch(self):
        eligible = list(NBA_ACTIONS)
        scored = score_action_options(eligible, "improving", 0, 0.01, "low")
        top_action = scored[0]["action"]
        assert top_action in ("no_action_required", "send_sms", "send_email")

    def test_improving_trajectory_not_blocked(self):
        result = evaluate_action_eligibility(False, "improving", 0, "current")
        assert "no_action_required" in result["eligible_actions"]
        assert "send_sms" in result["eligible_actions"]

    def test_arjun_sharma_scenario(self):
        """Arjun Sharma: current account, DPD=0, improving → no_action_required top."""
        eligible = list(NBA_ACTIONS)
        scored = score_action_options(eligible, "improving", 0, 0.01, "low")
        assert scored[0]["action"] in ("no_action_required", "send_sms")


# ── AC-006-05: Rationale references specific state values ────────────────────

class TestAC00605RationaleContent:
    """AC-006-05: Rationale must reference specific values from the state."""

    def test_rationale_minimum_length(self):
        rec = NBARecommendation(
            action="initiate_call", channel="mobile",
            rationale="Customer has 45 days past due with deteriorating trajectory on mobile channel.",
            confidence_score=0.8, urgency="high", summary="Call recommended.",
        )
        assert len(rec.rationale) >= 50

    def test_rationale_can_contain_state_values(self):
        rationale = ("DPD is 45 days, trajectory is deteriorating. Customer prefers mobile. "
                     "Risk segment is high. Initiating call is recommended.")
        rec = NBARecommendation(
            action="initiate_call", channel="mobile",
            rationale=rationale, confidence_score=0.8,
            urgency="high", summary="Call recommended.",
        )
        state_values = ["45", "deteriorating", "mobile", "high"]
        matches = sum(1 for v in state_values if v in rec.rationale)
        assert matches >= 2, f"Expected >=2 state values in rationale, found {matches}"


# ── AC-006-06: Confidence score within valid range ────────────────────────────

class TestAC00606ConfidenceRange:
    """AC-006-06: confidence_score always in [0.0, 1.0]."""

    @pytest.mark.parametrize("score", [0.0, 0.5, 0.99, 1.0])
    def test_valid_confidence_accepted(self, score):
        rec = NBARecommendation(
            action="send_sms", channel="mobile",
            rationale="Test rationale " * 5,
            confidence_score=score, urgency="low", summary="Test",
        )
        assert rec.confidence_score == round(score, 4)

    def test_confidence_above_1_clamped(self):
        rec = NBARecommendation(
            action="send_sms", channel="mobile",
            rationale="Test " * 10, confidence_score=1.5, urgency="low", summary="t",
        )
        assert rec.confidence_score == 1.0

    def test_confidence_below_0_clamped(self):
        rec = NBARecommendation(
            action="send_sms", channel="mobile",
            rationale="Test " * 10, confidence_score=-0.1, urgency="low", summary="t",
        )
        assert rec.confidence_score == 0.0


# ── AC-006-07: At least 2 alternative actions ─────────────────────────────────

class TestAC00607AlternativeActions:
    """AC-006-07: alternative_actions >= 2, all from approved catalogue."""

    def test_three_alternatives_accepted(self):
        rec = NBARecommendation(
            action="escalate_to_legal", channel="legal_team",
            rationale="Critical account. " * 5,
            confidence_score=0.95, urgency="critical",
            alternative_actions=[
                AlternativeAction(action="offer_settlement", rationale="Alt 1", confidence=0.82),
                AlternativeAction(action="initiate_call",   rationale="Alt 2", confidence=0.65),
                AlternativeAction(action="offer_payment_plan", rationale="Alt 3", confidence=0.55),
            ],
            summary="Escalate.",
        )
        assert len(rec.alternative_actions) == 3

    def test_all_alternative_actions_from_catalogue(self):
        alts = [
            AlternativeAction(action=a, rationale="r", confidence=0.5)
            for a in ["offer_settlement", "initiate_call", "send_sms"]
        ]
        rec = NBARecommendation(
            action="escalate_to_legal", channel="legal_team",
            rationale="Test " * 10, confidence_score=0.9, urgency="critical",
            alternative_actions=alts, summary="t",
        )
        for alt in rec.alternative_actions:
            assert alt.action in NBA_ACTIONS

    def test_invalid_alternative_action_normalised(self):
        alt = AlternativeAction(action="SEND MESSAGE", rationale="r", confidence=0.5)
        assert alt.action == "send_message" or alt.action == "no_action_required"

    def test_minimum_two_alternatives_satisfied(self):
        rec = NBARecommendation(
            action="initiate_call", channel="mobile",
            rationale="Deteriorating customer. " * 5, confidence_score=0.85,
            urgency="high",
            alternative_actions=[
                AlternativeAction(action="offer_payment_plan", rationale="Plan", confidence=0.7),
                AlternativeAction(action="send_sms", rationale="SMS", confidence=0.5),
            ],
            summary="Call.",
        )
        assert len(rec.alternative_actions) >= 2


# ── AC-006-08: Legal status account routes to escalate_to_legal ──────────────

class TestAC00608LegalAccountRouting:
    """AC-006-08: Ananya Reddy CUST-008 legal status + high default prob → escalate_to_legal."""

    def test_legal_status_eligible_actions(self):
        result = evaluate_action_eligibility(False, "critical", 120, "legal")
        assert "escalate_to_legal" in result["eligible_actions"]
        assert "offer_settlement" in result["eligible_actions"]

    def test_legal_status_constraints_applied(self):
        result = evaluate_action_eligibility(False, "critical", 120, "legal")
        assert len(result["constraints"]) > 0
        assert any("legal" in c.lower() for c in result["constraints"])

    def test_legal_status_scores_escalate_highest(self):
        eligible = ["initiate_call", "offer_settlement", "escalate_to_legal", "place_on_hold"]
        scored = score_action_options(eligible, "critical", 120, 0.99, "hardship")
        assert scored[0]["action"] in ("escalate_to_legal", "offer_settlement")

    def test_ananya_reddy_scenario(self):
        """Ananya Reddy: legal, DPD=120, hardship, default_prob=0.99."""
        result = evaluate_action_eligibility(
            collection_hold=False, arrears_trajectory="critical",
            dpd=120, account_status="legal"
        )
        assert "escalate_to_legal" in result["eligible_actions"]


# ── AC-006-09: Urgency Literal constraint ─────────────────────────────────────

class TestAC00609UrgencyConstraint:
    """AC-006-09: urgency is one of low | medium | high | critical."""

    @pytest.mark.parametrize("urgency", ["low", "medium", "high", "critical"])
    def test_valid_urgency_accepted(self, urgency):
        rec = NBARecommendation(
            action="send_sms", channel="mobile",
            rationale="Test " * 10, confidence_score=0.7,
            urgency=urgency, summary="t",
        )
        assert rec.urgency == urgency

    def test_invalid_urgency_coerced_to_medium(self):
        rec = NBARecommendation(
            action="send_sms", channel="mobile",
            rationale="Test " * 10, confidence_score=0.7,
            urgency="EXTREME", summary="t",
        )
        assert rec.urgency == "medium"
