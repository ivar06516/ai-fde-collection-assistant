from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class AgentStatus(TypedDict):
    stage: int
    status: str   # waiting | running | completed | error
    started_at: Optional[str]
    completed_at: Optional[str]
    elapsed_ms: Optional[int]
    error: Optional[str]


class CollectionWorkflowState(TypedDict):
    # Inputs
    workflow_id: str
    customer_id: str
    account_id: str
    trigger_context: str

    # Stage tracking
    agent_statuses: dict[str, AgentStatus]

    # Agent outputs (None until agent completes)
    customer_profile: Optional[dict[str, Any]]
    account_profile: Optional[dict[str, Any]]
    arrears_prediction: Optional[dict[str, Any]]
    dispute_summary: Optional[dict[str, Any]]
    nba_recommendation: Optional[dict[str, Any]]
    audit_record: Optional[dict[str, Any]]

    # Pipeline state
    workflow_status: str   # in_progress | completed | error | human_review
    error_log: list[str]
    started_at: str
    completed_at: Optional[str]
    total_ms: Optional[int]
