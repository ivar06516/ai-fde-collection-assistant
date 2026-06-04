from pydantic import BaseModel


class ArrearsPrediction(BaseModel):
    current_arrears_band: str   # current | 1-30 | 31-60 | 61-90 | 90+
    arrears_trajectory: str     # improving | stable | deteriorating | critical
    predicted_dpd_30: int
    predicted_dpd_60: int
    predicted_dpd_90: int
    default_probability: float  # 0.0 - 1.0
    predicted_arrears_amount: float
    contributing_risk_factors: list[str]
    confidence_score: float
    summary: str
