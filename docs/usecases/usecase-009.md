# UC-009: Load Quick-Demo Scenario

## Overview

| Field | Value |
|---|---|
| **ID** | UC-009 |
| **Actor** | Demo Presenter |
| **Goal** | Pre-populate the Input Panel with a named demo scenario using a single button click, so a specific pipeline path can be demonstrated without manually typing IDs |
| **Priority** | P1 — demo reliability, not core functionality |
| **Delivery Phase** | Phase 10 (demo polish) |
| **UI Location** | Page 1 — Portfolio Dashboard, customer row Analyse buttons |

---

## Preconditions

- DB is seeded with all 10 named scenarios (UC-008 complete)
- User is on Screen 1 (Input Panel)
- Four quick-load buttons are visible: Standard Case, Dispute Hold, Critical Arrears, Improving Customer

---

## Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | FDE | Clicks a quick-load button (e.g., **Critical Arrears**) | `st.session_state` updated: `customer_id = "CUST-003"`, `account_id = "ACC-003"`, `trigger_context = "routine_review"` |
| 2 | System | Form fields auto-populate | Customer ID, Account ID, Trigger show the scenario values |
| 3 | FDE | Optionally reviews pre-filled fields; clicks **Run Analysis** | Proceeds as UC-001 from step 3 onwards |
| 4 | System | Pipeline runs with the scenario's data | Results reflect the expected NBA action for that scenario |

---

## Scenario Button Mapping

| Button Label | Customer ID | Account ID | Trigger | Expected NBA Action | Key Demonstration |
|---|---|---|---|---|---|
| **No Action / Current** | CUST-001 Arjun Sharma | ACC-001 Personal Loan | routine_review | `no_action_required` | Happy path — DPD=0, low risk, all payments on time |
| **Dispute Hold** | CUST-002 Priya Mehta | ACC-002 Credit Card | missed_payment | `place_on_hold` | Dispute Agent returning hold; NBA hard constraint enforced |
| **Critical Arrears** | CUST-003 Rahul Singh | ACC-003 Personal Loan | routine_review | `offer_settlement` or `escalate_to_legal` | Arrears trajectory=critical, DPD=92, default_probability > 0.85 |
| **Hardship / Payment Plan** | CUST-004 Kavita Patel | ACC-004 Overdraft | hardship_claim | `offer_payment_plan` | Hardship flag active (unemployment), DPD=35, payment plan recommended |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | Scenario data not in DB (DB not seeded) | Button click populates form; Run Analysis fails at API with 404; UI shows "Customer not found — seed database first" |
| AF-02 | User modifies fields after quick-load | Modified values used; scenario label in UI clears to avoid confusion |

---

## Postconditions

- Input form is pre-populated with the scenario's `customer_id`, `account_id`, `trigger_context`
- User can immediately click Run Analysis without typing
- The pipeline runs UC-001 with the pre-selected data

---

## Acceptance Criteria

### AC-009-01: Standard Case Button Populates Correct Fields
- **Given** the user is on Screen 1 (Input Panel)
- **When** the **Standard Case** button is clicked
- **Then** `customer_id = "CUST-001"`, `account_id = "ACC-001"`, `trigger_context = "routine_review"` are pre-filled in the form
- **Verified by** unit test test_quick_scenarios.py::test_no_action_scenario

### AC-009-02: Dispute Hold Scenario Produces Hold Result
- **Given** the **Dispute Hold** button is clicked and Run Analysis is triggered
- **When** the pipeline completes
- **Then** `nba_recommendation.action = "place_on_hold"` and `dispute_summary.collection_hold = True`
- **Verified by** Phase 11 unit test test_quick_scenarios.py::test_dispute_hold_scenario

### AC-009-03: Critical Arrears Scenario Produces Escalation
- **Given** the **Critical Arrears** button is clicked and Run Analysis is triggered
- **When** the pipeline completes
- **Then** `arrears_prediction.arrears_trajectory = "critical"` and `nba_recommendation.action` is one of `"escalate_to_legal"` or `"offer_settlement"`
- **Verified by** Phase 11 unit test test_quick_scenarios.py::test_critical_arrears_scenario

### AC-009-04: Hardship Scenario Produces Payment Plan
- **Given** the **Improving Customer** button is clicked and Run Analysis is triggered
- **When** the pipeline completes
- **Then** `arrears_prediction.arrears_trajectory = "improving"` and `nba_recommendation.action` is one of `"no_action_required"` or `"send_sms"`
- **Verified by** Phase 11 unit test test_quick_scenarios.py::test_hardship_scenario

### AC-009-05: Button Click Navigates Instantly to Analysis Page
- **Given** the FDE clicks **Critical Arrears**
- **When** the form is populated
- **Then** the app navigates immediately to Page 2 (Analysis) showing the customer banner; the pipeline starts in the background and live agent status appears; no separate Run Analysis click required
- **Verified by** unit test test_quick_scenarios.py::test_instant_navigation

### AC-009-06: All Four Scenarios Run End-to-End Successfully
- **Given** all 10 named scenarios are seeded in the DB
- **When** each of the four quick-load scenarios is run in sequence
- **Then** all four complete with `workflow_status = "completed"` and the expected NBA action (per scenario button mapping table above)
- **Verified by** unit test test_quick_scenarios.py::test_all_four_scenarios_complete

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §5.3 (10 named scenarios spec), §10.2 Screen 1 quick-load buttons, §10.4 UX Principle: "one-click demo scenarios" |
| **Deployment** | Streamlit `st.session_state` — no API call on button click; pre-seeded SQLite data on Render |
| **Observability** | `trigger_context` and `customer_id` labels in `collection_workflow_total` counter capture which scenario was run; demo session creates a visible metrics spike in Grafana — useful for showing dashboards to client |
| **SRE** | Demo reliability: if any scenario fails, the demo fails; all 4 scenarios must pass in Phase 11 integration tests; Render cold-start (30s) is the biggest demo risk — UptimeRobot keep-warm monitor prevents cold starts during demo window |

