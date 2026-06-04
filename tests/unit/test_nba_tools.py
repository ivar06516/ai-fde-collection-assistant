"""Unit tests for NBA tools."""
from collection_assistant.tools.nba_tools import evaluate_action_eligibility, score_action_options


def test_collection_hold_restricts_actions():
    result = evaluate_action_eligibility(True, "deteriorating", 45, "delinquent")
    assert set(result["eligible_actions"]) == {"place_on_hold", "no_action_required"}
    assert len(result["constraints"]) > 0


def test_no_hold_allows_all_actions():
    result = evaluate_action_eligibility(False, "stable", 15, "delinquent")
    assert len(result["eligible_actions"]) > 5
    assert "initiate_call" in result["eligible_actions"]


def test_score_options_critical_trajectory():
    eligible = ["initiate_call", "escalate_to_legal", "offer_settlement", "send_sms"]
    scored = score_action_options(eligible, "critical", 95, 0.85, "high")
    top_action = scored[0]["action"]
    assert top_action in ("escalate_to_legal", "offer_settlement")


def test_score_returns_sorted_descending():
    eligible = ["send_sms", "offer_payment_plan", "escalate_to_legal"]
    scored = score_action_options(eligible, "stable", 20, 0.2, "medium")
    scores = [s["score"] for s in scored]
    assert scores == sorted(scores, reverse=True)
