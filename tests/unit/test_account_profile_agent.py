"""UC-003: Account Profile Agent — unit tests covering AC-003-01 through AC-003-06."""
import time
import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from collection_assistant.models.account import AccountProfile
from collection_assistant.tools.account_tools import (
    get_account_balance,
    get_delinquency_status,
    get_linked_accounts,
    get_payment_history_summary,
)
from collection_assistant.exceptions import AccountNotFoundError


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_account(
    account_id="ACC-001",
    customer_id="CUST-001",
    product_type="personal_loan",
    account_status="current",
    outstanding_balance=4500.0,
    original_balance=15000.0,
    credit_limit=None,
    interest_rate=12.5,
    days_past_due=0,
    delinquency_start=None,
    last_payment_date=None,
    last_payment_amount=375.0,
    next_due_date=None,
    next_due_amount=375.0,
    opened_date=None,
):
    a = MagicMock()
    a.account_id = account_id
    a.customer_id = customer_id
    a.product_type = product_type
    a.account_status = account_status
    a.outstanding_balance = outstanding_balance
    a.original_balance = original_balance
    a.credit_limit = credit_limit
    a.interest_rate = interest_rate
    a.days_past_due = days_past_due
    a.delinquency_start = delinquency_start
    a.last_payment_date = last_payment_date or date(2026, 5, 1)
    a.last_payment_amount = last_payment_amount
    a.next_due_date = next_due_date or date(2026, 7, 1)
    a.next_due_amount = next_due_amount
    a.opened_date = opened_date or date(2021, 1, 1)
    return a


def _make_payment_row(month, amount_due=500.0, amount_paid=500.0, on_time=1, payment_date=None):
    p = MagicMock()
    p.payment_month = month
    p.amount_due = amount_due
    p.amount_paid = amount_paid
    p.on_time = on_time
    p.payment_date = payment_date or date(2026, 1, 15)
    return p


def _mock_session_with_account(account):
    mock_ctx = MagicMock()
    mock_session = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    mock_session.get.return_value = account
    return mock_ctx, mock_session


# ── AC-003-01: Balance and DPD retrieved correctly ─────────────────────────────

class TestAC00301BalanceDPD:
    """AC-003-01: get_account_balance and get_delinquency_status return correct values."""

    def test_outstanding_balance_returned(self):
        account = _make_account(outstanding_balance=4500.0, original_balance=15000.0)
        mock_ctx, _ = _mock_session_with_account(account)
        with patch("collection_assistant.tools.account_tools.db_session", return_value=mock_ctx):
            result = get_account_balance("ACC-001")
        assert result["outstanding_balance"] == 4500.0
        assert result["original_balance"] == 15000.0

    def test_dpd_zero_for_current_account(self):
        account = _make_account(days_past_due=0, account_status="current")
        mock_ctx, _ = _mock_session_with_account(account)
        with patch("collection_assistant.tools.account_tools.db_session", return_value=mock_ctx):
            result = get_delinquency_status("ACC-001")
        assert result["days_past_due"] == 0
        assert result["account_status"] == "current"
        assert result["delinquency_start"] is None

    def test_dpd_populated_for_delinquent_account(self):
        account = _make_account(days_past_due=45, account_status="delinquent",
                                 delinquency_start=date(2026, 4, 15))
        mock_ctx, _ = _mock_session_with_account(account)
        with patch("collection_assistant.tools.account_tools.db_session", return_value=mock_ctx):
            result = get_delinquency_status("ACC-003")
        assert result["days_past_due"] == 45
        assert result["account_status"] == "delinquent"
        assert result["delinquency_start"] == "2026-04-15"

    def test_product_type_returned(self):
        account = _make_account(product_type="credit_card")
        mock_ctx, _ = _mock_session_with_account(account)
        with patch("collection_assistant.tools.account_tools.db_session", return_value=mock_ctx):
            result = get_account_balance("ACC-002")
        assert result["product_type"] == "credit_card"


# ── AC-003-02: Payment history 12 months ──────────────────────────────────────

class TestAC00302PaymentHistory:
    """AC-003-02: payment_history contains up to 12 months, each with required fields."""

    def test_twelve_months_returned(self):
        months = [_make_payment_row(f"2026-{12-i:02d}") for i in range(12)]
        with patch("collection_assistant.tools.account_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.account_tools.get_payment_history", return_value=months):
            mock_session = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_payment_history_summary("ACC-001")
        assert len(result["months"]) == 12

    def test_each_entry_has_required_keys(self):
        months = [_make_payment_row("2026-05")]
        with patch("collection_assistant.tools.account_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.account_tools.get_payment_history", return_value=months):
            mock_session = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_payment_history_summary("ACC-001")
        entry = result["months"][0]
        assert "month" in entry
        assert "amount_due" in entry
        assert "amount_paid" in entry
        assert "on_time" in entry

    def test_empty_history_returns_zero_rate(self):
        with patch("collection_assistant.tools.account_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.account_tools.get_payment_history", return_value=[]):
            mock_session = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_payment_history_summary("ACC-001")
        assert result["months"] == []
        assert result["on_time_rate"] == 1.0
        assert result["missed_last_6m"] == 0


# ── AC-003-03: Account status Literal constraint ───────────────────────────────

