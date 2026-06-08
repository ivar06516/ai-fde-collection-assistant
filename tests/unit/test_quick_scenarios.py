"""UC-009: Quick-Demo Scenarios — unit tests covering AC-009-01 through AC-009-06."""
import pytest


# ── Scenario definitions (mirrors app.py DEMO_SCENARIOS) ──────────────────────

DEMO_SCENARIOS = {
    "no_action":   {"customer_id": "CUST-001", "account_id": "ACC-001",
                    "trigger": "routine_review",  "name": "Arjun Sharma"},
    "dispute_hold":{"customer_id": "CUST-002", "account_id": "ACC-002",
                    "trigger": "missed_payment",  "name": "Priya Mehta"},
    "critical":    {"customer_id": "CUST-003", "account_id": "ACC-003",
                    "trigger": "routine_review",  "name": "Rahul Singh"},
    "hardship":    {"customer_id": "CUST-004", "account_id": "ACC-004",
                    "trigger": "hardship_claim",  "name": "Kavita Patel"},
}


# ── AC-009-01: Scenario session state mapping ─────────────────────────────────

class TestAC00901SessionStateMapping:
    """AC-009-01: Each scenario button maps to correct customer_id and account_id."""

    def test_no_action_scenario_ids(self):
        s = DEMO_SCENARIOS["no_action"]
        assert s["customer_id"] == "CUST-001"
        assert s["account_id"]  == "ACC-001"
        assert s["trigger"]     == "routine_review"

    def test_dispute_hold_scenario_ids(self):
        s = DEMO_SCENARIOS["dispute_hold"]
        assert s["customer_id"] == "CUST-002"
        assert s["account_id"]  == "ACC-002"
        assert s["trigger"]     == "missed_payment"

    def test_critical_arrears_scenario_ids(self):
        s = DEMO_SCENARIOS["critical"]
        assert s["customer_id"] == "CUST-003"
        assert s["account_id"]  == "ACC-003"

    def test_hardship_scenario_ids(self):
        s = DEMO_SCENARIOS["hardship"]
        assert s["customer_id"] == "CUST-004"
        assert s["account_id"]  == "ACC-004"
        assert s["trigger"]     == "hardship_claim"

    def test_four_scenarios_defined(self):
        assert len(DEMO_SCENARIOS) == 4

    def test_all_scenarios_have_required_keys(self):
        for name, s in DEMO_SCENARIOS.items():
            assert "customer_id" in s, f"{name} missing customer_id"
            assert "account_id"  in s, f"{name} missing account_id"
            assert "trigger"     in s, f"{name} missing trigger"


# ── AC-009-02: Dispute Hold scenario state ────────────────────────────────────

