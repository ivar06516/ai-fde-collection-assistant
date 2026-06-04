from sqlalchemy.orm import Session
from collection_assistant.db.models import Dispute


def get_active_disputes(session: Session, account_id: str) -> list[Dispute]:
    return (
        session.query(Dispute)
        .filter(Dispute.account_id == account_id, Dispute.status.in_(["open", "under_review", "escalated"]))
        .order_by(Dispute.opened_date.desc())
        .all()
    )


def get_all_disputes(session: Session, account_id: str) -> list[Dispute]:
    return (
        session.query(Dispute)
        .filter(Dispute.account_id == account_id)
        .order_by(Dispute.opened_date.desc())
        .all()
    )


def has_collection_hold(session: Session, account_id: str) -> tuple[bool, str]:
    active = get_active_disputes(session, account_id)
    for d in active:
        if d.collection_hold:
            return True, f"{d.dispute_type} dispute ({d.dispute_id}) opened {d.opened_date}"
    return False, ""
