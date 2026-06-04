from typing import Optional
from pydantic import BaseModel


class DisputeItem(BaseModel):
    dispute_id: str
    dispute_type: str
    status: str
    opened_date: str
    resolved_date: Optional[str] = None
    description: Optional[str] = None
    collection_hold: bool
    resolution: Optional[str] = None


class DisputeSummary(BaseModel):
    account_id: str
    active_disputes: list[DisputeItem] = []
    resolved_disputes: list[DisputeItem] = []
    collection_hold: bool
    hold_reason: Optional[str] = None
    total_open_disputes: int
    summary: str
