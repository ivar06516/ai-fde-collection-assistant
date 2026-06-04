NBA_ACTION_CATALOGUE = [
    "initiate_call", "send_sms", "send_email", "offer_payment_plan",
    "offer_settlement", "place_on_hold", "escalate_to_legal",
    "flag_for_writeoff", "no_action_required",
]


def evaluate_action_eligibility(collection_hold: bool, arrears_trajectory: str,
                                  dpd: int, account_status: str) -> dict:
    eligible = list(NBA_ACTION_CATALOGUE)
    constraints = []
    if collection_hold:
        eligible = ["place_on_hold", "no_action_required"]
        constraints.append("Collection hold active: outbound contact not permitted")
    elif account_status == "legal":
        eligible = ["escalate_to_legal", "offer_settlement", "place_on_hold"]
        constraints.append("Account in legal status")
    elif account_status == "written_off":
        eligible = ["flag_for_writeoff", "offer_settlement", "no_action_required"]
        constraints.append("Account written off")
    return {"eligible_actions": eligible, "constraints": constraints}


def score_action_options(eligible_actions: list, trajectory: str, dpd: int,
                          default_probability: float, risk_segment: str) -> list:
    scores = {}
    for action in eligible_actions:
        score = 0.5
        if trajectory == "critical" and action in ("escalate_to_legal", "offer_settlement"):
            score = 0.9
        elif trajectory == "deteriorating" and action in ("initiate_call", "offer_payment_plan"):
            score = 0.85
        elif trajectory == "stable" and action in ("send_sms", "send_email"):
            score = 0.75
        elif trajectory == "improving" and action in ("send_sms", "no_action_required"):
            score = 0.8
        if dpd > 90 and action in ("escalate_to_legal", "offer_settlement"):
            score = min(score + 0.1, 0.99)
        if default_probability > 0.7 and action == "offer_settlement":
            score = min(score + 0.1, 0.99)
        scores[action] = round(score, 2)
    return sorted([{"action": a, "score": s} for a, s in scores.items()], key=lambda x: -x["score"])
