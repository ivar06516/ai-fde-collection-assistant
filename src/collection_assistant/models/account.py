from typing import Optional
from pydantic import BaseModel


class PaymentRecord(BaseModel):
    month: str
    amount_due: float
    amount_paid: float
    on_time: bool


class AccountProfile(BaseModel):
    account_id: str
    customer_id: str
    product_type: str
    account_status: str
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
    summary: str
