"""UC-007: Audit Trail and Decision Lineage — unit tests covering AC-007-01 through AC-007-07."""
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from collection_assistant.tools.audit_tools import build_audit_record


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_state(
    workflow_id="wf-test-007",
    customer_id="CUST-002",
    account_id="ACC-002",
    trigger_context="routine_review",
    workflow_status="completed",
    total_ms=18000,
    collection_hold=False,
    nba_action="place_on_hold",
    nba_confidence=0.99,
    blocked_by_dispute=False,
) -> dict:
    """Build a minimal but realistic completed workflow state."""
    statuses = {
        "customer_profile":   {"stage":1,"status":"completed","elapsed_ms":4100,"error":None,"started_at":None,"completed_at":None},
        "account_profile":    {"stage":1,"status":"completed","elapsed_ms":5200,"error":None,"started_at":None,"completed_at":None},
        "arrears_prediction": {"stage":2,"status":"completed","elapsed_ms":80,  "error":None,"started_at":None,"completed_at":None},
        "dispute":            {"stage":2,"status":"completed","elapsed_ms":4400,"error":None,"started_at":None,"completed_at":None},
        "nba":                {"stage":3,"status":"completed","elapsed_ms":6300,"error":None,"started_at":None,"completed_at":None},
        "audit":              {"stage":3,"status":"completed","elapsed_ms":None,"error":None,"started_at":None,"completed_at":None},
    }
    return {
        "workflow_id":      workflow_id,
        "customer_id":      customer_id,
        "account_id":       account_id,
        "trigger_context":  trigger_context,
        "workflow_status":  workflow_status,
        "total_ms":         total_ms,
        "error_log":        [],
        "started_at":       datetime.now(timezone.utc).isoformat(),
        "completed_at":     datetime.now(timezone.utc).isoformat(),
        "agent_statuses":   statuses,
        "customer_profile": {
            "customer_id": customer_id, "full_name": "Priya Mehta",
            "risk_segment": "medium", "hardship_flag": False,
            "summary": "Medium risk customer.",
        },
        "account_profile": {
            "account_id": account_id, "days_past_due": 45,
            "account_status": "delinquent", "outstanding_balance": 2300.0,
            "on_time_payment_rate": 0.92, "summary": "Delinquent credit card.",
        },
        "arrears_prediction": {
            "arrears_trajectory": "deteriorating",
            "default_probability": 0.42,
            "predicted_dpd_90": 95,
            "confidence_score": 0.85,
            "summary": "Deteriorating trajectory.",
        },
        "dispute_summary": {
            "account_id": account_id,
            "collection_hold": collection_hold,
            "hold_reason": "identity_theft dispute (DISP-001)" if collection_hold else None,
            "total_open_disputes": 1 if collection_hold else 0,
            "active_disputes": [],
            "resolved_disputes": [],
            "summary": "Hold active." if collection_hold else "No hold.",
        },
        "nba_recommendation": {
            "action": nba_action,
            "channel": "none" if collection_hold else "mobile",
            "rationale": "Collection hold active. " * 5 if collection_hold else "Call customer. " * 5,
            "confidence_score": nba_confidence,
            "urgency": "high",
            "blocked_by_dispute": blocked_by_dispute,
            "alternative_actions": [],
            "summary": f"NBA: {nba_action}",
        },
        "audit_record": None,
    }


# ── AC-007-01: All six agents in lineage ──────────────────────────────────────

class TestAC00701AllSixAgents:
    """AC-007-01: decision_lineage must contain exactly 6 entries in pipeline order."""

    def test_exactly_six_agents_in_lineage(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state)
        assert len(record["decision_lineage"]) == 6

    def test_agent_order_matches_pipeline(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state)
        agents = [step["agent"] for step in record["decision_lineage"]]
        assert agents == [
            "customer_profile", "account_profile", "arrears_prediction",
            "dispute", "nba", "audit",
        ]

    def test_all_agents_have_status(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state)
        for step in record["decision_lineage"]:
            assert "status" in step
            assert step["status"] in ("completed", "error", "unknown", "waiting", "running")

    def test_audit_is_sixth_entry(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state, audit_elapsed_ms=22)
        sixth = record["decision_lineage"][5]
        assert sixth["agent"] == "audit"
        assert sixth["elapsed_ms"] == 22


