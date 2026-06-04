"""Pytest configuration and shared fixtures."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from collection_assistant.db.models import Base
from collection_assistant.graph.state import CollectionWorkflowState


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_state() -> CollectionWorkflowState:
    return CollectionWorkflowState(
        workflow_id="wf-test-001",
        customer_id="CUST-001",
        account_id="ACC-001",
        trigger_context="routine_review",
        agent_statuses={},
        customer_profile=None,
        account_profile=None,
        arrears_prediction=None,
        dispute_summary=None,
        nba_recommendation=None,
        audit_record=None,
        workflow_status="in_progress",
        error_log=[],
        started_at="2026-01-01T00:00:00+00:00",
        completed_at=None,
        total_ms=None,
    )
