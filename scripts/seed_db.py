"""Synthetic data generator — seeds SQLite DB with realistic retail customers.

Usage:
    python scripts/seed_db.py              # seed with defaults
    python scripts/seed_db.py --reset      # drop all tables and re-seed
"""
import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from faker import Faker
from sqlalchemy.orm import Session

from collection_assistant.db.models import (
    Account, Customer, Dispute, InteractionHistory, PaymentHistory, WorkflowAudit,
)
from collection_assistant.db.session import create_all_tables, get_engine

fake = Faker("en_GB")
fake.seed_instance(42)
random.seed(42)

PRODUCT_TYPES = ["personal_loan", "credit_card", "mortgage", "auto_loan", "overdraft"]
RISK_SEGMENTS = ["low", "medium", "high", "hardship"]
ACCOUNT_STATUSES = ["current", "delinquent", "legal", "written_off"]
EMPLOYMENT_STATUSES = ["employed", "unemployed", "self_employed", "retired"]
CHANNELS = ["mobile", "email", "post"]
TIMES = ["morning", "afternoon", "evening"]
DISPUTE_TYPES = ["billing_error", "fraud_claim", "identity_theft", "service_dispute", "payment_dispute"]
INTERACTION_TYPES = ["call", "sms", "email", "letter"]
OUTCOMES = ["contacted", "no_answer", "promise_to_pay", "refused", "payment_arranged"]

# 10 mandatory named demo scenarios
NAMED_SCENARIOS = [
    # (customer_id, first, last, risk_segment, hardship_flag, hardship_reason,
    #  account_id, product, status, balance, original, dpd, has_dispute, collection_hold)
    ("CUST-001", "James", "Chen", "low", 0, None,
     "ACC-001", "personal_loan", "current", 4500.0, 15000.0, 0, False, False),
    ("CUST-002", "Sarah", "Jones", "medium", 0, None,
     "ACC-002", "credit_card", "delinquent", 2300.0, 5000.0, 45, True, True),
    ("CUST-003", "Michael", "Okonkwo", "high", 0, None,
     "ACC-003", "personal_loan", "delinquent", 12000.0, 20000.0, 92, False, False),
    ("CUST-004", "Emma", "Patel", "hardship", 1, "unemployment",
     "ACC-004", "overdraft", "delinquent", 1800.0, 2000.0, 35, False, False),
    ("CUST-005", "William", "Nguyen", "low", 0, None,
     "ACC-005", "mortgage", "current", 185000.0, 250000.0, 0, False, False),
    ("CUST-006", "Olivia", "Smith", "medium", 0, None,
     "ACC-006", "auto_loan", "delinquent", 8000.0, 18000.0, 28, False, False),
    ("CUST-007", "David", "Brown", "high", 0, None,
     "ACC-007", "credit_card", "delinquent", 3500.0, 8000.0, 60, True, True),
    ("CUST-008", "Isabella", "Garcia", "hardship", 1, "medical",
     "ACC-008", "personal_loan", "legal", 22000.0, 25000.0, 120, False, False),
    ("CUST-009", "Ethan", "Wilson", "medium", 0, None,
     "ACC-009", "credit_card", "current", 500.0, 3000.0, 5, False, False),
    ("CUST-010", "Sophia", "Martinez", "low", 0, None,
     "ACC-010", "auto_loan", "current", 9000.0, 20000.0, 0, False, False),
]


def make_customer(session: Session, customer_id: str, first: str, last: str,
                   risk: str, hardship_flag: int, hardship_reason: str | None) -> Customer:
    dob = fake.date_of_birth(minimum_age=22, maximum_age=70)
    today = date.today()
    age = (today - dob).days // 365
    income_by_risk = {"low": (55000, 120000), "medium": (30000, 70000),
                       "high": (20000, 45000), "hardship": (12000, 28000)}
    lo, hi = income_by_risk[risk]
    emp = "unemployed" if hardship_reason == "unemployment" else random.choice(EMPLOYMENT_STATUSES)
    c = Customer(
        customer_id=customer_id,
        first_name=first, last_name=last,
        date_of_birth=dob, age=age,
        gender=random.choice(["M", "F"]),
        email=f"{first.lower()}.{last.lower()}@example.com",
        mobile_number=fake.phone_number()[:15],
        city=fake.city(), state=fake.county(), postcode=fake.postcode(),
        employment_status=emp,
        annual_income=round(random.uniform(lo, hi), 2),
        relationship_since=fake.date_between(start_date="-10y", end_date="-1y"),
        risk_segment=risk,
        preferred_channel=random.choice(CHANNELS),
        preferred_time=random.choice(TIMES),
        hardship_flag=hardship_flag,
        hardship_reason=hardship_reason,
    )
    session.add(c)
    return c


def make_account(session: Session, account_id: str, customer_id: str,
                  product: str, status: str, balance: float, original: float,
                  dpd: int) -> Account:
    opened = fake.date_between(start_date="-5y", end_date="-6m")
    delinq_start = (date.today() - timedelta(days=dpd + 10)) if dpd > 0 else None
    last_pay = (date.today() - timedelta(days=dpd + 5)) if dpd > 0 else (date.today() - timedelta(days=30))
    a = Account(
        account_id=account_id, customer_id=customer_id,
        product_type=product, account_status=status,
        outstanding_balance=balance, original_balance=original,
        credit_limit=original * 1.2 if product in ("credit_card", "overdraft") else None,
        interest_rate=round(random.uniform(8.5, 24.9), 2),
        days_past_due=dpd,
        delinquency_start=delinq_start,
        last_payment_date=last_pay,
        last_payment_amount=round(original * 0.02, 2),
        next_due_date=date.today() + timedelta(days=15),
        next_due_amount=round(original * 0.025, 2),
        opened_date=opened,
    )
    session.add(a)
    return a


