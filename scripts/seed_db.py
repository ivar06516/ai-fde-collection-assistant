"""Synthetic data generator — seeds SQLite DB with Indian retail customers.

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

fake = Faker("en_US")   # Indian locale — names, addresses, phone numbers
fake.seed_instance(42)
random.seed(42)

# ── US Geography ─────────────────────────────────────────────────────────────
INDIAN_CITIES = [  # variable name kept for compatibility, values are US cities
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
    "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
    "Fort Worth", "Columbus", "Charlotte", "Indianapolis", "San Francisco", "Seattle",
    "Denver", "Nashville", "Oklahoma City", "El Paso", "Washington", "Las Vegas",
    "Boston", "Memphis", "Louisville", "Portland", "Baltimore", "Milwaukee",
]
INDIAN_STATES = [  # variable name kept for compatibility, values are US states
    "California", "Texas", "Florida", "New York", "Illinois", "Pennsylvania",
    "Ohio", "Georgia", "North Carolina", "Michigan", "New Jersey", "Virginia",
    "Washington", "Arizona", "Massachusetts", "Tennessee", "Indiana", "Missouri",
]
# US ZIP codes
INDIAN_PINCODES = [  # variable name kept for compatibility, values are US ZIPs
    "10001", "90001", "60601", "77001", "85001", "19101",
    "78201", "92101", "75201", "95101", "73301", "32099",
    "76101", "43004", "28201", "46201", "94102", "98101",
    "80201", "37201", "73101", "79901", "20001", "89101",
    "02101", "38101", "40201", "97201", "21201", "53201",
]

# ── Indian first/last names ───────────────────────────────────────────────────
INDIAN_FIRST_NAMES = [
    "Arjun", "Priya", "Rahul", "Kavita", "Vikram", "Neha", "Suresh",
    "Ananya", "Ravi", "Deepika", "Amit", "Pooja", "Rajesh", "Sunita",
    "Dinesh", "Meera", "Sanjay", "Rekha", "Anil", "Shobha", "Kiran",
    "Geeta", "Manoj", "Lata", "Ajay", "Nisha", "Vijay", "Usha",
    "Ramesh", "Kamala", "Sunil", "Sarla", "Ashok", "Radha", "Vinod",
    "Savita", "Prakash", "Asha", "Mohan", "Pushpa", "Nitin", "Seema",
    "Harish", "Leela", "Girish", "Parvati", "Vivek", "Jyoti", "Santosh",
    "Bharati", "Naveen", "Anjali", "Rajan", "Madhuri", "Sudhir", "Swati",
    "Rohit", "Sneha", "Gaurav", "Tanvi", "Kunal", "Shruti", "Pavan",
    "Divya", "Sachin", "Rupali", "Aakash", "Manisha", "Ishaan", "Pallavi",
]
INDIAN_LAST_NAMES = [
    "Sharma", "Mehta", "Singh", "Patel", "Nair", "Gupta", "Kumar",
    "Reddy", "Krishnan", "Iyer", "Joshi", "Desai", "Verma", "Rao",
    "Malhotra", "Kapoor", "Bhat", "Chaudhary", "Tiwari", "Mishra",
    "Pillai", "Naidu", "Shah", "Agarwal", "Bajaj", "Bansal", "Bhatt",
    "Chopra", "Deshpande", "Dixit", "Dubey", "Gandhi", "Hegde", "Jain",
    "Khatri", "Lal", "Mathur", "More", "Mukherjee", "Murthy", "Nanda",
    "Pandey", "Parekh", "Patil", "Pillai", "Rane", "Rastogi", "Saxena",
    "Seth", "Shukla", "Sinha", "Srinivasan", "Thakur", "Trivedi", "Wagh",
]

# ── Realistic English interaction notes ──────────────────────────────────────
INTERACTION_NOTES_BY_OUTCOME = {
    "contacted": [
        "Spoke with customer. Reminded about overdue balance. Customer acknowledged and will arrange payment this week.",
        "Customer answered call. Explained consequences of continued non-payment. Customer agreed to visit branch.",
        "Reached customer on mobile. Discussed repayment options. Customer requested 7 days to arrange funds.",
        "Successful contact via phone. Customer aware of outstanding dues. Follow-up scheduled for next week.",
        "Customer contacted via email. Responded promptly. Agreed to initiate NEFT transfer within 3 working days.",
        "Spoke with customer regarding missed EMI. Customer cited temporary cash flow issue. Exploring part-payment option.",
    ],
    "no_answer": [
        "Called customer mobile number. No response. Left voicemail requesting callback.",
        "Attempted to reach customer — phone rang but not answered. SMS sent with callback number.",
        "No answer on primary mobile. Tried alternate contact — unavailable. Will retry tomorrow.",
        "Customer did not respond to call. Email reminder sent with payment details.",
        "Three call attempts made during business hours — no response. Escalating to written notice.",
    ],
    "promise_to_pay": [
        "Customer committed to paying ${amount} by {date}. Payment reference noted for follow-up.",
        "Customer promised full settlement within 10 days. Verbal commitment recorded.",
        "Customer confirmed partial payment of overdue amount will be made by end of month.",
        "Post-dated cheque arrangement discussed. Customer to deposit cheque at branch.",
        "Customer agreed to pay minimum due immediately and remaining balance next month.",
    ],
    "refused": [
        "Customer refused to engage and disconnected the call. Formal notice to be issued.",
        "Customer disputed the outstanding amount and refused payment. Referred to dispute resolution team.",
        "Customer stated financial hardship and unable to pay at this time. Hardship assessment initiated.",
        "Call ended abruptly. Customer unwilling to discuss payment. Legal team informed.",
        "Customer denied receiving previous notices. Resent statements via registered post.",
    ],
    "payment_arranged": [
        "Payment arrangement agreed: $5,000/month for 6 months starting next EMI date.",
        "Customer enrolled in restructuring plan. Standing instruction set up for monthly deductions.",
        "Partial payment of $10,000 received. Balance EMI schedule revised and shared.",
        "ECS mandate obtained. Auto-debit for EMI to begin from 1st of next month.",
        "Settlement offer accepted. Customer to pay 80% of outstanding as full and final settlement.",
    ],
}

DISPUTE_DESCRIPTIONS = {
    "billing_error": [
        "Customer reports incorrect EMI amount debited — charged $8,500 instead of agreed $7,200.",
        "Duplicate charge detected on statement. Customer did not authorise second debit on 15th.",
        "Interest calculation appears incorrect. Customer disputes the outstanding principal shown.",
        "Processing fee of $1,500 levied without prior intimation. Customer requests reversal.",
    ],
    "fraud_claim": [
        "Customer reports transactions not made by them totalling $45,000 between 10-15 March.",
        "Fraudulent withdrawals reported from linked savings account. FIR filed with local police.",
        "Customer did not authorise online transactions. Reports account compromised via phishing.",
        "Card cloned — multiple POS transactions in locations customer was not present.",
    ],
    "identity_theft": [
        "Loan application submitted under customer's name without knowledge. Identity documents misused.",
        "Customer received welcome letter for account they never opened. Identity theft suspected.",
        "Multiple credit enquiries found on CIBIL report from applications customer did not make.",
        "Customer's Aadhaar details used to open fraudulent account. Complaint filed with cyber cell.",
    ],
    "service_dispute": [
        "EMI holiday promised by relationship manager not applied. Customer objects to penalties.",
        "Loan top-up disbursement delayed by 45 days causing project loss. Compensation sought.",
        "Customer was promised waiver of foreclosure charges but levy applied at closure.",
        "Insurance premium bundled without customer consent at time of loan disbursement.",
    ],
    "payment_dispute": [
        "NEFT payment of $25,000 made on 5th March not credited to loan account after 7 days.",
        "Customer's cheque cleared from bank but not applied to account. Bank advice attached.",
        "Online payment failed but amount debited. Customer requests immediate credit or reversal.",
        "Auto-debit executed twice for same EMI period. Excess debit of $6,200 to be refunded.",
    ],
}

PRODUCT_TYPES = ["personal_loan", "credit_card", "mortgage", "auto_loan", "overdraft"]
RISK_SEGMENTS = ["low", "medium", "high", "hardship"]
ACCOUNT_STATUSES = ["current", "delinquent", "legal", "written_off"]
EMPLOYMENT_STATUSES = ["employed", "unemployed", "self_employed", "retired"]
CHANNELS = ["mobile", "email", "post"]
TIMES = ["morning", "afternoon", "evening"]
DISPUTE_TYPES = list(DISPUTE_DESCRIPTIONS.keys())
INTERACTION_TYPES = ["call", "sms", "email", "letter"]
OUTCOMES = ["contacted", "no_answer", "promise_to_pay", "refused", "payment_arranged"]

# ── 10 named Indian demo scenarios ───────────────────────────────────────────
NAMED_SCENARIOS = [
    # (cust_id, first, last, risk, hardship_flag, hardship_reason,
    #  acc_id, product, status, balance, original, dpd, has_dispute, hold)
    ("CUST-001", "Arjun",   "Sharma",   "low",      0, None,
     "ACC-001", "personal_loan", "current",    4500.0,   15000.0,   0,  False, False),
    ("CUST-002", "Priya",   "Mehta",    "medium",   0, None,
     "ACC-002", "credit_card",   "delinquent", 2300.0,    5000.0,  45,  True,  True),
    ("CUST-003", "Rahul",   "Singh",    "high",     0, None,
     "ACC-003", "personal_loan", "delinquent", 12000.0,  20000.0,  92,  False, False),
    ("CUST-004", "Kavita",  "Patel",    "hardship", 1, "unemployment",
     "ACC-004", "overdraft",     "delinquent", 1800.0,    2000.0,  35,  False, False),
    ("CUST-005", "Vikram",  "Nair",     "low",      0, None,
     "ACC-005", "mortgage",      "current",    185000.0, 250000.0,   0,  False, False),
    ("CUST-006", "Neha",    "Gupta",    "medium",   0, None,
     "ACC-006", "auto_loan",     "delinquent", 8000.0,   18000.0,  28,  False, False),
    ("CUST-007", "Suresh",  "Kumar",    "high",     0, None,
     "ACC-007", "credit_card",   "delinquent", 3500.0,    8000.0,  60,  True,  True),
    ("CUST-008", "Ananya",  "Reddy",    "hardship", 1, "medical",
     "ACC-008", "personal_loan", "legal",      22000.0,  25000.0, 120,  False, False),
    ("CUST-009", "Ravi",    "Krishnan", "medium",   0, None,
     "ACC-009", "credit_card",   "current",    500.0,     3000.0,   5,  False, False),
    ("CUST-010", "Deepika", "Iyer",     "low",      0, None,
     "ACC-010", "auto_loan",     "current",    9000.0,   20000.0,   0,  False, False),
]


def _random_name():
    return random.choice(INDIAN_FIRST_NAMES), random.choice(INDIAN_LAST_NAMES)


def _random_location():
    city = random.choice(INDIAN_CITIES)
    state = random.choice(INDIAN_STATES)
    pin = random.choice(INDIAN_PINCODES)
    return city, state, pin


def _interaction_note(outcome: str) -> str:
    notes = INTERACTION_NOTES_BY_OUTCOME.get(outcome, ["Interaction recorded."])
    note = random.choice(notes)
    if "{amount}" in note:
        note = note.replace("{amount}", f"{random.randint(5,50)*1000:,}")
    if "{date}" in note:
        future = date.today() + timedelta(days=random.randint(5, 14))
        note = note.replace("{date}", future.strftime("%d %b %Y"))
    return note


def make_customer(session: Session, customer_id: str, first: str, last: str,
                   risk: str, hardship_flag: int, hardship_reason) -> Customer:
    dob = fake.date_of_birth(minimum_age=22, maximum_age=65)
    today = date.today()
    age = (today - dob).days // 365
    income_by_risk = {"low": (65000, 150000), "medium": (38000, 75000),
                       "high": (22000, 48000), "hardship": (14000, 32000)}
    lo, hi = income_by_risk[risk]
    emp = "unemployed" if hardship_reason == "unemployment" else random.choice(EMPLOYMENT_STATUSES)
    city, state, pin = _random_location()
    mobile = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
    c = Customer(
        customer_id=customer_id,
        first_name=first, last_name=last,
        date_of_birth=dob, age=age,
        gender=random.choice(["M", "F"]),
        email=f"{first.lower()}.{last.lower()}{random.randint(1,99)}@{random.choice(['gmail.com','yahoo.com','outlook.com','hotmail.com'])}",
        mobile_number=mobile[:15],
        city=city, state=state, postcode=pin,
        employment_status=emp,
        annual_income=round(random.uniform(lo, hi), 0),
        relationship_since=fake.date_between(start_date="-8y", end_date="-1y"),
        risk_segment=risk,
        preferred_channel=random.choice(CHANNELS),
        preferred_time=random.choice(TIMES),
        hardship_flag=hardship_flag,
        hardship_reason=hardship_reason,
    )
    session.add(c)
    return c


def make_account(session: Session, account_id: str, customer_id: str,
                  product: str, status: str, balance: float, original: float, dpd: int) -> Account:
    opened = fake.date_between(start_date="-6y", end_date="-6m")
    delinq_start = (date.today() - timedelta(days=dpd + 10)) if dpd > 0 else None
    last_pay = (date.today() - timedelta(days=dpd + 5)) if dpd > 0 else (date.today() - timedelta(days=30))
    a = Account(
        account_id=account_id, customer_id=customer_id,
        product_type=product, account_status=status,
        outstanding_balance=balance, original_balance=original,
        credit_limit=original * 1.2 if product in ("credit_card", "overdraft") else None,
        interest_rate=round(random.uniform(9.5, 22.0), 2),
        days_past_due=dpd,
        delinquency_start=delinq_start,
        last_payment_date=last_pay,
        last_payment_amount=round(original * 0.02, 0),
        next_due_date=date.today() + timedelta(days=15),
        next_due_amount=round(original * 0.025, 0),
        opened_date=opened,
    )
    session.add(a)
    return a


def make_payment_history(session: Session, account_id: str, dpd: int, months: int = 12) -> None:
    today = date.today()
    for i in range(months):
        m = (today.replace(day=1) - timedelta(days=i * 31)).strftime("%Y-%m")
        amount_due = round(random.uniform(3000, 15000), 0)
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
                  collection_hold: bool, dispute_type: str = None) -> None:
    disp_num = session.query(Dispute).count() + 1
    dispute_id = f"DISP-{disp_num:03d}"
    dtype = dispute_type or random.choice(DISPUTE_TYPES)
    description = random.choice(DISPUTE_DESCRIPTIONS.get(dtype, ["Dispute raised by customer."]))
    d = Dispute(
        dispute_id=dispute_id, account_id=account_id, customer_id=customer_id,
        dispute_type=dtype, status="under_review",
        opened_date=fake.date_between(start_date="-45d", end_date="-5d"),
        description=description,
        collection_hold=1 if collection_hold else 0,
    )
    session.add(d)


def make_interactions(session: Session, customer_id: str, account_id: str, count: int = 5) -> None:
    for _ in range(count):
        outcome = random.choice(OUTCOMES)
        ih = InteractionHistory(
            customer_id=customer_id, account_id=account_id,
            interaction_type=random.choice(INTERACTION_TYPES),
            interaction_date=datetime.combine(
                fake.date_between(start_date="-180d", end_date="today"),
                datetime.min.time(),
            ),
            outcome=outcome,
            agent_notes=_interaction_note(outcome),
        )
        session.add(ih)


def seed(session: Session) -> None:
    # Seed 10 named Indian scenarios
    for (cid, first, last, risk, hf, hr, aid, product, status, bal, orig, dpd, has_disp, hold) in NAMED_SCENARIOS:
        make_customer(session, cid, first, last, risk, hf, hr)
        make_account(session, aid, cid, product, status, bal, orig, dpd)
        make_payment_history(session, aid, dpd)
        if has_disp:
            make_dispute(session, aid, cid, hold, "identity_theft" if cid == "CUST-002" else None)
        make_interactions(session, cid, aid, random.randint(3, 8))

    # AC-005-03: CUST-007 Suresh Kumar needs 2 active disputes
    from datetime import date as _date, timedelta as _td
    _extra_disp_num = session.query(Dispute).count() + 1
    session.add(Dispute(
        dispute_id=f"DISP-{_extra_disp_num:03d}",
        account_id="ACC-007", customer_id="CUST-007",
        dispute_type="billing_error",
        status="open",
        opened_date=_date.today() - _td(days=12),
        description="Incorrect charge appeared on statement — customer did not authorise this debit.",
        collection_hold=1,
    ))
    session.flush()

    # Seed 90 additional random Indian customers
    for i in range(11, 101):
        cid = f"CUST-{i:03d}"
        aid = f"ACC-{i:03d}"
        risk = random.choice(RISK_SEGMENTS)
        hf = 1 if risk == "hardship" else 0
        hr = random.choice(["unemployment", "medical", "family", None]) if hf else None
        first, last = _random_name()
        dpd = random.choice([0, 0, 0, 15, 30, 45, 60, 90, 120])
        status = "current" if dpd == 0 else random.choice(["delinquent", "delinquent", "legal"])
        orig = round(random.uniform(50000, 2000000), 0)
        bal = round(orig * random.uniform(0.1, 0.95), 0)
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
    print(f"Seeded: 100 Indian customers, 100 accounts")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed SQLite DB with Indian synthetic data")
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
