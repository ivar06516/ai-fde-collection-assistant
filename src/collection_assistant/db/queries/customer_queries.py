from sqlalchemy.orm import Session
from collection_assistant.db.models import Customer, InteractionHistory
from collection_assistant.exceptions import CustomerNotFoundError


def get_customer(session: Session, customer_id: str) -> Customer:
    customer = session.get(Customer, customer_id)
    if not customer:
        raise CustomerNotFoundError(customer_id)
    return customer


def get_interaction_history(session: Session, customer_id: str, limit: int = 20) -> list[InteractionHistory]:
    return (
        session.query(InteractionHistory)
        .filter(InteractionHistory.customer_id == customer_id)
        .order_by(InteractionHistory.interaction_date.desc())
        .limit(limit)
        .all()
    )


def list_customers(session: Session) -> list[tuple[str, str]]:
    rows = session.query(Customer.customer_id, Customer.first_name, Customer.last_name).all()
    return [(r.customer_id, f"{r.first_name} {r.last_name}") for r in rows]
