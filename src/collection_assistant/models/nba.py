from typing import Literal
from pydantic import BaseModel, field_validator

NBAAction = Literal[
    "initiate_call",
    "send_sms",
    "send_email",
    "offer_payment_plan",
    "offer_settlement",
    "place_on_hold",
    "escalate_to_legal",
    "flag_for_writeoff",
    "no_action_required",
]

NBAUrgency = Literal["low", "medium", "high", "critical"]

NBA_ACTIONS: list[str] = list(NBAAction.__args__)  # type: ignore[attr-defined]


class AlternativeAction(BaseModel):
    action: str
    rationale: str
    confidence: float

    @field_validator("action", mode="before")
    @classmethod
    def normalise_action(cls, v: str) -> str:
        clean = str(v).lower().strip().replace(" ", "_")
        return clean if clean in NBA_ACTIONS else "no_action_required"


class NBARecommendation(BaseModel):
    action: NBAAction
    channel: str
    rationale: str
    confidence_score: float
    urgency: NBAUrgency
    alternative_actions: list[AlternativeAction] = []
    policy_constraints_applied: list[str] = []
    blocked_by_dispute: bool = False  # True when collection_hold forced the action
    summary: str

    @field_validator("action", mode="before")
    @classmethod
    def normalise_action(cls, v: str) -> str:
        clean = str(v).lower().strip().replace(" ", "_")
        return clean if clean in NBA_ACTIONS else "no_action_required"

    @field_validator("urgency", mode="before")
    @classmethod
    def normalise_urgency(cls, v: str) -> str:
        clean = str(v).lower().strip()
        return clean if clean in ("low", "medium", "high", "critical") else "medium"

    @field_validator("confidence_score", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return round(min(max(float(v), 0.0), 1.0), 4)
