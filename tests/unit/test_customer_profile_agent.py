"""UC-002: Customer Profile Agent — unit tests covering AC-002-01 through AC-002-05."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone

from collection_assistant.models.customer import CustomerProfile
from collection_assistant.tools.customer_tools import (
    get_customer_demographics,
    get_contact_preferences,
    get_interaction_history_summary,
    detect_hardship_signals,
)
from collection_assistant.exceptions import CustomerNotFoundError


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_customer(
    customer_id="CUST-001",
    first_name="James",
    last_name="Chen",
    risk_segment="low",
    hardship_flag=0,
    hardship_reason=None,
    preferred_channel="mobile",
    preferred_time="morning",
    employment_status="employed",
    annual_income=103200.0,
    city="London",
    state="Greater London",
    relationship_since=None,
    age=27,
):
    c = MagicMock()
    c.customer_id = customer_id
    c.first_name = first_name
    c.last_name = last_name
    c.age = age
    c.gender = "M"
    c.email = f"{first_name.lower()}@example.com"
    c.mobile_number = "+44 7700 900001"
    c.city = city
    c.state = state
    c.postcode = "EC1A 1BB"
    c.employment_status = employment_status
    c.annual_income = annual_income
    c.relationship_since = relationship_since or date(2018, 1, 1)
    c.risk_segment = risk_segment
    c.preferred_channel = preferred_channel
    c.preferred_time = preferred_time
    c.hardship_flag = hardship_flag
    c.hardship_reason = hardship_reason
    return c


def _make_interaction(outcome="contacted"):
    i = MagicMock()
    i.interaction_type = "call"
    i.interaction_date = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    i.outcome = outcome
    i.agent_notes = "Called customer"
    return i


# ── AC-002-01: Demographics correctly retrieved ────────────────────────────────

class TestAC00201Demographics:
    """AC-002-01: get_customer_demographics returns correct fields for CUST-001 James Chen."""

    def test_demographics_full_name(self):
        mock_customer = _make_customer()
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = mock_customer
            result = get_customer_demographics("CUST-001")
        assert result["full_name"] == "James Chen"
        assert result["customer_id"] == "CUST-001"

    def test_demographics_preferred_channel_and_time(self):
        mock_customer = _make_customer(preferred_channel="mobile", preferred_time="morning")
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = mock_customer
            prefs = get_contact_preferences("CUST-001")
        assert prefs["preferred_channel"] == "mobile"
        assert prefs["preferred_time"] == "morning"

    def test_demographics_tenure_is_positive(self):
        mock_customer = _make_customer(relationship_since=date(2018, 6, 1))
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = mock_customer
            result = get_customer_demographics("CUST-001")
        assert result["relationship_tenure_years"] > 0

    def test_demographics_includes_risk_segment(self):
        mock_customer = _make_customer(risk_segment="low")
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = mock_customer
            result = get_customer_demographics("CUST-001")
        assert result["risk_segment"] == "low"
        assert "hardship_flag" in result
        assert "hardship_reason" in result


# ── AC-002-02: Risk segment Literal constraint ─────────────────────────────────

class TestAC00202RiskSegment:
    """AC-002-02: CustomerProfile.risk_segment accepts only low/medium/high/hardship."""

    @pytest.mark.parametrize("valid_segment", ["low", "medium", "high", "hardship"])
    def test_valid_risk_segments_accepted(self, valid_segment):
        profile = CustomerProfile(
            customer_id="CUST-001", full_name="James Chen", age=27,
            employment_status="employed", annual_income=103200.0,
            city="London", state="Greater London",
            preferred_channel="mobile", preferred_time="morning",
            relationship_tenure_years=6.3, risk_segment=valid_segment,
            hardship_flag=False, prior_collection_interactions=3,
            summary="Test summary",
        )
        assert profile.risk_segment == valid_segment

    def test_invalid_risk_segment_coerced_to_medium(self):
        # The field_validator normalises unknown values to "medium"
        profile = CustomerProfile(
            customer_id="CUST-001", full_name="James Chen", age=27,
            employment_status="employed", annual_income=103200.0,
            city="London", state="Greater London",
            preferred_channel="mobile", preferred_time="morning",
            relationship_tenure_years=6.3, risk_segment="UNKNOWN_VALUE",
            hardship_flag=False, prior_collection_interactions=3,
            summary="Test summary",
        )
        assert profile.risk_segment == "medium"

    def test_risk_segment_case_insensitive(self):
        profile = CustomerProfile(
            customer_id="CUST-001", full_name="James Chen", age=27,
            employment_status="employed", annual_income=103200.0,
            city="London", state="Greater London",
            preferred_channel="mobile", preferred_time="morning",
            relationship_tenure_years=6.3, risk_segment="HIGH",
            hardship_flag=False, prior_collection_interactions=3,
            summary="Test summary",
        )
        assert profile.risk_segment == "high"


# ── AC-002-03: Hardship flag surfaces correctly ────────────────────────────────

class TestAC00203HardshipFlag:
    """AC-002-03: Emma Patel CUST-004 hardship_flag=1, reason=unemployment surfaces correctly."""

    def test_hardship_signals_returned_for_flagged_customer(self):
        mock_customer = _make_customer(
            customer_id="CUST-004",
            first_name="Emma", last_name="Patel",
            risk_segment="hardship",
            hardship_flag=1,
            hardship_reason="unemployment",
            employment_status="unemployed",
        )
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = mock_customer
            result = detect_hardship_signals("CUST-004")
        assert result["hardship_flag"] is True
        assert result["hardship_reason"] == "unemployment"
        assert any("hardship" in s.lower() or "unemployment" in s.lower() for s in result["signals"])

    def test_risk_segment_preserved_as_hardship(self):
        mock_customer = _make_customer(
            customer_id="CUST-004", risk_segment="hardship",
            hardship_flag=1, hardship_reason="unemployment",
        )
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = mock_customer
            result = get_customer_demographics("CUST-004")
        assert result["risk_segment"] == "hardship"
        assert result["hardship_flag"] is True
        assert result["hardship_reason"] == "unemployment"

    def test_no_hardship_signals_for_clean_customer(self):
        mock_customer = _make_customer(hardship_flag=0, hardship_reason=None,
                                        employment_status="employed", annual_income=80000.0)
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = mock_customer
            result = detect_hardship_signals("CUST-001")
        assert result["hardship_flag"] is False
        assert result["signals"] == []


# ── AC-002-04: Interaction count matches DB ────────────────────────────────────

class TestAC00204InteractionCount:
    """AC-002-04: prior_collection_interactions count matches rows in DB."""

    def test_interaction_count_two_rows(self):
        interactions = [_make_interaction("contacted"), _make_interaction("promise_to_pay")]
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.customer_tools.get_interaction_history",
                   return_value=interactions):
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = get_interaction_history_summary("CUST-001")
        assert result["total_interactions"] == 2
        assert result["last_outcome"] == "contacted"

    def test_zero_interactions_returns_zero_count(self):
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.customer_tools.get_interaction_history",
                   return_value=[]):
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = get_interaction_history_summary("CUST-001")
        assert result["total_interactions"] == 0
        assert result["last_interaction"] is None
        assert result["last_outcome"] is None

    def test_interaction_count_five_rows(self):
        interactions = [_make_interaction(o) for o in
                        ["contacted", "no_answer", "promise_to_pay", "refused", "payment_arranged"]]
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.customer_tools.get_interaction_history",
                   return_value=interactions):
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = get_interaction_history_summary("CUST-001")
        assert result["total_interactions"] == 5


# ── AC-002-05: Missing customer raises CustomerNotFoundError ───────────────────

class TestAC00205MissingCustomer:
    """AC-002-05: CustomerNotFoundError raised for unknown customer_id."""

    def test_get_customer_raises_not_found(self):
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = None  # simulates missing customer
            with pytest.raises(CustomerNotFoundError) as exc_info:
                get_customer_demographics("CUST-INVALID")
        assert "CUST-INVALID" in str(exc_info.value)

    def test_contact_prefs_raises_not_found(self):
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = None
            with pytest.raises(CustomerNotFoundError):
                get_contact_preferences("CUST-INVALID")

    def test_hardship_signals_raises_not_found(self):
        with patch("collection_assistant.tools.customer_tools.db_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = None
            with pytest.raises(CustomerNotFoundError):
                detect_hardship_signals("CUST-INVALID")
