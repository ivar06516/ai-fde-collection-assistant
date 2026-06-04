from collection_assistant.db.session import db_session
from collection_assistant.db.queries.account_queries import (
    get_account, get_accounts_for_customer, get_payment_history,
)


def get_account_balance(account_id: str) -> dict:
    with db_session() as session:
        a = get_account(session, account_id)
        return {
            "account_id": a.account_id,
            "product_type": a.product_type,
            "account_status": a.account_status,
            "outstanding_balance": a.outstanding_balance,
            "original_balance": a.original_balance,
            "credit_limit": a.credit_limit,
            "interest_rate": a.interest_rate,
        }


def get_delinquency_status(account_id: str) -> dict:
    with db_session() as session:
        a = get_account(session, account_id)
        return {
            "days_past_due": a.days_past_due,
            "delinquency_start": str(a.delinquency_start) if a.delinquency_start else None,
            "account_status": a.account_status,
        }


def get_linked_accounts(account_id: str) -> dict:
    """Return other accounts held by the same customer."""
    with db_session() as session:
        account = get_account(session, account_id)
        all_accounts = get_accounts_for_customer(session, account.customer_id)
        linked = [
            {"account_id": a.account_id, "product_type": a.product_type,
             "account_status": a.account_status, "outstanding_balance": a.outstanding_balance}
            for a in all_accounts
            if a.account_id != account_id
        ]
        return {"customer_id": account.customer_id, "linked_accounts": linked, "count": len(linked)}


def get_payment_history_summary(account_id: str) -> dict:
    with db_session() as session:
        history = get_payment_history(session, account_id, months=12)
        if not history:
            return {"months": [], "on_time_rate": 1.0, "missed_last_6m": 0}
        months = [
            {"month": h.payment_month, "amount_due": h.amount_due,
             "amount_paid": h.amount_paid, "on_time": bool(h.on_time)}
            for h in history
        ]
        on_time_count = sum(1 for h in history if h.on_time)
        missed_6m = sum(1 for h in history[:6] if not h.on_time)
        return {
            "months": months,
            "on_time_rate": round(on_time_count / len(history), 2),
            "missed_last_6m": missed_6m,
            "last_payment_date": str(history[0].payment_date) if history[0].payment_date else None,
            "last_payment_amount": history[0].amount_paid,
        }
