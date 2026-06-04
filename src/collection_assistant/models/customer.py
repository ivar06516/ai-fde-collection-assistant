from typing import Literal, Optional
from pydantic import BaseModel, field_validator

RiskSegment = Literal["low", "medium", "high", "hardship"]
PreferredChannel = Literal["mobile", "email", "post"]
PreferredTime = Literal["morning", "afternoon", "evening"]


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
    risk_segment: RiskSegment
    hardship_flag: bool
    hardship_reason: Optional[str] = None
    prior_collection_interactions: int
    last_interaction_outcome: Optional[str] = None
    behavioural_signals: list[str] = []
    summary: str

    @field_validator("risk_segment", mode="before")
    @classmethod
    def normalise_risk_segment(cls, v: str) -> str:
        clean = str(v).lower().strip()
        valid = {"low", "medium", "high", "hardship"}
        return clean if clean in valid else "medium"
