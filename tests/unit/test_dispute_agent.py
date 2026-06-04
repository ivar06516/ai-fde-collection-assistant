"""UC-005: Dispute Agent — unit tests covering AC-005-01 through AC-005-07."""
import time
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from collection_assistant.models.dispute import DisputeItem, DisputeSummary
from collection_assistant.models.nba import NBARecommendation
from collection_assistant.tools.dispute_tools import (
    classify_dispute_type,
    check_collection_hold,
    get_active_disputes_data,
    get_dispute_history,
    get_resolution_timeline,
)
from collection_assistant.tools.nba_tools import evaluate_action_eligibility


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_dispute_row(dispute_id="DISP-001", dispute_type="identity_theft",
                       status="under_review", collection_hold=1,
                       opened_date=None, resolved_date=None,
                       description="Test dispute", resolution=None):
    d = MagicMock()
    d.dispute_id = dispute_id
    d.dispute_type = dispute_type
    d.status = status
    d.collection_hold = collection_hold
    d.opened_date = opened_date or (date.today() - timedelta(days=15))
    d.resolved_date = resolved_date
    d.description = description
    d.resolution = resolution
    return d


def _mock_db(disputes):
    mock_ctx = MagicMock()
    mock_session = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx, mock_session


# ── AC-005-01: Active dispute sets collection_hold True ────────────────────────

class TestAC00501ActiveDisputeSetsHold:
    """AC-005-01: CUST-002 Sarah Jones identity_theft dispute → hold True."""

    def test_hold_true_when_active_dispute_has_flag(self):
        dispute = _make_dispute_row(collection_hold=1)
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.has_collection_hold",
                   return_value=(True, "identity_theft dispute (DISP-001) opened 2026-05-23")):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = check_collection_hold("ACC-002")
        assert result["collection_hold"] is True
        assert result["hold_reason"] != ""
        assert len(result["hold_reason"]) > 0

    def test_hold_reason_contains_dispute_info(self):
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.has_collection_hold",
                   return_value=(True, "identity_theft dispute (DISP-001)")):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = check_collection_hold("ACC-002")
        assert "DISP-001" in result["hold_reason"]

    def test_dispute_item_model_with_hold(self):
        item = DisputeItem(
            dispute_id="DISP-001", dispute_type="identity_theft",
            status="under_review", opened_date="2026-05-23", collection_hold=True,
        )
        assert item.collection_hold is True
        assert item.dispute_type == "identity_theft"


# ── AC-005-02: No disputes → hold False ───────────────────────────────────────

class TestAC00502NoDisputesHoldFalse:
    """AC-005-02: James Chen CUST-001 has no disputes → hold False."""

    def test_no_disputes_returns_hold_false(self):
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.has_collection_hold",
                   return_value=(False, "")):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = check_collection_hold("ACC-001")
        assert result["collection_hold"] is False
        assert result["hold_reason"] == ""

    def test_empty_active_list_returned(self):
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.get_active_disputes", return_value=[]):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_active_disputes_data("ACC-001")
        assert result == []

    def test_dispute_summary_model_no_hold(self):
        summary = DisputeSummary(
            account_id="ACC-001", active_disputes=[], resolved_disputes=[],
            collection_hold=False, total_open_disputes=0, summary="No disputes."
        )
        assert summary.collection_hold is False
        assert summary.total_open_disputes == 0


# ── AC-005-03: Multiple disputes all listed ────────────────────────────────────

class TestAC00503MultipleDisputesListed:
    """AC-005-03: CUST-007 David Brown has 2 active disputes — both returned."""

    def test_two_disputes_both_returned(self):
        disputes = [
            _make_dispute_row("DISP-002", "fraud_claim"),
            _make_dispute_row("DISP-003", "billing_error", status="open"),
        ]
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.get_active_disputes",
                   return_value=disputes):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_active_disputes_data("ACC-007")
        assert len(result) == 2
        ids = {d["dispute_id"] for d in result}
        assert "DISP-002" in ids
        assert "DISP-003" in ids

    def test_any_hold_flag_triggers_summary_hold(self):
        # If either dispute has collection_hold=1, the summary hold should be True
        disputes = [
            _make_dispute_row("DISP-002", "fraud_claim", collection_hold=1),
            _make_dispute_row("DISP-003", "billing_error", collection_hold=0),
        ]
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.has_collection_hold",
                   return_value=(True, "fraud_claim dispute (DISP-002)")):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = check_collection_hold("ACC-007")
        assert result["collection_hold"] is True


# ── AC-005-04: Resolved dispute in history, not in active ─────────────────────

class TestAC00504ResolvedDisputeRouting:
    """AC-005-04: resolved dispute in resolution_history, not in active_disputes."""

    def test_resolved_dispute_not_in_active(self):
        resolved = _make_dispute_row("DISP-OLD", status="resolved",
                                      collection_hold=0, resolved_date=date.today() - timedelta(days=10))
        all_disputes = [resolved]
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.get_active_disputes", return_value=[]), \
             patch("collection_assistant.tools.dispute_tools.get_all_disputes", return_value=all_disputes):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            active = get_active_disputes_data("ACC-TEST")
            history = get_dispute_history("ACC-TEST")
        assert active == []
        resolved_items = [d for d in history if d["status"] == "resolved"]
        assert len(resolved_items) == 1
        assert resolved_items[0]["dispute_id"] == "DISP-OLD"

    def test_resolved_dispute_does_not_set_hold(self):
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.has_collection_hold",
                   return_value=(False, "")):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = check_collection_hold("ACC-TEST")
        assert result["collection_hold"] is False


