from typing import Optional
from pydantic import BaseModel


class CustomerProfile(BaseModel):
    customer_id: str
    full_name: str
    age: int
    employment_status: str
    annual_income: float
    city: str
    state: str
    preferred_channel: str
    preferred_time: str
    relationship_tenure_years: float
    risk_segment: str   # low | medium | high | hardship
    hardship_flag: bool
    hardship_reason: Optional[str] = None
    prior_collection_interactions: int
    last_interaction_outcome: Optional[str] = None
    behavioural_signals: list[str] = []
    summary: str
