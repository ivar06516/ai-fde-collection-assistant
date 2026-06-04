# Use Case Document — AI FDE Collection Assistant

## Document Purpose

Each use case in this document is written to arrive at four dimensions simultaneously:
**Requirements** (what must be built) → **Deployment** (where it runs) → **Observability** (what it emits) → **SRE** (how it is kept reliable).

Every use case references specific sections of the project documents so that a reader can trace any requirement, platform decision, metric, or SLO back to the user need that justified it.

---

## Actors

| Actor | Description | Frequency |
|---|---|---|
| **Collection Agent** | Primary user — debt collection specialist who runs analyses and acts on NBA recommendations | Multiple times per day |
| **FDE / Demo Presenter** | Forward Deployed Engineer — sets up data, runs demo for client | Per demo session |
| **Compliance Officer** | Reviews audit trails, validates decision lineage, may override recommendations | Spot-check / escalation |
| **DevOps / SRE Engineer** | Monitors system health, responds to incidents, deploys new versions | Continuous |
| **Data Admin** | Seeds and manages the synthetic customer database | On setup / reset |
| **System** | The automated multi-agent pipeline (Orchestrator + 5 agents) | Per workflow trigger |

---

## Use Case Index

| ID | Title | Actor | Priority | Phase |
|---|---|---|---|---|
| [UC-001](#uc-001-run-full-collection-analysis) | Run Full Collection Analysis | Collection Agent | P0 | Phase 7–9 |
| [UC-002](#uc-002-build-customer-profile) | Build Customer Profile | System | P0 | Phase 3 |
| [UC-003](#uc-003-build-account-profile) | Build Account Profile | System | P0 | Phase 3 |
| [UC-004](#uc-004-predict-arrears-trajectory) | Predict Arrears Trajectory | System | P0 | Phase 4 |
| [UC-005](#uc-005-detect-disputes-and-collection-hold) | Detect Disputes and Collection Hold | System | P0 | Phase 5 |
| [UC-006](#uc-006-generate-next-best-action-recommendation) | Generate Next Best Action Recommendation | System | P0 | Phase 6 |
| [UC-007](#uc-007-review-audit-trail-and-decision-lineage) | Review Audit Trail and Decision Lineage | Compliance Officer | P0 | Phase 7–9 |
| [UC-008](#uc-008-seed-synthetic-customer-database) | Seed Synthetic Customer Database | Data Admin / FDE | P0 | Phase 2 |
| [UC-009](#uc-009-load-quick-demo-scenario) | Load Quick-Demo Scenario | FDE / Demo Presenter | P1 | Phase 10 |
| [UC-010](#uc-010-monitor-pipeline-health-and-agent-performance) | Monitor Pipeline Health and Agent Performance | DevOps / SRE | P1 | Phase 12, 14 |
| [UC-011](#uc-011-respond-to-service-incident) | Respond to Service Incident | SRE Engineer | P1 | Phase 14–15 |
| [UC-012](#uc-012-deploy-new-version-via-cicd-pipeline) | Deploy New Version via CI/CD Pipeline | DevOps Engineer | P1 | Phase 13 |

---

## UC-001: Run Full Collection Analysis

**Actor:** Collection Agent
**Goal:** Receive a complete, AI-generated Next Best Action recommendation for a specific customer and account by running the full multi-agent pipeline from the UI.
**Priority:** P0 — the core end-to-end scenario every other use case supports.

### Preconditions
- SQLite database is seeded (`seed_db.py` has been run — see UC-008)
- `GROQ_API_KEY` is configured in the deployment environment (free — console.groq.com)
- FastAPI backend is running and healthy (`GET /health` returns 200)
- Streamlit UI is accessible

### Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | Collection Agent | Opens Streamlit UI at the Input Panel (Screen 1) | Screen renders with Customer ID / Account ID dropdowns populated from SQLite DB |
| 2 | Collection Agent | Selects Customer ID (e.g., CUST-001) and Account ID (e.g., ACC-001), sets Trigger to "New Delinquency", clicks **Run Analysis** | UI calls `POST /collections/recommend` with the three inputs |
| 3 | System | FastAPI receives request, creates a `workflow_id`, starts the LangGraph pipeline | Returns `202 Accepted` with `{"workflow_id": "wf-abc123", "status": "in_progress"}` |
| 4 | System | UI immediately opens `GET /collections/{workflow_id}/stream` (SSE) | Execution Panel (Screen 2) appears; agent rows show waiting state |
| 5 | System | Orchestrator launches Stage 1 agents in parallel | SSE events fire: `customer_profile → running`, `account_profile → running` |
| 6 | System | Both Stage 1 agents complete | SSE events fire: both rows update to ✅ Complete with elapsed time |
| 7 | System | Orchestrator launches Stage 2 agents in parallel | SSE events fire: `arrears_prediction → running`, `dispute → running` |
| 8 | System | Both Stage 2 agents complete | SSE events fire: both rows update to ✅ Complete |
| 9 | System | Orchestrator launches NBA Agent (Stage 3) | SSE event fires: `nba → running` |
| 10 | System | NBA Agent produces recommendation; Audit Agent logs the full trail | SSE events fire: NBA ✅, Audit ✅, then `workflow_complete` event |
| 11 | System | UI transitions to Results Dashboard (Screen 3) | All four agent output cards rendered; NBA Recommendation displayed prominently |

### Alternative Flows

| Alt | Condition | System Behaviour |
|---|---|---|
| A1 | Dispute Agent returns `collection_hold = true` | NBA Agent is constrained — only `place_on_hold` or `no_action_required` allowed; NBA card shows hold reason |
| A2 | Arrears Prediction returns `trajectory = critical` | NBA Agent prefers `escalate_to_legal` or `offer_settlement`; confidence bar reflects urgency |
| A3 | An agent fails and exhausts 3 retries | Agent row shows ❌ Error; `workflow_status = "error"`; pipeline degrades gracefully; error logged in `error_log` |
| A4 | Customer ID not found in DB | FastAPI returns 404; UI shows "Customer not found — check ID or re-seed database" |
| A5 | Groq API timeout | Agent retried (exponential backoff × 3); if all fail, `workflow_status = "error"` |

### Postconditions
- `workflow_audit` table record written with full `CollectionWorkflowState` JSON
- NBA recommendation surfaced to user in Screen 3
- Full audit trail available via `GET /collections/{workflow_id}/audit`

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | REQUIREMENTS.md §1.2, §2.1, §2.2.1–2.2.7, §10.2 Screens 1–3, §11 | All 7 agents, all 3 API endpoints, all 4 UI screens |
| **Deployment** | Render.com (FastAPI), Streamlit Community Cloud (UI), SQLite on Render | Pipeline runs on Render; UI served from Streamlit Cloud; DB co-located with API |
| **Observability** | `collection_workflow_total` counter, `collection_workflow_duration_seconds` histogram; root trace span for workflow; `workflow_started` + `workflow_complete` log events | Metrics: total runs and end-to-end latency. Trace: full pipeline visible in Tempo. Logs: Loki query by `workflow_id` |
| **SRE** | SLO: pipeline success rate ≥ 95%, p95 latency ≤ 15s; Alert: error rate > 10% over 5 min; Runbook: §8.3 "Pipeline Failure Surge" | If this UC fails at scale, the error budget is consumed; latency alert fires if Stage 3 (NBA) exceeds 5s |

---

## UC-002: Build Customer Profile

**Actor:** System (Customer Profile Agent, triggered by Orchestrator)
**Goal:** Retrieve and synthesise a 360° customer profile from the `customers` and `interaction_history` SQLite tables to populate `state.customer_profile`.
**Priority:** P0 — upstream dependency for UC-004 and UC-006.

### Preconditions
- `customer_id` is present in `state`
- SQLite DB is seeded and reachable
- Stage 1 parallel execution has been started by Orchestrator

### Main Flow

| Step | Action | Detail |
|---|---|---|
| 1 | Agent calls `get_customer_demographics(customer_id)` | Queries `customers` table — returns name, DOB, employment, income, preferred channel/time, hardship flag |
| 2 | Agent calls `get_contact_preferences(customer_id)` | Reads `preferred_channel` and `preferred_time` from `customers` |
| 3 | Agent calls `get_interaction_history(customer_id)` | Queries `interaction_history` — returns last 12 interactions with outcomes |
| 4 | Agent calls `classify_risk_segment(...)` | Applies risk logic over demographics + interaction pattern to assign `low / medium / high / hardship` |
| 5 | Agent calls `detect_hardship_signals(...)` | Checks `hardship_flag`, `employment_status`, `annual_income` for hardship indicators |
| 6 | Agent returns `CustomerProfile` TypedDict | Written to `state.customer_profile` by Orchestrator |
| 7 | SSE event emitted | `{"agent": "customer_profile", "stage": 1, "status": "complete", ...}` |

### Alternative Flows

| Alt | Condition | Behaviour |
|---|---|---|
| A1 | Customer ID not found in DB | Agent raises `CustomerNotFoundError`; Orchestrator logs error; pipeline sets `workflow_status = "error"` |
| A2 | No interaction history found | `prior_collection_interactions = 0`; `hardship_indicators = ["none"]`; risk segment inferred from demographics only |
| A3 | LLM call times out | Retry × 3 with exponential backoff; if all fail, agent marks itself as failed |

### Postconditions
- `state.customer_profile` populated with all fields from `CustomerProfile` TypedDict
- Audit Agent will include this in decision lineage

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §2.2.2 (Customer Profile Agent), §5.2 (`customers` + `interaction_history` tables), §6.1 Stage 1 | Agent definition, DB schema, pipeline position |
| **Deployment** | Render.com (FastAPI + SQLite); Groq Llama 3.3 70B via Groq API (free) | Agent runs in FastAPI service; queries local SQLite file |
| **Observability** | `agent_execution_duration_seconds{agent="customer_profile"}` histogram; `agent_started` + `agent_complete` log events; child span `stage1.customer_profile` in Tempo trace | Per-agent latency tracked. Trace shows this as a parallel sibling of Account Profile Agent |
| **SRE** | Agent error rate SLO ≤ 2%; Alert: `agent_failed` log event triggers error-rate alert; Runbook §8.3 "LLM API timeout" | Risk: if Groq API is slow, Stage 1 is the bottleneck. Parallel execution with Account Profile mitigates partial slowness |

---

## UC-003: Build Account Profile

**Actor:** System (Account Profile Agent, triggered by Orchestrator)
**Goal:** Retrieve and summarise the full account snapshot — balance, DPD, product details, payment history — from `accounts` and `payment_history` tables to populate `state.account_profile`.
**Priority:** P0 — upstream dependency for UC-004, UC-005, and UC-006.

### Preconditions
- `account_id` is present in `state`
- Stage 1 parallel execution is running (alongside UC-002)

### Main Flow

| Step | Action | Detail |
|---|---|---|
| 1 | Agent calls `get_account_balance(account_id)` | Queries `accounts` table — returns `outstanding_balance`, `original_balance`, `interest_rate` |
| 2 | Agent calls `get_delinquency_status(account_id)` | Returns `days_past_due`, `account_status`, `delinquency_start` |
| 3 | Agent calls `get_payment_history(account_id)` | Queries `payment_history` — returns last 18 months of `{month, amount_due, amount_paid, on_time}` records |
| 4 | Agent calls `get_linked_accounts(customer_id)` | Returns list of other account IDs linked to same customer |
| 5 | Agent calls `get_product_details(account_id)` | Returns `product_type`, `credit_limit` (if applicable), `next_due_date`, `next_due_amount` |
| 6 | Agent synthesises `AccountProfile` TypedDict | Written to `state.account_profile` by Orchestrator |
| 7 | SSE event emitted | `{"agent": "account_profile", "stage": 1, "status": "complete", ...}` |

### Alternative Flows

| Alt | Condition | Behaviour |
|---|---|---|
| A1 | Account has `account_status = "written_off"` | Profile still built; NBA Agent will use this to route towards `flag_for_writeoff` |
| A2 | Account has `account_status = "legal"` | Profile built; NBA Agent will prefer `escalate_to_legal` |
| A3 | Fewer than 3 months of payment history | Arrears Prediction Agent will note low data confidence; `confidence` score reduced |

### Postconditions
- `state.account_profile` populated; payment history (up to 18 months) available for Arrears Prediction Agent

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §2.2.3 (Account Profile Agent), §5.2 (`accounts` + `payment_history` tables), §6.1 Stage 1 | Agent definition, DB schema |
| **Deployment** | Render.com FastAPI + SQLite; Groq Llama 3.3 70B | Parallel execution with UC-002 in same service |
| **Observability** | `agent_execution_duration_seconds{agent="account_profile"}` histogram; `db_query_duration_seconds` histogram for payment history query (up to 18 rows per account); `stage1.account_profile` span in Tempo | DB query latency separately tracked. Long payment history queries are the most expensive DB call in the pipeline |
| **SRE** | Agent error rate SLO ≤ 2%; `db_query_duration_seconds` alert if > 500ms (SQLite on Render should be < 50ms); Runbook §8.3 "SQLite locked" | SQLite single-writer constraint: Account and Customer Profile queries are read-only so they can run safely in parallel |

---

## UC-004: Predict Arrears Trajectory

**Actor:** System (Arrears Prediction Agent, triggered by Orchestrator)
**Goal:** Analyse the payment pattern from `state.account_profile` and behavioural signals from `state.customer_profile` to forecast arrears trajectory and default probability at 30/60/90 days.
**Priority:** P0 — the arrears signal is the key urgency driver for the NBA Agent.

### Preconditions
- `state.customer_profile` and `state.account_profile` are populated (Stage 1 complete)
- Stage 2 parallel execution started alongside UC-005

### Main Flow

| Step | Action | Detail |
|---|---|---|
| 1 | Agent calls `analyse_payment_pattern(payment_history)` | Identifies: number of consecutive missed payments, average payment % of amount due, payment trend (improving/worsening) |
| 2 | Agent calls `calculate_arrears_trajectory(...)` | Computes trend: `improving / stable / deteriorating / critical` based on DPD direction over last 6 months |
| 3 | Agent calls `predict_default_probability(...)` | Scores probability of reaching write-off threshold (0.0–1.0) using payment pattern + risk segment |
| 4 | Agent calls `estimate_future_arrears(...)` | Projects DPD at +30d, +60d, +90d using trend rate; projects outstanding balance at +30d |
| 5 | Agent calls `identify_risk_factors(...)` | Returns ranked list of contributing factors (e.g., `missed_3_consecutive: 45%`, `balance_growth: 30%`) |
| 6 | Agent returns `ArrearsPrediction` TypedDict | Written to `state.arrears_prediction` by Orchestrator |
| 7 | SSE event emitted | `{"agent": "arrears_prediction", "stage": 2, "status": "complete", "output": {"arrears_trajectory": "...", "default_probability": ...}}` |

### Alternative Flows

| Alt | Condition | Behaviour |
|---|---|---|
| A1 | Payment history < 3 months | `confidence` returned as low (< 0.5); NBA Agent shown low-confidence warning in rationale |
| A2 | `account_status = "improving"` (all recent payments on time) | `arrears_trajectory = "improving"`; NBA Agent routes towards `send_sms` or `no_action_required` |
| A3 | DPD already > 90 | `arrears_trajectory = "critical"`, `default_probability` near 1.0; NBA Agent routes towards `escalate_to_legal` or `flag_for_writeoff` |

### Postconditions
- `state.arrears_prediction` populated with trajectory, default probability, DPD forecasts, and ranked factors
- Results rendered in Screen 3 as three charts: gauge dial, area line chart, horizontal bar chart (see UC-001 Screen 3 results)

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §2.2.4 (Arrears Prediction Agent), §6.1 Stage 2, §10.2 Screen 3 Arrears Card, REQUIREMENTS.md Q8 (resolved — 3 chart types) | Agent definition, pipeline stage, UI chart specification |
| **Deployment** | Render.com FastAPI; Groq Llama 3.3 70B; no additional DB query (uses state from Stage 1) | Most compute-intensive Sonnet agent due to numerical pattern analysis |
| **Observability** | `arrears_trajectory_distribution{trajectory="deteriorating"}` counter; `agent_execution_duration_seconds{agent="arrears_prediction"}` histogram; `stage2.arrears_prediction` Tempo span; `arrears_trajectory` field in structured log | Business metric: trajectory distribution shows portfolio health trend over time. Grafana Dashboard 3 shows this as bar chart |
| **SRE** | Agent error rate SLO ≤ 2%; p95 latency target < 3s for this agent (heaviest Sonnet call); Alert: NBA recommendation rate drops if this agent fails consistently | This agent's output is the primary NBA urgency signal — its failure degrades recommendation quality even if the pipeline completes |

---

## UC-005: Detect Disputes and Collection Hold

**Actor:** System (Dispute Agent, triggered by Orchestrator)
**Goal:** Query the `disputes` table for active disputes on the account, classify hold status, and set `collection_hold` flag that may block all outbound contact in the NBA Agent.
**Priority:** P0 — a hard constraint on the entire collection workflow. A missed hold is a compliance failure.

### Preconditions
- `state.account_profile` is populated (Stage 1 complete)
- Stage 2 parallel execution is running (alongside UC-004)

### Main Flow

| Step | Action | Detail |
|---|---|---|
| 1 | Agent calls `get_active_disputes(account_id)` | Queries `disputes` table WHERE `status IN ('open', 'under_review')` |
| 2 | Agent calls `classify_dispute_type(disputes)` | Categorises each: `billing_error / fraud_claim / identity_theft / service_dispute / payment_dispute` |
| 3 | Agent calls `check_collection_hold_flag(disputes)` | Returns `True` if any active dispute has `collection_hold = 1`; returns hold reason string |
| 4 | Agent calls `get_dispute_history(account_id)` | Queries resolved disputes for context (resolution pattern, prior outcomes) |
| 5 | Agent calls `get_resolution_timeline(dispute_id)` | For active disputes: returns opened_date, days open, escalation status |
| 6 | Agent returns `DisputeSummary` TypedDict | `collection_hold: bool`, `hold_reason: str` written to `state.dispute_summary` |
| 7 | SSE event emitted | `{"agent": "dispute", "stage": 2, "status": "complete", "output": {"collection_hold": ...}}` |

### Alternative Flows

| Alt | Condition | Behaviour |
|---|---|---|
| A1 | `collection_hold = True` | NBA Agent hard-constrained: only `place_on_hold` or `no_action_required` allowed. Warning log emitted: `dispute_hold_triggered` |
| A2 | Multiple active disputes | All listed in `active_disputes` array; single `collection_hold = True` if any has hold flag |
| A3 | Dispute recently resolved (< 7 days ago) | Included in `resolution_history`; NBA Agent notes caution in rationale even if no current hold |

### Postconditions
- `state.dispute_summary` populated; `collection_hold` flag available to NBA Agent
- If hold = True, NBA Agent hard constraint enforced at Stage 3

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §2.2.5 (Dispute Agent), §5.2 (`disputes` table), §6.1 Stage 2, §6.2 Dispute Hold Path | Agent definition, DB schema, dispute hold pipeline path |
| **Deployment** | Render.com FastAPI + SQLite `disputes` table; Groq Llama 3.3 70B | Fastest agent in Stage 2 (simple DB query + classification) |
| **Observability** | `dispute_hold_triggered_total` counter (key business metric); `agent_execution_duration_seconds{agent="dispute"}` histogram; `dispute_hold_triggered` WARNING log event; `stage2.dispute` Tempo span with `dispute.hold` attribute | Alert: if hold rate > 30% of runs over 1h, may indicate data issue (Observability doc §7) |
| **SRE** | Agent error rate SLO ≤ 2%; **Hard reliability requirement**: dispute hold must never be missed — test UC-005 A1 path in every integration test run; Alert: if `dispute` agent fails, NBA must not be allowed to produce outbound contact recommendations | Single most critical compliance control in the pipeline. Failure here is a regulatory risk, not just an SRE metric |

---

## UC-006: Generate Next Best Action Recommendation

**Actor:** System (NBA Agent, triggered by Orchestrator after Stage 2 completes)
**Goal:** Synthesise all four upstream agent outputs into a single, prioritised action recommendation with channel, rationale, confidence score, and ranked alternatives.
**Priority:** P0 — the primary deliverable of the entire system.

### Preconditions
- All four upstream state fields populated: `customer_profile`, `account_profile`, `arrears_prediction`, `dispute_summary`
- Stage 2 complete (both Arrears Prediction and Dispute agents finished)

### Main Flow

| Step | Action | Detail |
|---|---|---|
| 1 | Agent calls `evaluate_action_eligibility(state)` | Applies hard constraints: if `collection_hold = True`, remove all outbound contact actions from catalogue |
| 2 | Agent applies arrears signal routing | `critical` trajectory or `default_probability > 0.85` → boost `escalate_to_legal`, `offer_settlement`; `improving` → boost `no_action_required`, `send_sms` |
| 3 | Agent calls `score_action_options(state, eligible_actions)` | Groq Llama 3.3 70B reasons over full customer + account + arrears + dispute context to score each eligible action (0.0–1.0) |
| 4 | Agent calls `generate_recommendation_rationale(top_action, state)` | Produces a 2–4 sentence human-readable rationale referencing specific state values (DPD, trajectory, contact preference, dispute status) |
| 5 | Agent calls `validate_against_policy(recommendation)` | Final policy check — ensures action is in approved catalogue |
| 6 | Agent returns `NBARecommendation` TypedDict | `action`, `channel`, `rationale`, `confidence_score`, `alternative_actions`, `blocked_by_dispute` written to `state.nba_recommendation` |
| 7 | SSE event emitted | `{"agent": "nba", "stage": 3, "status": "complete", "output": {"action": "...", "confidence_score": ...}}` |

### Alternative Flows

| Alt | Condition | Behaviour |
|---|---|---|
| A1 | Dispute hold active | `blocked_by_dispute = True`; action forced to `place_on_hold`; rationale explains hold reason and dispute reference |
| A2 | `default_probability = 0.91` + `trajectory = critical` | Action = `escalate_to_legal` with confidence > 0.90; no lighter-touch alternatives shown |
| A3 | Account status = `written_off` | Action = `flag_for_writeoff`; rationale explains historical context |
| A4 | `trajectory = improving` + `DPD < 15` | Action = `no_action_required` or `send_sms`; rationale notes positive payment trend |
| A5 | Low arrears confidence (< 0.5) | Rationale includes caveat: "Arrears prediction based on limited payment history — recommend manual review" |

### Postconditions
- `state.nba_recommendation` populated with ranked action, channel, rationale, and alternatives
- NBA card rendered in Screen 3 with Accenture purple border and confidence bar

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §2.2.6 (NBA Agent), §2.2.6 NBA action catalogue (9 actions), §6.1 Stage 3, §6.2 Dispute Hold Path, §6.3 Parallel Execution, §10.2 Screen 3 NBA Card | Agent definition, action catalogue, hard constraints, UI card |
| **Deployment** | Render.com FastAPI; **Groq Llama 3.3 70B** (most powerful model, highest cost — justified by synthesis complexity); prompt caching on policy/constraint system prompt | Opus 4.8 is used only here and in the Orchestrator — highest cost per call |
| **Observability** | `nba_action_recommended_total{action="initiate_call"}` counter (business metric); `agent_execution_duration_seconds{agent="nba"}` histogram (Stage 3 bottleneck); `stage3.nba` Tempo span with `nba.action` and `nba.confidence` attributes; `nba_recommended` INFO log event | Grafana Dashboard 2 shows NBA action distribution pie chart — key business intelligence for demo |
| **SRE** | NBA recommendation rate SLO ≥ 98% of completed workflows; p95 latency for NBA agent ≤ 4s; Alert: NBA agent failure causes pipeline to return `human_review` status; Runbook §8.3 covers "LLM API timeout" | This is the most expensive and slowest agent. If the NBA agent fails repeatedly, error budget is consumed fastest |

---

## UC-007: Review Audit Trail and Decision Lineage

**Actor:** Compliance Officer, Collection Agent
**Goal:** Retrieve and review the complete, step-by-step decision trail for a completed workflow run — to understand why the NBA recommendation was made and to satisfy audit/compliance requirements.
**Priority:** P0 — transparency is a core PoC goal ("how the recommendation was reached").

### Preconditions
- A workflow has been completed (UC-001 executed, `workflow_status = "completed"`)
- `workflow_id` is known (returned in UC-001 step 3)

### Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | Collection Agent | Scrolls to bottom of Results Dashboard (Screen 3) | "▾ Full Audit Trail" expandable section is visible |
| 2 | Agent | Clicks expander | UI calls `GET /collections/{workflow_id}/audit` |
| 3 | System | FastAPI queries `workflow_audit` table for `workflow_id` | Returns structured audit JSON with per-agent steps |
| 4 | System | UI renders Audit Trail (Screen 4) | Per-agent rows displayed: icon, name, elapsed time, input summary, output summary |
| 5 | Compliance Officer | Reviews each agent's input and output | Verifies: correct data was used, dispute hold was checked, arrears risk was considered |
| 6 | Compliance Officer | Inspects NBA rationale text | Confirms the recommendation is consistent with the decision inputs |

### Alternative Flows

| Alt | Condition | Behaviour |
|---|---|---|
| A1 | Workflow failed before NBA | Audit trail shows up to the agent that failed; subsequent agents show "not reached" |
| A2 | Dispute hold was triggered | Audit trail shows NBA agent receiving `collection_hold = True` and routing accordingly |

### Postconditions
- Compliance officer has a complete, immutable decision record
- Audit record persists in `workflow_audit` table (append-only)

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §2.2.7 (Audit Agent), §5.2 (`workflow_audit` table), §10.2 Screen 4, §11 `GET /collections/{id}/audit` | Agent definition, DB table, UI screen, API endpoint |
| **Deployment** | Render.com FastAPI reads `workflow_audit` SQLite table; Streamlit renders expandable `st.expander()` component | No LLM call needed for this use case — pure DB read + UI render |
| **Observability** | Loki query: `{service="collection-assistant-api"} \| json \| workflow_id="wf-abc123"` returns full decision log; Tempo trace shows all 6 agent spans for the workflow; `build_decision_lineage` tool call logged as a span | The audit trail is itself an observability artefact — the log record IS the compliance record |
| **SRE** | Audit completeness: every completed workflow must have a `workflow_audit` record — verified in integration tests; If audit record is missing, treat as P2 incident (data integrity); Runbook §8.3 covers DB integrity | The `workflow_audit` table uses `workflow_id` as primary key — duplicate workflow runs update the same record, protecting against double-logging |

---

## UC-008: Seed Synthetic Customer Database

**Actor:** Data Admin / FDE Demo Presenter
**Goal:** Populate the SQLite database with ~100 realistic synthetic retail customers (including 10 mandatory named demo scenarios) so the pipeline has data to query.
**Priority:** P0 — without seeded data, all collection workflow use cases are blocked.

### Preconditions
- Python environment is configured (`pip install -e ".[dev]"` completed)
- `.env` file has `DATABASE_URL` set
- `data/` directory exists (or is created by the script)

### Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | Data Admin | Runs `python scripts/seed_db.py` (or clicks **Seed Database** in Streamlit sidebar) | Script creates `data/collection_assistant.db` if not present |
| 2 | System | Alembic migration runs | Creates all 6 tables: `customers`, `accounts`, `payment_history`, `disputes`, `interaction_history`, `workflow_audit` |
| 3 | System | Inserts 10 mandatory named scenarios | John Smith, Sarah Jones, Michael Tan, Emily Carter, Robert Davis, Karen Wilson, David Brown, Anna Zhang, James O'Brien, Lisa Park (see REQUIREMENTS.md §5.3) |
| 4 | System | Generates ~90 random customers using Faker (seed=42) | Realistic UK/AU/US names, addresses, income ranges, employment status distribution |
| 5 | System | Generates accounts, payment histories, disputes, interactions | ~150 accounts, ~2,000 payment rows, ~40 disputes, ~300 interactions |
| 6 | System | Prints summary table | Records inserted per table printed to terminal / shown in Streamlit sidebar stats panel |
| 7 | Data Admin | Verifies counts in Streamlit Data Management panel | Panel shows: Customers 102, Accounts 148, Payment rows 1,987, etc. |

### Alternative Flows

| Alt | Condition | Behaviour |
|---|---|---|
| A1 | `--reset` flag passed | All tables dropped and recreated before seeding (used to reset a corrupted or outdated DB) |
| A2 | `--scenarios-only` flag passed | Only the 10 named scenarios inserted (useful for minimal demo setup) |
| A3 | DB already seeded | Script detects existing records and skips (idempotent by default) |

### Postconditions
- SQLite DB is seeded and queryable
- All 10 demo scenarios are accessible by their known `customer_id` / `account_id`
- Streamlit Input Panel dropdowns are populated

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §5.1 (SQLite decision), §5.2 (DB schema — all 6 tables), §5.3 (synthetic data spec, 10 named scenarios), §5.4 (`seed_db.py` CLI), §5.5 (Streamlit Data Management panel) | Data layer specification |
| **Deployment** | SQLite file at `data/collection_assistant.db` on Render.com; `scripts/seed_db.py` run during deploy init; Streamlit sidebar panel for interactive re-seeding | Seeding must run before FastAPI starts accepting requests — wired as a startup hook in `src/collection_assistant/api/main.py` |
| **Observability** | DB table row counts logged at startup (`INFO` level); `seed_completed` INFO log event with counts; Grafana Data Management panel shows live record counts | No ongoing metric for seeding, but startup log verifies the DB is ready |
| **SRE** | Prerequisite for all P0 use cases — if DB is empty, all workflow UCs fail; Health check (`GET /health`) verifies DB connectivity before returning 200; Deploy checklist item: "SQLite DB seeded on fresh deploy" | A fresh Render.com deploy wipes the ephemeral filesystem — seed script must re-run on every cold deploy |

---

## UC-009: Load Quick-Demo Scenario

**Actor:** FDE / Demo Presenter
**Goal:** Load a pre-built scenario with a single button click to immediately demonstrate a specific pipeline path (dispute hold, critical arrears, etc.) without manually typing IDs.
**Priority:** P1 — demo reliability, not core functionality.

### Preconditions
- DB is seeded with 10 named scenarios (UC-008 complete)
- User is on Screen 1 (Input Panel)

### Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | FDE | Clicks one of four quick-load buttons (Standard Case / Dispute Hold / Critical Arrears / Improving Customer) | Customer ID, Account ID, and Trigger fields auto-populate with the scenario's known values |
| 2 | FDE | Reviews pre-filled fields | Tooltip shows expected outcome (e.g., "Dispute Hold: Sarah Jones — NBA result: place_on_hold") |
| 3 | FDE | Clicks **Run Analysis** | Proceeds as UC-001 from step 3 onwards |

### Demo Scenario Mapping

| Button | Customer | Account | DPD | Expected NBA | Key Demonstration |
|---|---|---|---|---|---|
| Standard Case | CUST-001 John Smith | ACC-001 Personal Loan | 45 | `initiate_call` | Full happy path, no holds, deteriorating arrears |
| Dispute Hold | CUST-002 Sarah Jones | ACC-002 Credit Card | 30 | `place_on_hold` | Dispute Agent returning `collection_hold = True`; NBA hard constraint |
| Critical Arrears | CUST-003 Michael Tan | ACC-003 Mortgage | 92 | `escalate_to_legal` | Arrears Prediction returning `trajectory = critical`, `default_probability = 0.91` |
| Improving Customer | CUST-004 Emily Carter | ACC-001 Personal Loan | 12 | `no_action_required` or `send_sms` | NBA choosing light-touch because trajectory = improving |

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §5.3 (10 named scenarios table), §10.2 Screen 1 (quick-load buttons), §10.4 UX Principles ("one-click demo scenarios") | Scenario data, UI button design |
| **Deployment** | Pre-seeded SQLite data on Render; Streamlit session state holds button-selected values | No API call on button click — just pre-fills form fields in `st.session_state` |
| **Observability** | `trigger_context` label in `collection_workflow_total` counter shows scenario mix; Loki shows which scenario was run via `customer_id` label | Demo sessions create a visible spike in workflow_total metrics — useful for showing Grafana to client during demo |
| **SRE** | Demo reliability: if a scenario fails, the demo fails — integration tests (Phase 11) verify all 10 named scenarios end-to-end; No SLO specific to this UC but covered by UC-001's success rate SLO | Render cold-start (30s) is the biggest demo risk — keep-warm UptimeRobot monitor prevents cold starts during demo window |

---

## UC-010: Monitor Pipeline Health and Agent Performance

**Actor:** DevOps / SRE Engineer
**Goal:** Review real-time and historical metrics, logs, and traces to understand pipeline behaviour, detect anomalies, and verify SLOs are being met.
**Priority:** P1 — operational visibility for the PoC.

### Preconditions
- Grafana Cloud account is configured
- OTel exporter in FastAPI is pointing to Grafana Cloud OTLP endpoint
- At least one workflow run has been executed (data exists in Grafana)

### Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | SRE Engineer | Opens Grafana Cloud dashboard "FDE Collection Assistant — Pipeline" | Dashboard shows: total runs (24h), success rate, p50/p95/p99 latency |
| 2 | SRE Engineer | Checks "Agent Deep-Dive" dashboard | Per-agent latency bar chart; token usage by agent (stacked); Stage 2 parallel efficiency |
| 3 | SRE Engineer | Checks "Business Metrics" dashboard | NBA action distribution pie; arrears trajectory distribution bar; default probability histogram |
| 4 | SRE Engineer | Opens Loki Explore tab | Runs query: `{service="collection-assistant-api"} \| json \| level="error"` to check for recent agent failures |
| 5 | SRE Engineer | Opens Tempo search | Finds trace for a slow workflow run by filtering `workflow_duration > 12s` |
| 6 | SRE Engineer | Inspects trace waterfall | Identifies which agent span is the bottleneck; checks NBA span attributes (`nba.action`, `nba.confidence`) |

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §9 NFR §9.4 (Observability), §13 (Deployment Strategy) | Observability NFR, platform choice |
| **Deployment** | Grafana Cloud free tier (10k Prometheus series, 50GB Loki, 50GB Tempo); OpenTelemetry exporter configured in `src/collection_assistant/observability/` | OTel SDK instrumented in FastAPI; Grafana Cloud receives via OTLP |
| **Observability** | Full three-pillar observability: all 9 metrics in `docs/observability_strategy.md §3.1`; all 8 log events in `§4.4`; all span attributes in `§5.2`; all 4 Grafana dashboards in `§6` | Observability doc is the implementation spec for this use case |
| **SRE** | All 5 SLOs from `docs/sre_strategy.md §4`; Error budget tracking via Grafana SLO dashboard; Alert rules from `docs/sre_strategy.md §7.2` fire if thresholds breached | UC-010 is the SRE engineer's primary daily tool — the dashboard IS the SRE artefact demonstrated to the client |

---

## UC-011: Respond to Service Incident

**Actor:** SRE Engineer
**Goal:** Detect, triage, mitigate, and resolve a service incident that degrades or disrupts the collection assistant pipeline.
**Priority:** P1 — demonstrates SRE practices.

### Preconditions
- UptimeRobot monitors are configured (see UC-012 postconditions)
- Grafana alerting is configured with at least one active alert rule
- SRE engineer has access to Render.com dashboard and GitHub Actions

### Main Flow (P1 API Down Incident)

| Step | Actor | Action |
|---|---|---|
| 1 | System | UptimeRobot detects `/health` returning non-200 for 2 consecutive 5-min checks → sends email alert |
| 2 | SRE Engineer | Receives alert email; opens UptimeRobot dashboard to confirm outage start time |
| 3 | SRE Engineer | Opens Render.com dashboard → checks service logs for error messages |
| 4 | SRE Engineer | Opens Grafana Loki → queries `{service="collection-assistant-api"} \| json \| level="critical"` for recent critical errors |
| 5 | SRE Engineer | Identifies root cause (e.g., cold start crash, bad deploy, SQLite lock) |
| 6 | SRE Engineer | Mitigates: redeploys via Render dashboard (previous deploy) or triggers GitHub Actions re-deploy |
| 7 | System | Service recovers; UptimeRobot sends recovery email |
| 8 | SRE Engineer | Verifies recovery: `/health` returns 200; runs one manual workflow via UI |
| 9 | SRE Engineer | Creates GitHub Issue `[INCIDENT] API Down — <date>` with timeline, root cause, error budget impact |
| 10 | SRE Engineer | Calculates error budget consumed: downtime / allowed downtime (7h 12m in 30 days for 99% SLO) |

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §9 NFR §9.1 Performance, §9.2 Reliability, §13 Platform Strategy | NFRs that set reliability targets; deployment platforms used for mitigation |
| **Deployment** | UptimeRobot (detection), Render.com (mitigation — rollback/redeploy), GitHub Actions (re-deploy trigger), Grafana Cloud (diagnosis) | Each platform plays a role in the incident lifecycle |
| **Observability** | Loki `level="critical"` query for root cause; Tempo trace of the last successful vs first failed request; `workflow_completion_status{status="error"}` spike in Prometheus | Observability is the diagnosis tool — without it, incident triage is blind |
| **SRE** | `docs/sre_strategy.md §7` (Alert routing), `§8` (Full incident response steps), `§8.3` (Common failure modes and mitigations), `§4` SLO error budget calculation | SRE doc is the runbook for this use case |

---

## UC-012: Deploy New Version via CI/CD Pipeline

**Actor:** DevOps Engineer
**Goal:** Push a code change to GitHub and have it automatically linted, type-checked, tested, containerised, and deployed to both Render.com (FastAPI) and Streamlit Community Cloud (UI) without manual steps.
**Priority:** P1 — demonstrates DevOps maturity.

### Preconditions
- Code change is committed to a feature branch
- GitHub Actions workflows are configured (`.github/workflows/ci.yml`)
- Render deploy webhooks are set as GitHub Secrets
- All tests were passing on the previous deploy

### Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | DevOps Engineer | Opens PR from `feature/*` into `develop` | GitHub Actions triggers CI pipeline automatically |
| 2 | System | **Job 1: lint-and-typecheck** runs | `ruff check` + `mypy` — fails fast if code quality issues found |
| 3 | System | **Job 2: test** runs (depends on Job 1) | `pytest tests/ --cov=src --cov-fail-under=80` — fails if coverage < 80% or any test fails |
| 4 | DevOps Engineer | Reviews test results in PR; approves PR after 1 reviewer approval | Merges to `develop` |
| 5 | System | **Job 3: build** runs on `develop` push | `docker build → docker push` to GHCR for both API and UI images |
| 6 | System | **Job 4: deploy-staging** runs | `curl` to Render staging webhook → Render pulls new image → staging deploy |
| 7 | DevOps Engineer | Verifies staging deploy; opens PR from `develop` into `main` | Requires all checks green + 1 approval |
| 8 | DevOps Engineer | Merges to `main` | GitHub Actions triggers production pipeline |
| 9 | System | **Job 5: deploy-prod** runs | Render production deploy + Streamlit Community Cloud auto-deploys from `main` push |
| 10 | DevOps Engineer | Runs reliability review checklist (from `docs/sre_strategy.md §9`) | Verifies metrics, traces, health endpoint, error budget |

### Alternative Flows

| Alt | Condition | Behaviour |
|---|---|---|
| A1 | Lint fails on PR | CI fails at Job 1; PR blocked from merge until fixed |
| A2 | Tests fail | CI fails at Job 2; coverage report uploaded as PR artefact for review |
| A3 | Deploy fails on Render | Render automatically rolls back to previous deploy; alert fires |

### Traceability Matrix

| Dimension | Reference | Detail |
|---|---|---|
| **Requirements** | §13 (Deployment Strategy), §13.4 (Phase 13 deliverable) | Platform decision and CI/CD phase |
| **Deployment** | GitHub + GitHub Actions (CI/CD); GHCR (container registry); Render.com (API deploy); Streamlit Community Cloud (UI auto-deploy from main) | Full deploy pipeline documented in `docs/devops_strategy.md §3` with complete YAML |
| **Observability** | Post-deploy: verify metrics appear in Grafana within 2 min; verify `/health` returns 200; check Loki for no ERROR-level logs in first 5 min | Deploy is successful only when observability confirms healthy behaviour, not just HTTP 200 on health |
| **SRE** | Reliability review checklist from `docs/sre_strategy.md §9`; Error budget must be > 25% before deploying (from error budget policy); Branch protection rules enforce test coverage; No force-push to `main` | SRE gates the deploy: low error budget = deploy freeze. This is the operational flywheel connecting DevOps → Observability → SRE |

---

## Traceability Summary Matrix

This table shows which requirements sections, deployment platforms, observability signals, and SRE artefacts each use case depends on.

| Use Case | Requirements §§ | Deployment Platform | Key Observability Signal | SRE Concern |
|---|---|---|---|---|
| UC-001 Run Analysis | §2.1, §2.2.1–7, §10.2, §11 | Render + Streamlit Cloud | `collection_workflow_total`, root trace span | p95 ≤ 15s SLO, success rate ≥ 95% |
| UC-002 Customer Profile | §2.2.2, §5.2 | Render + SQLite + Groq (free) | `agent_execution_duration{customer_profile}` | Agent error rate ≤ 2% |
| UC-003 Account Profile | §2.2.3, §5.2 | Render + SQLite + Groq (free) | `db_query_duration_seconds` | SQLite single-writer constraint |
| UC-004 Arrears Prediction | §2.2.4, §6.1, §10.2 | Render + Groq (free) | `arrears_trajectory_distribution` counter | NBA quality degrades if this fails |
| UC-005 Dispute Detection | §2.2.5, §5.2, §6.2 | Render + SQLite + Groq (free) | `dispute_hold_triggered_total` | Hard compliance constraint — zero tolerance for miss |
| UC-006 NBA Recommendation | §2.2.6, §6.1, §10.2 | Render + Groq free (llama-3.3-70b-versatile) | `nba_action_recommended_total` | NBA rate ≥ 98% |
| UC-007 Audit Trail | §2.2.7, §5.2, §10.2, §11 | Render + SQLite | Loki query by `workflow_id` | Append-only audit record integrity |
| UC-008 Seed Database | §5.1–5.5 | Render (SQLite), Streamlit sidebar | DB startup row count logs | Must re-run on every fresh Render deploy |
| UC-009 Quick Demo | §5.3, §10.2 Screen 1 | Streamlit session state + SQLite | `trigger_context` label in metrics | Render cold-start is demo blocker |
| UC-010 Monitor Health | §9 NFR, §13 | Grafana Cloud (all three pillars) | All 9 metrics + all 4 dashboards | All 5 SLOs tracked here |
| UC-011 Respond to Incident | §9.2 Reliability, §13 | UptimeRobot + Grafana + Render | Loki `level="critical"` + Tempo trace | Full incident runbook (`sre_strategy.md §8`) |
| UC-012 CI/CD Deploy | §13, §13.4 Phase 13 | GitHub Actions + GHCR + Render + Streamlit | Post-deploy Grafana health check | Error budget policy gates production deploy |

---

## Cross-Document Reference Guide

| Document | Sections Referenced by Use Cases |
|---|---|
| `REQUIREMENTS.md` | §2.2.1–2.2.7 (agents), §5.1–5.5 (data layer), §6.1–6.3 (flows), §9 (NFRs), §10.2 (UI screens), §11 (API), §13 (deployment) |
| `docs/devops_strategy.md` | §3 (CI/CD pipeline YAML — UC-012), §5 (Render.com config — UC-001, UC-008), §6 (Environments — UC-009), §7 (Secrets — all UCs) |
| `docs/observability_strategy.md` | §3.1 (metrics table — UC-001 to UC-007), §4.4 (log events — all UCs), §5.2 (span attributes — UC-001 to UC-007), §6 (dashboards — UC-010), §7 (alerts — UC-011), §8 (Plotly charts — UC-004) |
| `docs/sre_strategy.md` | §3 (SLIs — UC-001, UC-006), §4 (SLOs — UC-001, UC-010), §5 (error budgets — UC-012), §6 (UptimeRobot — UC-011), §7 (alert routing — UC-010, UC-011), §8 (incident runbook — UC-011), §9 (deploy checklist — UC-012) |
| `ui/previews/` | `preview_01_input.html` (UC-001, UC-009), `preview_02_execution.html` (UC-001), `preview_03_results.html` (UC-001, UC-004, UC-007) |