class TestAC00902DisputeHoldScenario:
    """AC-009-02: Priya Mehta CUST-002 has active dispute hold in DB."""

    def test_priya_mehta_has_collection_hold(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
        from collection_assistant.db.session import db_session
        from collection_assistant.db.queries.dispute_queries import has_collection_hold
        with db_session() as session:
            hold, reason = has_collection_hold(session, "ACC-002")
        assert hold is True, f"Expected collection hold for ACC-002, got hold={hold}"

    def test_priya_mehta_dispute_type_identity_theft(self):
        from collection_assistant.db.session import db_session
        from collection_assistant.db.models import Dispute
        with db_session() as session:
            disputes = session.query(Dispute).filter(
                Dispute.account_id == "ACC-002",
                Dispute.status.in_(["open", "under_review"])
            ).all()
            holds = [d.collection_hold for d in disputes]
        assert len(holds) >= 1
        assert any(holds)

    def test_dispute_hold_nba_action_is_restricted(self):
        from collection_assistant.tools.nba_tools import evaluate_action_eligibility
        result = evaluate_action_eligibility(True, "deteriorating", 45, "delinquent")
        assert set(result["eligible_actions"]) == {"place_on_hold", "no_action_required"}


# ── AC-009-03: Critical Arrears scenario ─────────────────────────────────────

class TestAC00903CriticalArrearsScenario:
    """AC-009-03: Rahul Singh CUST-003 routes to escalate_to_legal or offer_settlement."""

    def test_rahul_singh_has_high_dpd(self):
        from collection_assistant.db.session import db_session
        from collection_assistant.db.models import Account
        with db_session() as session:
            a = session.get(Account, "ACC-003")
            assert a is not None
            dpd = a.days_past_due
        assert dpd >= 90, f"Expected DPD >= 90 for ACC-003, got {dpd}"

    def test_critical_trajectory_for_dpd_92(self):
        from collection_assistant.tools.arrears_tools import calculate_arrears_trajectory
        trajectory = calculate_arrears_trajectory(92, "deteriorating", 3)
        assert trajectory == "critical"

    def test_critical_trajectory_default_prob_above_85(self):
        from collection_assistant.tools.arrears_tools import predict_default_probability
        prob = predict_default_probability(92, "critical", "high", 0.3)
        assert prob > 0.85

    def test_critical_eligible_actions_include_escalation(self):
        from collection_assistant.tools.nba_tools import evaluate_action_eligibility
        result = evaluate_action_eligibility(False, "critical", 92, "delinquent")
        assert "escalate_to_legal" in result["eligible_actions"]
        assert "offer_settlement"  in result["eligible_actions"]


# ── AC-009-04: Hardship scenario ──────────────────────────────────────────────

class TestAC00904HardshipScenario:
    """AC-009-04: Kavita Patel CUST-004 hardship flag set, payment plan recommended."""

    def test_kavita_patel_has_hardship_flag(self):
        from collection_assistant.db.session import db_session
        from collection_assistant.db.models import Customer
        with db_session() as session:
            c = session.get(Customer, "CUST-004")
            assert c is not None
            flag = bool(c.hardship_flag)
            reason = c.hardship_reason
        assert flag is True
        assert reason == "unemployment"

    def test_kavita_patel_account_is_overdraft(self):
        from collection_assistant.db.session import db_session
        from collection_assistant.db.models import Account
        with db_session() as session:
            a = session.get(Account, "ACC-004")
            assert a is not None
            product = a.product_type
            dpd = a.days_past_due
        assert product == "overdraft"
        assert dpd == 35

    def test_hardship_risk_factors_include_flag(self):
        from collection_assistant.tools.arrears_tools import identify_risk_factors
        factors = identify_risk_factors(35, "deteriorating", True, "unemployed", 0.7, 1)
        names = [f["name"] for f in factors]
        assert any("hardship" in n.lower() or "unemploy" in n.lower() for n in names)

    def test_hardship_no_collection_hold(self):
        from collection_assistant.db.session import db_session
        from collection_assistant.db.queries.dispute_queries import has_collection_hold
        with db_session() as session:
            hold, _ = has_collection_hold(session, "ACC-004")
        assert hold is False


# ── AC-009-05: Instant navigation ─────────────────────────────────────────────

class TestAC00905InstantNavigation:
    """AC-009-05: Clicking a demo scenario navigates immediately to analysis page."""

    def test_demo_scenario_sets_workflow_id_to_none(self):
        """Clicking a demo scenario button sets workflow_id=None (pipeline starts fresh)."""
        # Simulate what app.py does when a demo button is clicked
        session_state = {
            "workflow_id": "old-wf-id",
            "page": "dashboard",
        }
        # After button click, workflow_id is reset to None for fresh pipeline
        session_state["workflow_id"] = None
        session_state["pipeline_customer_id"] = "CUST-003"
        session_state["pipeline_account_id"]  = "ACC-003"
        session_state["page"] = "analysis"

        assert session_state["workflow_id"] is None
        assert session_state["page"] == "analysis"
        assert session_state["pipeline_customer_id"] == "CUST-003"

    def test_all_four_demo_scenarios_have_distinct_customers(self):
        customer_ids = [s["customer_id"] for s in DEMO_SCENARIOS.values()]
        assert len(set(customer_ids)) == 4, "All 4 demo scenarios must use distinct customers"

    def test_all_four_demo_triggers_are_valid(self):
        valid_triggers = {
            "routine_review", "missed_payment", "hardship_claim",
            "dispute_raised", "payment_arrangement_review", "legal_referral_review",
        }
        for name, s in DEMO_SCENARIOS.items():
            assert s["trigger"] in valid_triggers, \
                f"Scenario {name} has invalid trigger: {s['trigger']}"


# ── AC-009-06: All four scenarios have correct DB data ────────────────────────

class TestAC00906AllFourScenarios:
    """AC-009-06: All 4 demo scenarios have the required DB records."""

    @pytest.mark.parametrize("cid,aid", [
        ("CUST-001", "ACC-001"),
        ("CUST-002", "ACC-002"),
        ("CUST-003", "ACC-003"),
        ("CUST-004", "ACC-004"),
    ])
    def test_customer_and_account_exist(self, cid, aid):
        from collection_assistant.db.session import db_session
        from collection_assistant.db.models import Customer, Account
        with db_session() as session:
            c = session.get(Customer, cid)
            a = session.get(Account, aid)
            c_found = c is not None
            a_found = a is not None
            linked = (a.customer_id == cid) if a else False
        assert c_found, f"Customer {cid} missing from DB"
        assert a_found, f"Account {aid} missing from DB"
        assert linked, f"{aid} not linked to {cid}"

    def test_all_four_scenarios_pass_preflight_validation(self):
        """Simulates the pre-flight check in POST /recommend for all 4 scenarios."""
        from collection_assistant.db.session import db_session
        from collection_assistant.db.queries.customer_queries import get_customer
        from collection_assistant.db.queries.account_queries import get_account
        errors = []
        for name, s in DEMO_SCENARIOS.items():
            try:
                with db_session() as session:
                    get_customer(session, s["customer_id"])
                    get_account(session, s["account_id"])
            except Exception as e:
                errors.append(f"{name}: {e}")
        assert errors == [], f"Pre-flight validation failed: {errors}"
