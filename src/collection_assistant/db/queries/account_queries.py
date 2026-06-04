from typing import Optional
from sqlalchemy.orm import Session
from collection_assistant.db.models import Account, PaymentHistory
from collection_assistant.exceptions import AccountNotFoundError


def get_account(session: Session, account_id: str) -> Account:
    account = session.get(Account, account_id)
    if not account:
        raise AccountNotFoundError(account_id)
    return account


def get_payment_history(session: Session, account_id: str, months: int = 12) -> list[PaymentHistory]:
    return (
        session.query(PaymentHistory)
        .filter(PaymentHistory.account_id == account_id)
        .order_by(PaymentHistory.payment_month.desc())
        .limit(months)
        .all()
    )


def get_accounts_for_customer(session: Session, customer_id: str) -> list[Account]:
    return session.query(Account).filter(Account.customer_id == customer_id).all()


def list_accounts(session: Session) -> list[tuple[str, str]]:
    rows = session.query(Account.account_id, Account.product_type, Account.customer_id).all()
    return [(r.account_id, f"{r.account_id} ({r.product_type})") for r in rows]
