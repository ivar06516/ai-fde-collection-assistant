from pydantic import BaseModel


NBA_ACTIONS = [
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


class AlternativeAction(BaseModel):
    action: str
    rationale: str
    confidence: float


class NBARecommendation(BaseModel):
    action: str
    channel: str
    rationale: str
    confidence_score: float
    urgency: str   # low | medium | high | critical
    alternative_actions: list[AlternativeAction] = []
    policy_constraints_applied: list[str] = []
    blocked_by_dispute: bool = False  # True when collection_hold forced the action
    summary: str
