from typing import Literal, Optional
from pydantic import BaseModel, field_validator

AccountStatus = Literal["current", "delinquent", "legal", "written_off", "closed"]
ProductType = Literal["personal_loan", "credit_card", "mortgage", "auto_loan", "overdraft"]


class PaymentRecord(BaseModel):
    month: str
    amount_due: float
    amount_paid: float
    on_time: bool


class AccountProfile(BaseModel):
    account_id: str
    customer_id: str
    product_type: str
    account_status: AccountStatus
    outstanding_balance: float
    original_balance: float
    credit_limit: Optional[float] = None
    days_past_due: int
    delinquency_start: Optional[str] = None
    last_payment_date: Optional[str] = None
    last_payment_amount: Optional[float] = None
    next_due_date: Optional[str] = None
    next_due_amount: Optional[float] = None
    payment_history: list[PaymentRecord] = []
    on_time_payment_rate: float
    missed_payments_last_6m: int
    linked_account_ids: list[str] = []
    summary: str

    @field_validator("account_status", mode="before")
    @classmethod
    def normalise_account_status(cls, v: str) -> str:
        clean = str(v).lower().strip()
        valid = {"current", "delinquent", "legal", "written_off", "closed"}
        return clean if clean in valid else "delinquent"
