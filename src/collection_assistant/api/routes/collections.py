"""Collections API routes - trigger pipeline, stream SSE, retrieve audit."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from collection_assistant.db.queries.account_queries import get_account, get_accounts_for_customer, list_accounts
from collection_assistant.db.queries.audit_queries import get_audit_record, list_recent_audits
from collection_assistant.db.queries.customer_queries import get_customer, list_customers
from collection_assistant.db.session import db_session
from collection_assistant.exceptions import AccountNotFoundError, CustomerNotFoundError
from collection_assistant.graph.collection_graph import run_collection_pipeline
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus

router = APIRouter(prefix="/collections")

# In-memory workflow store — capped at 200 entries (M-2 fix: prevent memory leak)
_workflow_store: dict[str, CollectionWorkflowState] = {}
_MAX_STORE_SIZE = 200


def _evict_oldest_workflow() -> None:
    if len(_workflow_store) > _MAX_STORE_SIZE:
        oldest = next(iter(_workflow_store))
        del _workflow_store[oldest]


class RecommendRequest(BaseModel):
    customer_id: str
    account_id: str
    trigger_context: str = "routine_review"


class RecommendResponse(BaseModel):
    workflow_id: str
    status: str


def _run_pipeline_with_events(workflow_id: str, customer_id: str,
                               account_id: str, trigger_context: str) -> None:
    """Run pipeline — agents emit live events via event_bus as they start/complete."""
    event_bus.emit(workflow_id, "pipeline_started", {
        "workflow_id": workflow_id,
        "customer_id": customer_id,
        "account_id": account_id,
    })
    try:
        state = run_collection_pipeline(workflow_id, customer_id, account_id, trigger_context)
        _workflow_store[workflow_id] = state
        event_bus.emit(workflow_id, "workflow_complete", {
            "workflow_id": workflow_id,
            "status": state["workflow_status"],
            "total_ms": state.get("total_ms"),
        })
    except (CustomerNotFoundError, AccountNotFoundError) as e:
        event_bus.emit(workflow_id, "workflow_error", {"error": str(e), "workflow_id": workflow_id})
        _workflow_store[workflow_id] = {"workflow_status": "error", "error_log": [str(e)]}
    except Exception as e:
        event_bus.emit(workflow_id, "workflow_error", {"error": str(e), "workflow_id": workflow_id})
        _workflow_store[workflow_id] = {"workflow_status": "error", "error_log": [str(e)]}


@router.post("/recommend", response_model=RecommendResponse, status_code=202)
async def recommend(req: RecommendRequest, background_tasks: BackgroundTasks) -> RecommendResponse:
    # Pre-flight: validate customer and account exist before starting any background work
    with db_session() as session:
        try:
            get_customer(session, req.customer_id)
        except CustomerNotFoundError:
            raise HTTPException(status_code=404, detail=f"Customer {req.customer_id} not found")
        try:
            get_account(session, req.account_id)
        except AccountNotFoundError:
            raise HTTPException(status_code=404, detail=f"Account {req.account_id} not found")

    workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
    event_bus.register(workflow_id)
    _workflow_store[workflow_id] = {"workflow_status": "in_progress"}
    _evict_oldest_workflow()

    background_tasks.add_task(
        _run_pipeline_with_events,
        workflow_id, req.customer_id, req.account_id, req.trigger_context,
    )
    return RecommendResponse(workflow_id=workflow_id, status="in_progress")


@router.get("/{workflow_id}/stream")
async def stream_workflow(workflow_id: str) -> StreamingResponse:
    """SSE endpoint - streams agent events as they arrive."""
    if workflow_id not in event_bus._queues:
        raise HTTPException(status_code=404, detail="Workflow not found")

    async def event_generator() -> AsyncIterator[str]:
        from collection_assistant.config import get_settings
        seen = 0
        max_wait = get_settings().agent_timeout_seconds * 6  # m-3 fix: configurable timeout
        waited = 0
        while waited < max_wait:
            events = event_bus.get_events(workflow_id)
            while seen < len(events):
                event = events[seen]
                yield f"data: {json.dumps(event)}\n\n"
                seen += 1
                if event["type"] == "workflow_complete":
                    event_bus.cleanup(workflow_id)
                    return
                if event["type"] == "workflow_error":
                    event_bus.cleanup(workflow_id)
                    return
            await asyncio.sleep(0.2)
            waited += 0.2
        timeout_event = json.dumps({"type": "timeout", "data": {}})
        yield f"data: {timeout_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{workflow_id}/state")
async def get_workflow_state(workflow_id: str) -> dict:
    state = _workflow_store.get(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return state


@router.get("/{workflow_id}/audit")
async def get_workflow_audit(workflow_id: str) -> dict:
    with db_session() as session:
        record = get_audit_record(session, workflow_id)
        if not record:
            raise HTTPException(status_code=404, detail="Audit record not found")
        return {
            "workflow_id": record.workflow_id,
            "customer_id": record.customer_id,
            "account_id": record.account_id,
            "trigger_context": record.trigger_context,
            "nba_action": record.nba_action,
            "nba_channel": record.nba_channel,
            "nba_confidence": record.nba_confidence,
            "nba_rationale": record.nba_rationale,
            "status": record.status,
            "total_ms": record.total_ms,
            "created_at": str(record.created_at),
            "full_state": json.loads(record.full_state_json) if record.full_state_json else None,
        }


@router.get("/recent/audits")
async def recent_audits() -> list:
    with db_session() as session:
        records = list_recent_audits(session)
        return [
            {"workflow_id": r.workflow_id, "customer_id": r.customer_id,
             "account_id": r.account_id, "nba_action": r.nba_action,
             "status": r.status, "total_ms": r.total_ms, "created_at": str(r.created_at)}
            for r in records
        ]


@router.get("/data/portfolio")
async def get_portfolio() -> list:
    """Full customer + account data for the dashboard table."""
    from collection_assistant.db.models import Customer, Account, Dispute
    from sqlalchemy import func
    with db_session() as session:
        rows = (
            session.query(Customer, Account)
            .join(Account, Account.customer_id == Customer.customer_id)
            .order_by(Account.days_past_due.desc(), Customer.customer_id)
            .all()
        )
        # Active hold lookup
        holds = {}
        hold_reasons = {}
        active_disputes = (
            session.query(Dispute)
            .filter(Dispute.status.in_(["open", "under_review", "escalated"]))
            .all()
        )
        for d in active_disputes:
            if d.collection_hold:
                holds[d.account_id] = True
                hold_reasons[d.account_id] = f"{d.dispute_type.replace('_',' ').title()} ({d.dispute_id})"

        dispute_counts = {}
        for d in active_disputes:
            dispute_counts[d.account_id] = dispute_counts.get(d.account_id, 0) + 1

        result = []
        for c, a in rows:
            dpd = a.days_past_due or 0
            result.append({
                "customer_id":       c.customer_id,
                "account_id":        a.account_id,
                "full_name":         f"{c.first_name} {c.last_name}",
                "risk_segment":      c.risk_segment,
                "hardship_flag":     bool(c.hardship_flag),
                "hardship_reason":   c.hardship_reason,
                "employment_status": c.employment_status,
                "annual_income":     c.annual_income,
                "preferred_channel": c.preferred_channel,
                "product_type":      a.product_type,
                "account_status":    a.account_status,
                "days_past_due":     dpd,
                "outstanding_balance": a.outstanding_balance,
                "original_balance":    a.original_balance,
                "collection_hold":   holds.get(a.account_id, False),
                "hold_reason":       hold_reasons.get(a.account_id),
                "active_disputes":   dispute_counts.get(a.account_id, 0),
                "arrears_band": (
                    "current" if dpd == 0 else
                    "1-30"    if dpd <= 30 else
                    "31-60"   if dpd <= 60 else
                    "61-90"   if dpd <= 90 else "90+"
                ),
            })
        return result



@router.get("/data/customer/{customer_id}")
async def get_customer_detail(customer_id: str) -> dict:
    """Full customer detail for Page 3 — customer profile view."""
    from collection_assistant.db.models import Customer, Account, Dispute, InteractionHistory, PaymentHistory
    with db_session() as session:
        from collection_assistant.exceptions import CustomerNotFoundError
        try:
            from collection_assistant.db.queries.customer_queries import get_customer
            c = get_customer(session, customer_id)
        except CustomerNotFoundError:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

        accounts = session.query(Account).filter(Account.customer_id == customer_id).all()
        interactions = (session.query(InteractionHistory)
                        .filter(InteractionHistory.customer_id == customer_id)
                        .order_by(InteractionHistory.interaction_date.desc())
                        .limit(10).all())
        disputes = (session.query(Dispute)
                    .filter(Dispute.customer_id == customer_id)
                    .order_by(Dispute.opened_date.desc()).all())

        from datetime import date
        tenure_years = round((date.today() - c.relationship_since).days / 365.25, 1) if c.relationship_since else 0

        accounts_data = []
        for a in accounts:
            ph = (session.query(PaymentHistory)
                  .filter(PaymentHistory.account_id == a.account_id)
                  .order_by(PaymentHistory.payment_month.desc())
                  .limit(12).all())
            on_time = sum(1 for p in ph if p.on_time)
            accounts_data.append({
                "account_id": a.account_id,
                "product_type": a.product_type,
                "account_status": a.account_status,
                "outstanding_balance": a.outstanding_balance,
                "original_balance": a.original_balance,
                "days_past_due": a.days_past_due or 0,
                "on_time_rate": round(on_time / len(ph), 2) if ph else 1.0,
                "missed_last_6m": sum(1 for p in ph[:6] if not p.on_time),
                "last_payment_date": str(a.last_payment_date) if a.last_payment_date else None,
                "last_payment_amount": a.last_payment_amount,
                "payment_history": [
                    {"month": p.payment_month, "amount_due": p.amount_due,
                     "amount_paid": p.amount_paid, "on_time": bool(p.on_time)}
                    for p in ph
                ],
            })

        return {
            "customer_id": c.customer_id,
            "full_name": f"{c.first_name} {c.last_name}",
            "age": c.age,
            "gender": c.gender,
            "email": c.email,
            "mobile_number": c.mobile_number,
            "city": c.city,
            "state": c.state,
            "employment_status": c.employment_status,
            "annual_income": c.annual_income,
            "relationship_since": str(c.relationship_since),
            "relationship_tenure_years": tenure_years,
            "risk_segment": c.risk_segment,
            "preferred_channel": c.preferred_channel,
            "preferred_time": c.preferred_time,
            "hardship_flag": bool(c.hardship_flag),
            "hardship_reason": c.hardship_reason,
            "accounts": accounts_data,
            "interactions": [
                {"type": i.interaction_type, "date": str(i.interaction_date),
                 "outcome": i.outcome, "notes": i.agent_notes}
                for i in interactions
            ],
            "disputes": [
                {"dispute_id": d.dispute_id, "type": d.dispute_type, "status": d.status,
                 "opened": str(d.opened_date), "resolved": str(d.resolved_date) if d.resolved_date else None,
                 "collection_hold": bool(d.collection_hold), "description": d.description}
                for d in disputes
            ],
        }

@router.get("/data/customers")
async def get_customers() -> list:
    with db_session() as session:
        return [{"id": id_, "label": label} for id_, label in list_customers(session)]


@router.get("/data/accounts")
async def get_accounts() -> list:
    with db_session() as session:
        return [{"id": id_, "label": label} for id_, label in list_accounts(session)]