# ── AC-007-02: Output summaries match state ────────────────────────────────────

class TestAC00702OutputSummariesMatchState:
    """AC-007-02: Each step's output_keys reflect actual state output keys."""

    def test_account_profile_output_keys_present(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state)
        ap_step = next(s for s in record["decision_lineage"] if s["agent"] == "account_profile")
        assert "days_past_due" in ap_step["output_keys"]
        assert "account_status" in ap_step["output_keys"]

    def test_nba_output_keys_present(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state)
        nba_step = next(s for s in record["decision_lineage"] if s["agent"] == "nba")
        assert "action" in nba_step["output_keys"]
        assert "confidence_score" in nba_step["output_keys"]

    def test_nba_action_matches_state(self):
        state = _make_state(nba_action="offer_settlement")
        record = build_audit_record("wf-test-007", state)
        assert record["nba_action"] == "offer_settlement"

    def test_nba_confidence_matches_state(self):
        state = _make_state(nba_confidence=0.87)
        record = build_audit_record("wf-test-007", state)
        assert record["nba_confidence"] == 0.87

    def test_dispute_output_keys_contain_collection_hold(self):
        state = _make_state(collection_hold=True)
        record = build_audit_record("wf-test-007", state)
        dis_step = next(s for s in record["decision_lineage"] if s["agent"] == "dispute")
        assert "collection_hold" in dis_step["output_keys"]


# ── AC-007-03: Elapsed times recorded ────────────────────────────────────────

class TestAC00703ElapsedTimes:
    """AC-007-03: Elapsed ms recorded for agents that ran; audit entry gets its own."""

    def test_completed_agents_have_elapsed_ms(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state, audit_elapsed_ms=15)
        for step in record["decision_lineage"]:
            if step["agent"] != "audit":
                assert step["elapsed_ms"] is not None and step["elapsed_ms"] > 0

    def test_audit_elapsed_ms_set_from_parameter(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state, audit_elapsed_ms=42)
        audit_step = record["decision_lineage"][5]
        assert audit_step["elapsed_ms"] == 42

    def test_total_ms_in_record(self):
        state = _make_state(total_ms=18000)
        record = build_audit_record("wf-test-007", state)
        assert record["total_ms"] == 18000


# ── AC-007-04: Audit record fields ────────────────────────────────────────────

class TestAC00704AuditRecordPersists:
    """AC-007-04: Build record has all required fields for DB persistence."""

    def test_record_has_workflow_id(self):
        state = _make_state(workflow_id="wf-abc-123")
        record = build_audit_record("wf-abc-123", state)
        assert record["workflow_id"] == "wf-abc-123"

    def test_record_has_nba_action(self):
        state = _make_state(nba_action="escalate_to_legal")
        record = build_audit_record("wf-test-007", state)
        assert record["nba_action"] == "escalate_to_legal"

    def test_record_has_workflow_status_completed(self):
        state = _make_state(workflow_status="completed")
        record = build_audit_record("wf-test-007", state)
        assert record["workflow_status"] == "completed"

    def test_record_has_audit_timestamp(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state)
        assert "audit_timestamp" in record
        assert "T" in record["audit_timestamp"]  # ISO format

    def test_record_is_json_serialisable(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state)
        serialised = json.dumps(record, default=str)
        parsed = json.loads(serialised)
        assert parsed["workflow_id"] == "wf-test-007"

    def test_record_has_all_required_keys(self):
        state = _make_state()
        record = build_audit_record("wf-test-007", state)
        required = {"workflow_id","customer_id","account_id","trigger_context",
                    "audit_timestamp","nba_action","decision_lineage",
                    "workflow_status","total_ms"}
        assert required.issubset(set(record.keys()))


# ── AC-007-05: Dispute hold visible in audit trail ────────────────────────────

