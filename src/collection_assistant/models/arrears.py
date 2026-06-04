from typing import Literal
from pydantic import BaseModel, field_validator

ArrearsBand = Literal["current", "1-30", "31-60", "61-90", "90+"]
ArrearsTrajectory = Literal["improving", "stable", "deteriorating", "critical"]


class RiskFactor(BaseModel):
    name: str
    weight: float  # 0.0 - 1.0, higher = more impactful


class ArrearsPrediction(BaseModel):
    current_arrears_band: ArrearsBand
    arrears_trajectory: ArrearsTrajectory
    predicted_dpd_30: int
    predicted_dpd_60: int
    predicted_dpd_90: int
    default_probability: float  # 0.0 - 1.0
    predicted_arrears_amount: float
    contributing_risk_factors: list[RiskFactor] = []
    confidence_score: float
    summary: str

    @field_validator("arrears_trajectory", mode="before")
    @classmethod
    def normalise_trajectory(cls, v: str) -> str:
        clean = str(v).lower().strip()
        return clean if clean in {"improving", "stable", "deteriorating", "critical"} else "stable"

    @field_validator("current_arrears_band", mode="before")
    @classmethod
    def normalise_band(cls, v: str) -> str:
        clean = str(v).strip()
        return clean if clean in {"current", "1-30", "31-60", "61-90", "90+"} else "current"

    @field_validator("default_probability", "confidence_score", mode="before")
    @classmethod
    def clamp_float(cls, v: float) -> float:
        return round(min(max(float(v), 0.0), 1.0), 4)
