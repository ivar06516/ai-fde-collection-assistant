from typing import Literal, Optional
from pydantic import BaseModel, field_validator

DisputeType = Literal[
    "billing_error", "fraud_claim", "identity_theft",
    "service_dispute", "payment_dispute",
]
DisputeStatus = Literal["open", "under_review", "resolved", "escalated"]


class DisputeItem(BaseModel):
    dispute_id: str
    dispute_type: DisputeType
    status: str
    opened_date: str
    resolved_date: Optional[str] = None
    description: Optional[str] = None
    collection_hold: bool
    resolution: Optional[str] = None
    days_open: Optional[int] = None
    escalated: bool = False

    @field_validator("dispute_type", mode="before")
    @classmethod
    def normalise_dispute_type(cls, v: str) -> str:
        clean = str(v).lower().strip()
        valid = {"billing_error", "fraud_claim", "identity_theft", "service_dispute", "payment_dispute"}
        return clean if clean in valid else "billing_error"


class DisputeSummary(BaseModel):
    account_id: str
    active_disputes: list[DisputeItem] = []
    resolved_disputes: list[DisputeItem] = []
    collection_hold: bool
    hold_reason: Optional[str] = None
    total_open_disputes: int
    summary: str