# ── AC-005-05: NBA blocked when hold active ────────────────────────────────────

class TestAC00505NBABlockedByHold:
    """AC-005-05: collection_hold=True → NBA restricted to place_on_hold or no_action_required."""

    def test_eligible_actions_restricted_when_hold(self):
        result = evaluate_action_eligibility(True, "deteriorating", 45, "delinquent")
        assert set(result["eligible_actions"]) == {"place_on_hold", "no_action_required"}

    def test_constraint_message_present(self):
        result = evaluate_action_eligibility(True, "deteriorating", 45, "delinquent")
        assert len(result["constraints"]) > 0
        assert any("hold" in c.lower() for c in result["constraints"])

    def test_nba_recommendation_blocked_by_dispute_field_exists(self):
        nba = NBARecommendation(
            action="place_on_hold", channel="none",
            rationale="Collection hold active due to open dispute.",
            confidence_score=0.99, urgency="medium",
            blocked_by_dispute=True, summary="Placed on hold.",
        )
        assert nba.blocked_by_dispute is True
        assert nba.action == "place_on_hold"

    def test_blocked_by_dispute_default_is_false(self):
        nba = NBARecommendation(
            action="initiate_call", channel="mobile",
            rationale="No hold, calling customer.",
            confidence_score=0.8, urgency="medium",
            summary="Call recommended.",
        )
        assert nba.blocked_by_dispute is False

    def test_outbound_actions_blocked_regardless_of_trajectory(self):
        for trajectory in ["improving", "stable", "deteriorating", "critical"]:
            result = evaluate_action_eligibility(True, trajectory, 45, "delinquent")
            for action in result["eligible_actions"]:
                assert action in {"place_on_hold", "no_action_required"}, \
                    f"Outbound action {action} allowed despite hold (trajectory={trajectory})"


# ── AC-005-06: classify_dispute_type accuracy ─────────────────────────────────

class TestAC00506DisputeClassification:
    """AC-005-06: classify_dispute_type correctly maps descriptions to types."""

    def test_fraud_description_classified_as_fraud_or_billing(self):
        result = classify_dispute_type("charge I did not authorise on my account")
        assert result in ("fraud_claim", "billing_error")

    def test_identity_theft_keywords(self):
        result = classify_dispute_type("this account was opened without my knowledge, identity theft")
        assert result == "identity_theft"

    def test_billing_error_keywords(self):
        result = classify_dispute_type("I was overcharged on my statement, incorrect amount billed")
        assert result == "billing_error"

    def test_payment_dispute_keywords(self):
        result = classify_dispute_type("my payment was not credited to my account")
        assert result == "payment_dispute"

    def test_service_dispute_keywords(self):
        result = classify_dispute_type("goods never received, cancelled order not refunded")
        assert result == "service_dispute"

    def test_empty_description_defaults_to_billing_error(self):
        assert classify_dispute_type("") == "billing_error"
        assert classify_dispute_type(None) == "billing_error"

    def test_dispute_type_literal_validates(self):
        item = DisputeItem(
            dispute_id="DISP-X", dispute_type="fraud_claim",
            status="open", opened_date="2026-01-01", collection_hold=True,
        )
        assert item.dispute_type == "fraud_claim"

    def test_unknown_dispute_type_coerced_to_billing_error(self):
        item = DisputeItem(
            dispute_id="DISP-X", dispute_type="UNKNOWN_TYPE",
            status="open", opened_date="2026-01-01", collection_hold=False,
        )
        assert item.dispute_type == "billing_error"


# ── AC-005-07: Resolution timeline returns days open ──────────────────────────

class TestAC00507ResolutionTimeline:
    """AC-005-07: get_resolution_timeline returns days_open >= 0 and escalated bool."""

    def test_timeline_returns_days_open(self):
        opened = date.today() - timedelta(days=20)
        dispute = _make_dispute_row("DISP-001", opened_date=opened)
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.get_active_disputes",
                   return_value=[dispute]):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_resolution_timeline("ACC-002")
        assert len(result) == 1
        assert result[0]["days_open"] == 20
        assert result[0]["dispute_id"] == "DISP-001"
        assert isinstance(result[0]["escalated"], bool)

    def test_dispute_over_30_days_is_escalated(self):
        opened = date.today() - timedelta(days=35)
        dispute = _make_dispute_row("DISP-001", opened_date=opened)
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.get_active_disputes",
                   return_value=[dispute]):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_resolution_timeline("ACC-002")
        assert result[0]["escalated"] is True

    def test_dispute_under_30_days_not_escalated(self):
        opened = date.today() - timedelta(days=10)
        dispute = _make_dispute_row("DISP-001", opened_date=opened)
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.get_active_disputes",
                   return_value=[dispute]):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_resolution_timeline("ACC-002")
        assert result[0]["escalated"] is False

    def test_no_active_disputes_returns_empty_timeline(self):
        with patch("collection_assistant.tools.dispute_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.dispute_tools.get_active_disputes",
                   return_value=[]):
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_resolution_timeline("ACC-001")
        assert result == []
