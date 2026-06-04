"""Collections API routes - trigger pipeline, stream SSE, retrieve audit."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from collection_assistant.db.queries.account_queries import list_accounts
from collection_assistant.db.queries.audit_queries import get_audit_record, list_recent_audits
from collection_assistant.db.queries.customer_queries import list_customers
from collection_assistant.db.session import db_session
from collection_assistant.exceptions import AccountNotFoundError, CustomerNotFoundError
from collection_assistant.graph.collection_graph import run_collection_pipeline
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus

router = APIRouter(prefix="/collections")

# In-memory store for active/completed workflows (PoC: replace with Redis for prod)
_workflow_store: dict[str, CollectionWorkflowState] = {}
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
    workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
    event_bus.register(workflow_id)
    _workflow_store[workflow_id] = {"workflow_status": "in_progress"}

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
        seen = 0
        max_wait = 60  # seconds
        waited = 0
        while waited < max_wait:
            events = event_bus.get_events(workflow_id)
            while seen < len(events):
                event = events[seen]
                yield f"data: {json.dumps(event)}\n\n"
                seen += 1
                if event["type"] == "workflow_complete":
                    return
                if event["type"] == "workflow_error":
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


@router.get("/data/customers")
async def get_customers() -> list:
    with db_session() as session:
        return [{"id": id_, "label": label} for id_, label in list_customers(session)]


@router.get("/data/accounts")
async def get_accounts() -> list:
    with db_session() as session:
        return [{"id": id_, "label": label} for id_, label in list_accounts(session)]

