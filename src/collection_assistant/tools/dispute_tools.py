from collection_assistant.db.session import db_session
from collection_assistant.db.queries.dispute_queries import get_active_disputes, get_all_disputes, has_collection_hold


def get_active_disputes_data(account_id: str) -> list:
    with db_session() as session:
        disputes = get_active_disputes(session, account_id)
        return [
            {"dispute_id": d.dispute_id, "dispute_type": d.dispute_type, "status": d.status,
             "opened_date": str(d.opened_date), "description": d.description,
             "collection_hold": bool(d.collection_hold)}
            for d in disputes
        ]


def get_dispute_history(account_id: str) -> list:
    with db_session() as session:
        disputes = get_all_disputes(session, account_id)
        return [
            {"dispute_id": d.dispute_id, "dispute_type": d.dispute_type, "status": d.status,
             "opened_date": str(d.opened_date),
             "resolved_date": str(d.resolved_date) if d.resolved_date else None,
             "resolution": d.resolution, "collection_hold": bool(d.collection_hold)}
            for d in disputes
        ]


def check_collection_hold(account_id: str) -> dict:
    with db_session() as session:
        hold, reason = has_collection_hold(session, account_id)
        return {"collection_hold": hold, "hold_reason": reason}