class TestAC00303AccountStatus:
    """AC-003-03: AccountProfile.account_status accepts only the 5 valid values."""

    @pytest.mark.parametrize("status", ["current", "delinquent", "legal", "written_off", "closed"])
    def test_valid_statuses_accepted(self, status):
        profile = AccountProfile(
            account_id="ACC-001", customer_id="CUST-001",
            product_type="personal_loan", account_status=status,
            outstanding_balance=4500.0, original_balance=15000.0,
            days_past_due=0, on_time_payment_rate=1.0,
            missed_payments_last_6m=0, summary="Test",
        )
        assert profile.account_status == status

    def test_invalid_status_coerced_to_delinquent(self):
        profile = AccountProfile(
            account_id="ACC-001", customer_id="CUST-001",
            product_type="personal_loan", account_status="UNKNOWN_STATUS",
            outstanding_balance=4500.0, original_balance=15000.0,
            days_past_due=0, on_time_payment_rate=1.0,
            missed_payments_last_6m=0, summary="Test",
        )
        assert profile.account_status == "delinquent"

    def test_status_case_insensitive(self):
        profile = AccountProfile(
            account_id="ACC-001", customer_id="CUST-001",
            product_type="personal_loan", account_status="WRITTEN_OFF",
            outstanding_balance=4500.0, original_balance=15000.0,
            days_past_due=0, on_time_payment_rate=1.0,
            missed_payments_last_6m=0, summary="Test",
        )
        assert profile.account_status == "written_off"


# ── AC-003-04: on_time flag mapping ───────────────────────────────────────────

class TestAC00304OnTimeFlag:
    """AC-003-04: on_time = 0 in DB maps to on_time = False in output."""

    def test_on_time_zero_maps_to_false(self):
        missed = _make_payment_row("2026-04", amount_paid=0.0, on_time=0)
        with patch("collection_assistant.tools.account_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.account_tools.get_payment_history",
                   return_value=[missed]):
            mock_session = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_payment_history_summary("ACC-001")
        assert result["months"][0]["on_time"] is False

    def test_on_time_one_maps_to_true(self):
        paid = _make_payment_row("2026-05", on_time=1)
        with patch("collection_assistant.tools.account_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.account_tools.get_payment_history",
                   return_value=[paid]):
            mock_session = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_payment_history_summary("ACC-001")
        assert result["months"][0]["on_time"] is True

    def test_missed_count_calculated_from_last_6m(self):
        rows = [_make_payment_row(f"2026-{6-i:02d}", on_time=(0 if i < 3 else 1)) for i in range(6)]
        with patch("collection_assistant.tools.account_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.account_tools.get_payment_history", return_value=rows):
            mock_session = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = get_payment_history_summary("ACC-001")
        assert result["missed_last_6m"] == 3


# ── AC-003-05: Special statuses do not block pipeline ─────────────────────────

class TestAC00305SpecialStatuses:
    """AC-003-05: written_off and legal account statuses are profiled without error."""

    @pytest.mark.parametrize("status", ["written_off", "legal", "closed"])
    def test_special_status_profile_builds_without_error(self, status):
        account = _make_account(account_status=status, days_past_due=120)
        mock_ctx, _ = _mock_session_with_account(account)
        with patch("collection_assistant.tools.account_tools.db_session", return_value=mock_ctx):
            result = get_delinquency_status("ACC-008")
        assert result["account_status"] == status

    def test_written_off_status_preserved_in_model(self):
        profile = AccountProfile(
            account_id="ACC-X", customer_id="CUST-X",
            product_type="personal_loan", account_status="written_off",
            outstanding_balance=22000.0, original_balance=25000.0,
            days_past_due=120, on_time_payment_rate=0.3,
            missed_payments_last_6m=5, summary="Written off account",
        )
        assert profile.account_status == "written_off"

    def test_account_not_found_raises_error(self):
        mock_ctx = MagicMock()
        mock_session = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = None
        with patch("collection_assistant.tools.account_tools.db_session", return_value=mock_ctx):
            with pytest.raises(AccountNotFoundError) as exc_info:
                get_account_balance("ACC-INVALID")
        assert "ACC-INVALID" in str(exc_info.value)


# ── AC-003-06: DB query timing ────────────────────────────────────────────────

class TestAC00306DBQueryTiming:
    """AC-003-06: get_payment_history tool completes in < 500ms."""

    def test_payment_history_query_under_500ms(self):
        rows = [_make_payment_row(f"2026-{12-i:02d}") for i in range(12)]
        with patch("collection_assistant.tools.account_tools.db_session") as mock_ctx, \
             patch("collection_assistant.tools.account_tools.get_payment_history", return_value=rows):
            mock_session = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            start = time.perf_counter()
            get_payment_history_summary("ACC-001")
            elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500, f"Query took {elapsed_ms:.1f}ms — expected < 500ms"


# ── get_linked_accounts tool ──────────────────────────────────────────────────

class TestGetLinkedAccounts:
    """get_linked_accounts returns other accounts for the same customer."""

    def test_linked_accounts_excludes_self(self):
        main_account = _make_account(account_id="ACC-001", customer_id="CUST-001")
        other_account = _make_account(account_id="ACC-099", customer_id="CUST-001",
                                       product_type="credit_card")
        mock_ctx = MagicMock()
        mock_session = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = main_account
        with patch("collection_assistant.tools.account_tools.db_session", return_value=mock_ctx), \
             patch("collection_assistant.tools.account_tools.get_accounts_for_customer",
                   return_value=[main_account, other_account]):
            result = get_linked_accounts("ACC-001")
        assert result["count"] == 1
        assert result["linked_accounts"][0]["account_id"] == "ACC-099"

    def test_no_linked_accounts_returns_empty_list(self):
        main_account = _make_account(account_id="ACC-001", customer_id="CUST-001")
        mock_ctx = MagicMock()
        mock_session = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = main_account
        with patch("collection_assistant.tools.account_tools.db_session", return_value=mock_ctx), \
             patch("collection_assistant.tools.account_tools.get_accounts_for_customer",
                   return_value=[main_account]):
            result = get_linked_accounts("ACC-001")
        assert result["count"] == 0
        assert result["linked_accounts"] == []
