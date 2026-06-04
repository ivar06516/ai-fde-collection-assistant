from datetime import date
from collection_assistant.db.session import db_session
from collection_assistant.db.queries.dispute_queries import get_active_disputes, get_all_disputes, has_collection_hold

DISPUTE_KEYWORDS: dict[str, list[str]] = {
    "fraud_claim": ["fraud", "did not authorise", "unauthorised", "unauthorized", "did not make",
                    "fraudulent", "not my transaction", "scam"],
    "identity_theft": ["identity theft", "not me", "stolen identity", "someone else",
                       "my details were used", "account opened without"],
    "billing_error": ["charge", "incorrect amount", "overcharged", "wrong amount",
                      "billing", "duplicate charge", "error on statement", "misapplied"],
    "payment_dispute": ["payment", "not credited", "paid already", "payment not received",
                        "payment missing", "direct debit"],
    "service_dispute": ["service", "product", "goods", "never received", "not delivered",
                        "poor service", "cancelled"],
}

ESCALATION_THRESHOLD_DAYS = 30


def classify_dispute_type(description: str) -> str:
    """Classify dispute type from description text using keyword matching."""
    if not description:
        return "billing_error"
    text = description.lower()
    scores: dict[str, int] = {k: 0 for k in DISPUTE_KEYWORDS}
    for dtype, keywords in DISPUTE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[dtype] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "billing_error"


def get_resolution_timeline(account_id: str) -> list:
    """Return days_open and escalation status for each active dispute."""
    today = date.today()
    with db_session() as session:
        disputes = get_active_disputes(session, account_id)
        return [
            {
                "dispute_id": d.dispute_id,
                "dispute_type": d.dispute_type,
                "status": d.status,
                "days_open": (today - d.opened_date).days if d.opened_date else 0,
                "escalated": (today - d.opened_date).days > ESCALATION_THRESHOLD_DAYS if d.opened_date else False,
                "collection_hold": bool(d.collection_hold),
            }
            for d in disputes
        ]


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
