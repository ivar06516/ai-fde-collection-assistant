from datetime import date
from collection_assistant.db.session import db_session
from collection_assistant.db.queries.customer_queries import get_customer, get_interaction_history


def get_customer_demographics(customer_id: str) -> dict:
    with db_session() as session:
        c = get_customer(session, customer_id)
        return {
            "customer_id": c.customer_id,
            "full_name": f"{c.first_name} {c.last_name}",
            "age": c.age,
            "gender": c.gender,
            "email": c.email,
            "mobile_number": c.mobile_number,
            "city": c.city,
            "state": c.state,
            "employment_status": c.employment_status,
            "annual_income": c.annual_income,
            "relationship_since": str(c.relationship_since),
            "relationship_tenure_years": round(
                (date.today() - c.relationship_since).days / 365.25, 1
            ),
            "risk_segment": c.risk_segment,
            "hardship_flag": bool(c.hardship_flag),
            "hardship_reason": c.hardship_reason,
        }


def get_contact_preferences(customer_id: str) -> dict:
    with db_session() as session:
        c = get_customer(session, customer_id)
        return {"preferred_channel": c.preferred_channel, "preferred_time": c.preferred_time}


def get_interaction_history_summary(customer_id: str) -> dict:
    with db_session() as session:
        interactions = get_interaction_history(session, customer_id)
        if not interactions:
            return {"total_interactions": 0, "last_interaction": None, "last_outcome": None, "outcomes": []}
        outcomes = [i.outcome for i in interactions if i.outcome]
        return {
            "total_interactions": len(interactions),
            "last_interaction": str(interactions[0].interaction_date),
            "last_outcome": interactions[0].outcome,
            "outcomes": outcomes[:5],
        }


def detect_hardship_signals(customer_id: str) -> dict:
    with db_session() as session:
        c = get_customer(session, customer_id)
        signals = []
        if c.hardship_flag:
            signals.append(f"Hardship flag active: {c.hardship_reason or 'unknown reason'}")
        if c.employment_status == "unemployed":
            signals.append("Currently unemployed")
        if c.annual_income and c.annual_income < 25000:
            signals.append("Low annual income")
        return {"hardship_flag": bool(c.hardship_flag), "hardship_reason": c.hardship_reason, "signals": signals}