def make_payment_history(session: Session, account_id: str, dpd: int, months: int = 12) -> None:
    today = date.today()
    for i in range(months):
        m = (today.replace(day=1) - timedelta(days=i * 31)).strftime("%Y-%m")
        amount_due = round(random.uniform(100, 500), 2)
        missed = (i < (dpd // 30)) and dpd > 0
        amount_paid = 0.0 if missed else amount_due
        on_time = 0 if missed else 1
        pay_date = None if missed else (today - timedelta(days=i * 30 + 5))
        try:
            ph = PaymentHistory(
                account_id=account_id, payment_month=m,
                amount_due=amount_due, amount_paid=amount_paid,
                on_time=on_time, payment_date=pay_date,
            )
            session.add(ph)
        except Exception:
            pass


def make_dispute(session: Session, account_id: str, customer_id: str,
                  collection_hold: bool) -> None:
    disp_num = len([d for d in session.query(Dispute).all()]) + 1
    dispute_id = f"DISP-{disp_num:03d}"
    d = Dispute(
        dispute_id=dispute_id, account_id=account_id, customer_id=customer_id,
        dispute_type=random.choice(DISPUTE_TYPES),
        status="under_review",
        opened_date=fake.date_between(start_date="-60d", end_date="-5d"),
        description=fake.sentence(nb_words=12),
        collection_hold=1 if collection_hold else 0,
    )
    session.add(d)


def make_interactions(session: Session, customer_id: str, account_id: str, count: int = 5) -> None:
    for _ in range(count):
        ih = InteractionHistory(
            customer_id=customer_id, account_id=account_id,
            interaction_type=random.choice(INTERACTION_TYPES),
            interaction_date=datetime.combine(
                fake.date_between(start_date="-180d", end_date="today"),
                datetime.min.time(),
            ),
            outcome=random.choice(OUTCOMES),
            agent_notes=fake.sentence(nb_words=8),
        )
        session.add(ih)


def seed(session: Session) -> None:
    # Seed 10 named scenarios
    for (cid, first, last, risk, hf, hr, aid, product, status, bal, orig, dpd, has_disp, hold) in NAMED_SCENARIOS:
        make_customer(session, cid, first, last, risk, hf, hr)
        make_account(session, aid, cid, product, status, bal, orig, dpd)
        make_payment_history(session, aid, dpd)
        if has_disp:
            make_dispute(session, aid, cid, hold)
        make_interactions(session, cid, aid, random.randint(2, 8))

    # AC-005-03: CUST-007 David Brown needs 2 active disputes (seeded with 1 above)
    from datetime import date as _date, timedelta as _td
    disp_num = session.query(Dispute).count() + 1
    session.add(Dispute(
        dispute_id=f"DISP-{disp_num:03d}",
        account_id="ACC-007", customer_id="CUST-007",
        dispute_type="billing_error",
        status="open",
        opened_date=_date.today() - _td(days=12),
        description="Incorrect charge appeared on my statement that I did not authorise",
        collection_hold=1,
    ))
    session.flush()

    # Seed 90 additional random customers
    for i in range(11, 101):
        cid = f"CUST-{i:03d}"
        aid = f"ACC-{i:03d}"
        risk = random.choice(RISK_SEGMENTS)
        hf = 1 if risk == "hardship" else 0
        hr = random.choice(["unemployment", "medical", "family", None]) if hf else None
        first, last = fake.first_name(), fake.last_name()
        dpd = random.choice([0, 0, 0, 15, 30, 45, 60, 90, 120])
        status = "current" if dpd == 0 else random.choice(["delinquent", "delinquent", "legal"])
        orig = round(random.uniform(1000, 50000), 2)
        bal = round(orig * random.uniform(0.1, 0.95), 2)
        product = random.choice(PRODUCT_TYPES)
        has_disp = random.random() < 0.15
        hold = has_disp and random.random() < 0.7
        make_customer(session, cid, first, last, risk, hf, hr)
        make_account(session, aid, cid, product, status, bal, orig, dpd)
        make_payment_history(session, aid, dpd)
        if has_disp:
            make_dispute(session, aid, cid, hold)
        make_interactions(session, cid, aid, random.randint(0, 6))

    session.commit()
    print(f"Seeded: 100 customers, 100 accounts")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic data into SQLite DB")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables first")
    args = parser.parse_args()

    engine = get_engine()
    if args.reset:
        from collection_assistant.db.models import Base
        print("Dropping all tables...")
        Base.metadata.drop_all(engine)
        print("Tables dropped.")

    create_all_tables()
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    with Session() as session:
        existing = session.query(Customer).count()
        if existing > 0 and not args.reset:
            print(f"DB already has {existing} customers. Use --reset to re-seed.")
            return
        seed(session)
    print("Done.")


if __name__ == "__main__":
    main()
