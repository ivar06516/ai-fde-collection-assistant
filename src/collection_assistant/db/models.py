from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    mobile_number: Mapped[Optional[str]] = mapped_column(String)
    city: Mapped[Optional[str]] = mapped_column(String)
    state: Mapped[Optional[str]] = mapped_column(String)
    postcode: Mapped[Optional[str]] = mapped_column(String)
    employment_status: Mapped[Optional[str]] = mapped_column(String)
    annual_income: Mapped[Optional[float]] = mapped_column(Float)
    relationship_since: Mapped[date] = mapped_column(Date, nullable=False)
    risk_segment: Mapped[str] = mapped_column(String, nullable=False)
    preferred_channel: Mapped[str] = mapped_column(String, default="mobile")
    preferred_time: Mapped[str] = mapped_column(String, default="morning")
    hardship_flag: Mapped[int] = mapped_column(Integer, default=0)
    hardship_reason: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    accounts: Mapped[list["Account"]] = relationship(back_populates="customer")
    interactions: Mapped[list["InteractionHistory"]] = relationship(back_populates="customer")


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    product_type: Mapped[str] = mapped_column(String, nullable=False)
    account_status: Mapped[str] = mapped_column(String, nullable=False)
    outstanding_balance: Mapped[float] = mapped_column(Float, default=0)
    original_balance: Mapped[float] = mapped_column(Float, nullable=False)
    credit_limit: Mapped[Optional[float]] = mapped_column(Float)
    interest_rate: Mapped[Optional[float]] = mapped_column(Float)
    days_past_due: Mapped[int] = mapped_column(Integer, default=0)
    delinquency_start: Mapped[Optional[date]] = mapped_column(Date)
    last_payment_date: Mapped[Optional[date]] = mapped_column(Date)
    last_payment_amount: Mapped[Optional[float]] = mapped_column(Float)
    next_due_date: Mapped[Optional[date]] = mapped_column(Date)
    next_due_amount: Mapped[Optional[float]] = mapped_column(Float)
    opened_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="accounts")
    payment_history: Mapped[list["PaymentHistory"]] = relationship(back_populates="account")
    disputes: Mapped[list["Dispute"]] = relationship(back_populates="account")
    interactions: Mapped[list["InteractionHistory"]] = relationship(back_populates="account")


class PaymentHistory(Base):
    __tablename__ = "payment_history"
    __table_args__ = (UniqueConstraint("account_id", "payment_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False)
    payment_month: Mapped[str] = mapped_column(String, nullable=False)
    amount_due: Mapped[float] = mapped_column(Float, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Float, default=0)
    on_time: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_date: Mapped[Optional[date]] = mapped_column(Date)

    account: Mapped["Account"] = relationship(back_populates="payment_history")


class Dispute(Base):
    __tablename__ = "disputes"

    dispute_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    dispute_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    opened_date: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_date: Mapped[Optional[date]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)
    collection_hold: Mapped[int] = mapped_column(Integer, default=1)
    resolution: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped["Account"] = relationship(back_populates="disputes")
    customer: Mapped["Customer"] = relationship()


class InteractionHistory(Base):
    __tablename__ = "interaction_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False)
    interaction_type: Mapped[str] = mapped_column(String, nullable=False)
    interaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(String)
    agent_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="interactions")
    account: Mapped["Account"] = relationship(back_populates="interactions")


class WorkflowAudit(Base):
    __tablename__ = "workflow_audit"

    workflow_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    trigger_context: Mapped[str] = mapped_column(String, nullable=False)
    nba_action: Mapped[Optional[str]] = mapped_column(String)
    nba_channel: Mapped[Optional[str]] = mapped_column(String)
    nba_confidence: Mapped[Optional[float]] = mapped_column(Float)
    nba_rationale: Mapped[Optional[str]] = mapped_column(Text)
    full_state_json: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False)
    total_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