class TestAC00705DisputeHoldVisible:
    """AC-007-05: Priya Mehta hold scenario — dispute and NBA steps show hold."""

    def test_collection_hold_in_record_when_active(self):
        state = _make_state(collection_hold=True, nba_action="place_on_hold",
                             blocked_by_dispute=True)
        record = build_audit_record("wf-test-007", state)
        assert record["collection_hold"] is True

    def test_nba_blocked_by_dispute_in_record(self):
        state = _make_state(collection_hold=True, nba_action="place_on_hold",
                             blocked_by_dispute=True)
        record = build_audit_record("wf-test-007", state)
        assert record["nba_blocked_by_dispute"] is True

    def test_dispute_step_output_keys_include_hold(self):
        state = _make_state(collection_hold=True)
        record = build_audit_record("wf-test-007", state)
        dis_step = next(s for s in record["decision_lineage"] if s["agent"] == "dispute")
        assert "collection_hold" in dis_step["output_keys"]

    def test_no_hold_shows_false(self):
        state = _make_state(collection_hold=False)
        record = build_audit_record("wf-test-007", state)
        assert record["collection_hold"] is False
        assert record["nba_blocked_by_dispute"] is False

    def test_priya_mehta_scenario(self):
        """Priya Mehta CUST-002: identity_theft dispute, hold=True, NBA=place_on_hold."""
        state = _make_state(
            customer_id="CUST-002", account_id="ACC-002",
            collection_hold=True, nba_action="place_on_hold",
            nba_confidence=0.99, blocked_by_dispute=True,
        )
        record = build_audit_record("wf-test-007", state)
        assert record["collection_hold"] is True
        assert record["nba_action"] == "place_on_hold"
        assert record["nba_blocked_by_dispute"] is True


# ── AC-007-06: API accessibility ──────────────────────────────────────────────

class TestAC00706APIAccess:
    """AC-007-06: GET /audit endpoint returns valid JSON with audit schema."""

    @pytest.mark.asyncio
    async def test_audit_api_returns_200_for_existing_run(self):
        from httpx import AsyncClient, ASGITransport
        from collection_assistant.api.main import app
        from collection_assistant.db.session import db_session
        from collection_assistant.db.models import WorkflowAudit
        import json as _json

        # Seed a minimal audit record
        test_wf_id = "wf-test-ac007-api"
        with db_session() as session:
            existing = session.get(WorkflowAudit, test_wf_id)
            if not existing:
                session.add(WorkflowAudit(
                    workflow_id=test_wf_id,
                    customer_id="CUST-002", account_id="ACC-002",
                    trigger_context="routine_review",
                    nba_action="place_on_hold", nba_channel="none",
                    nba_confidence=0.99, nba_rationale="Hold active.",
                    full_state_json=_json.dumps({"workflow_status": "completed"}),
                    status="completed", total_ms=18000,
                ))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/collections/{test_wf_id}/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == test_wf_id
        assert data["nba_action"] == "place_on_hold"
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_audit_api_returns_404_for_unknown_workflow(self):
        from httpx import AsyncClient, ASGITransport
        from collection_assistant.api.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/collections/wf-does-not-exist-xyz/audit")

        assert response.status_code == 404


# ── AC-007-07: No LLM call in audit agent ─────────────────────────────────────

class TestAC00707NoLLMCall:
    """AC-007-07: Audit Agent is deterministic — build_audit_record makes no LLM call."""

    def test_build_audit_record_has_no_llm_imports(self):
        import ast
        with open("src/collection_assistant/tools/audit_tools.py") as f:
            tree = ast.parse(f.read())
        imports = [
            node.names[0].name if isinstance(node, ast.Import) else node.module
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        llm_imports = [i for i in imports if i and ("groq" in i or "langchain" in i or "openai" in i)]
        assert llm_imports == [], f"LLM imports found in audit_tools: {llm_imports}"

    def test_audit_agent_has_no_llm_call(self):
        import ast
        with open("src/collection_assistant/agents/audit.py") as f:
            src = f.read()
        assert "get_llm" not in src, "audit.py should not call get_llm()"
        assert "ChatGroq" not in src, "audit.py should not use ChatGroq directly"

    def test_build_audit_record_is_pure_function(self):
        """Calling build_audit_record twice with same input returns same output."""
        state = _make_state()
        r1 = build_audit_record("wf-idempotent", state, audit_elapsed_ms=10)
        r2 = build_audit_record("wf-idempotent", state, audit_elapsed_ms=10)
        assert r1["nba_action"] == r2["nba_action"]
        assert r1["decision_lineage"] == r2["decision_lineage"]
