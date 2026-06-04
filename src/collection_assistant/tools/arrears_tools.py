def analyse_payment_pattern(payment_months: list) -> dict:
    if not payment_months:
        return {"trend": "unknown", "consecutive_missed": 0, "avg_payment_ratio": 1.0}
    ratios = []
    for m in payment_months:
        due = m.get("amount_due", 0)
        paid = m.get("amount_paid", 0)
        ratios.append(paid / due if due > 0 else 1.0)
    recent = ratios[:3]
    older = ratios[3:6] if len(ratios) >= 6 else ratios[3:]
    avg_recent = sum(recent) / len(recent) if recent else 1.0
    avg_older = sum(older) / len(older) if older else 1.0
    if avg_recent < avg_older - 0.1:
        trend = "deteriorating"
    elif avg_recent > avg_older + 0.1:
        trend = "improving"
    else:
        trend = "stable"
    consecutive_missed = 0
    for m in payment_months:
        if not m.get("on_time", True):
            consecutive_missed += 1
        else:
            break
    return {"trend": trend, "consecutive_missed": consecutive_missed,
            "avg_payment_ratio": round(sum(ratios) / len(ratios), 2),
            "avg_recent_ratio": round(avg_recent, 2)}


def calculate_arrears_trajectory(dpd: int, trend: str, consecutive_missed: int) -> str:
    if dpd >= 90 or consecutive_missed >= 4:
        return "critical"
    if dpd >= 60 or (trend == "deteriorating" and consecutive_missed >= 2):
        return "deteriorating"
    if trend == "improving" and dpd < 30:
        return "improving"
    return "stable"


def predict_default_probability(dpd: int, trajectory: str, risk_segment: str, on_time_rate: float) -> float:
    base = min(dpd / 120, 0.9)
    multipliers = {"critical": 1.5, "deteriorating": 1.3, "stable": 1.0, "improving": 0.7}
    risk_add = {"hardship": 0.15, "high": 0.1, "medium": 0.05, "low": 0.0}
    prob = base * multipliers.get(trajectory, 1.0) + risk_add.get(risk_segment, 0.0)
    return round(min(max(prob, 0.01), 0.99), 2)


def identify_risk_factors(dpd: int, trajectory: str, hardship_flag: bool,
                           employment_status: str, on_time_rate: float, missed_6m: int) -> list:
    """Return ranked list of risk factors as [{"name": str, "weight": float}] sorted by weight desc."""
    raw: list[tuple[str, float]] = []
    if dpd > 90:
        raw.append((f"High DPD: {dpd} days past due", 0.90))
    elif dpd > 60:
        raw.append((f"Elevated DPD: {dpd} days past due", 0.75))
    elif dpd > 30:
        raw.append((f"DPD: {dpd} days past due", 0.55))
    if trajectory == "critical":
        raw.append(("Arrears trajectory: critical", 0.85))
    elif trajectory == "deteriorating":
        raw.append(("Arrears trajectory: deteriorating", 0.65))
    if hardship_flag:
        raw.append(("Active hardship flag", 0.70))
    if employment_status == "unemployed":
        raw.append(("Currently unemployed", 0.60))
    if on_time_rate < 0.5:
        raw.append((f"Very low on-time payment rate: {int(on_time_rate*100)}%", 0.75))
    elif on_time_rate < 0.7:
        raw.append((f"Low on-time payment rate: {int(on_time_rate*100)}%", 0.50))
    if missed_6m >= 4:
        raw.append((f"{missed_6m} missed payments in last 6 months", 0.70))
    elif missed_6m >= 2:
        raw.append((f"{missed_6m} missed payments in last 6 months", 0.45))
    if not raw:
        raw.append(("No significant risk factors identified", 0.05))
    raw.sort(key=lambda x: -x[1])
    return [{"name": name, "weight": weight} for name, weight in raw]


def estimate_future_arrears(current_dpd: int, trajectory: str, outstanding_balance: float,
                             monthly_interest_rate: float = 0.015,
                             months_available: int = 12) -> dict:
    """Project DPD at +30/+60/+90 days and calculate confidence score.

    Returns: predicted_dpd_30, predicted_dpd_60, predicted_dpd_90,
             predicted_arrears_amount, confidence_score.
    """
    escalation = {"critical": 35, "deteriorating": 22, "stable": 5, "improving": -8}
    step = escalation.get(trajectory, 5)

    predicted_30 = max(0, current_dpd + step)
    predicted_60 = max(0, current_dpd + step * 2)
    predicted_90 = max(0, current_dpd + step * 3)

    months_accrued = max(1, round(predicted_90 / 30))
    predicted_amount = round(outstanding_balance * ((1 + monthly_interest_rate) ** months_accrued), 2)

    # Confidence degrades for low history and extreme projections
    confidence = 0.85
    if months_available < 3:
        confidence = 0.30
    elif months_available < 6:
        confidence = 0.55
    if trajectory == "critical" and current_dpd < 90:
        confidence = min(confidence, 0.65)

    return {
        "predicted_dpd_30": predicted_30,
        "predicted_dpd_60": predicted_60,
        "predicted_dpd_90": predicted_90,
        "predicted_arrears_amount": predicted_amount,
        "confidence_score": round(confidence, 2),
    }
