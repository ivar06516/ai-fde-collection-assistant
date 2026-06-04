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
    factors = []
    if dpd > 60:
        factors.append(f"High DPD: {dpd} days past due")
    if trajectory in ("deteriorating", "critical"):
        factors.append(f"Arrears trajectory: {trajectory}")
    if hardship_flag:
        factors.append("Active hardship flag")
    if employment_status == "unemployed":
        factors.append("Currently unemployed")
    if on_time_rate < 0.6:
        factors.append(f"Low on-time payment rate: {int(on_time_rate*100)}%")
    if missed_6m >= 3:
        factors.append(f"{missed_6m} missed payments in last 6 months")
    return factors or ["No significant risk factors identified"]
