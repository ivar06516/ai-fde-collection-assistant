# AI FDE Collection Assistant — Multi-Agent Architecture Requirements

## 1. Project Overview

### 1.1 Purpose
The AI FDE Collection Assistant is a **Forward Deployed Engineer (FDE) proof of concept** demonstrating how a multi-agent AI system can power intelligent, context-aware debt collection. The entire experience is delivered through a **web UI** — a collection agent opens the dashboard, enters a customer and account ID, watches the five specialized AI agents execute in real time, and receives a clear Next Best Action recommendation with full decision transparency. No CLI, no notebook, no raw API calls — everything from the UI.

### 1.2 Goals
The PoC must demonstrate a working end-to-end multi-agent pipeline covering these five capabilities:

| # | Capability | Agent | What it produces |
|---|---|---|---|
| 1 | **Customer Profile** | Customer Profile Agent | 360° view of the customer — demographics, contact preferences, relationship history, risk segment, behavioural signals |
| 2 | **Account Profile** | Account Profile Agent | Full account snapshot — outstanding balance, days past due, product type, payment history, linked accounts, account status |
| 3 | **Arrears Prediction** | Arrears Prediction Agent | Forward-looking arrears forecast — predicted DPD at 30/60/90 days, default probability, arrears trajectory, contributing risk factors |
| 4 | **Dispute Detection** | Dispute Agent | Active disputes, dispute type & status, resolution history, hold/freeze flags that block collection actions |
| 5 | **Next Best Action** | NBA Agent | Synthesises all four upstream outputs → recommends the optimal next action (call, SMS, payment plan, hold, escalate, write-off) with reasoning |

**Supporting goal:** Provide an audit trail of every agent decision so the client can see how the recommendation was reached.

### 1.3 Scope
This is a **PoC scope** — functional enough to demonstrate the multi-agent pattern end-to-end with stubbed data sources, not production-hardened.

- **Primary interface is the web UI** — all interactions (input, trigger, results, audit) happen through the browser
- Given a customer/account ID entered in the UI, run all five agents in the correct dependency order
- Real-time agent execution progress streamed to the UI so the user sees each agent complete live
- Results rendered as structured, visual cards — not raw JSON
- Data sources (CRM, core banking, dispute management system) are stubbed with realistic mock data
- NBA output and full audit trail surfaced in the UI — no post-hoc log digging required

---

## 2. Multi-Agent Architecture

### 2.1 Architecture Pattern
**UI-Driven Pipeline: Browser → API → LangGraph → 5 Agents → Streamed Results**

```
  ┌──────────────────────────────────────────────────┐
  │                 WEB UI (Streamlit)               │
  │                                                  │
  │  [Input Form]          [Agent Execution Panel]  │
  │  customer_id ────┐     Stage 1 ● Customer ✓     │
  │  account_id  ────┤     Stage 1 ● Account  ✓     │
  │  trigger     ────┤     Stage 2 ● Arrears  ⟳     │
  │  [Run ▶]     ────┘     Stage 2 ● Dispute  ⟳     │
  │                        Stage 3 ● NBA      ○     │
  │                                                  │
  │  [Customer Card] [Account Card] [Arrears Card]  │
  │  [Dispute Card]  [NBA Recommendation ★]         │
  │  [Audit Trail ▾]                                │
  └───────────────────────┬──────────────────────────┘
                          │ HTTP POST + SSE stream
                          ▼
  ┌──────────────────────────────────────────────────┐
  │              FastAPI Backend                     │
  │  POST /collections/recommend  (trigger run)     │
  │  GET  /collections/{id}/stream (SSE progress)   │
  │  GET  /collections/{id}/audit  (full trail)     │
  └───────────────────────┬──────────────────────────┘
                          │ LangGraph
                          ▼
              ┌───────────────────────┐
              │   Orchestrator Agent  │
              └───────────┬───────────┘
                          │
           ── STAGE 1: parallel ──────────────
            ┌─────────────┴──────────────┐
            ▼                            ▼
   ┌─────────────────┐        ┌─────────────────┐
   │ Customer Profile│        │ Account Profile │
   │     Agent       │        │     Agent       │
   └────────┬────────┘        └────────┬────────┘
            └──────────┬───────────────┘
                       │
           ── STAGE 2: parallel ──────────────
                  ┌────┴──────┐
                  ▼           ▼
        ┌──────────────┐  ┌──────────────┐
        │   Arrears    │  │   Dispute    │
        │  Prediction  │  │    Agent     │
        │    Agent     │  │              │
        └──────┬───────┘  └──────┬───────┘
               └────────┬────────┘
                        │
           ── STAGE 3: sequential ────────────
                        ▼
               ┌─────────────────┐
               │   NBA Agent     │  ← Synthesises all 4 outputs
               └────────┬────────┘
                        ▼
               ┌─────────────────┐
               │   Audit Agent   │  ← Builds decision trail
               └────────┬────────┘
                        │ SSE event stream  ↑ back to UI
                        ▼
               workflow_status = "completed"
```

**Communication pattern:**
- UI triggers the run via `POST /collections/recommend` and immediately opens an SSE stream
- Each agent completion emits a server-sent event — the UI updates live (no polling)
- All agents share a single `CollectionWorkflowState` object within the LangGraph run
- **Stage 1 (parallel):** Customer Profile + Account Profile
- **Stage 2 (parallel):** Arrears Prediction + Dispute Agent
- **Stage 3 (sequential):** NBA Agent → Audit Agent

### 2.2 Agent Definitions

#### 2.2.1 Orchestrator Agent
| Property | Detail |
|---|---|
| Role | Manages the pipeline: triggers parallel/sequential agent runs, maintains shared state, handles retries and errors |
| Model | `claude-opus-4-8` |
| Inputs | `customer_id`, `account_id`, trigger context |
| Outputs | Final `CollectionWorkflowState` with all agent outputs populated |
| Tools | `run_agent_parallel`, `run_agent_sequential`, `update_shared_state`, `request_human_review` |
| Termination | When NBA Agent produces a recommendation or workflow reaches an error/human-review state |

#### 2.2.2 Customer Profile Agent
| Property | Detail |
|---|---|
| Role | Build a 360° customer profile covering identity, demographics, contact preferences, relationship history, and behavioural risk signals |
| Model | `claude-sonnet-4-6` |
| Inputs | `customer_id` |
| Outputs | `customer_profile`: name, contact channels, preferred contact time, relationship tenure, prior collection interactions, hardship indicators, risk segment (`low` / `medium` / `high` / `hardship`) |
| Tools | `get_customer_demographics`, `get_contact_preferences`, `get_interaction_history`, `classify_risk_segment`, `detect_hardship_signals` |
| Data sources (stubbed) | CRM, contact history store |

#### 2.2.3 Account Profile Agent
| Property | Detail |
|---|---|
| Role | Retrieve and summarise the full account snapshot — balances, delinquency status, product details, and payment history |
| Model | `claude-sonnet-4-6` |
| Inputs | `account_id` |
| Outputs | `account_profile`: outstanding balance, days past due (DPD), product type, payment history (last 12 months), account status (`current` / `delinquent` / `written-off` / `legal`), linked accounts, last payment date and amount |
| Tools | `get_account_balance`, `get_delinquency_status`, `get_payment_history`, `get_linked_accounts`, `get_product_details` |
| Data sources (stubbed) | Core banking system, loan management system |

#### 2.2.4 Arrears Prediction Agent
| Property | Detail |
|---|---|
| Role | Analyse historical payment behaviour and account signals to forecast the customer's arrears trajectory and default probability over the next 30/60/90 days |
| Model | `claude-sonnet-4-6` |
| Inputs | `account_profile` (payment history, DPD, balance), `customer_profile` (risk segment, hardship indicators) |
| Outputs | `arrears_prediction`: current arrears band, predicted DPD at 30/60/90 days, arrears trajectory, default probability, predicted arrears amount, contributing risk factors, confidence score |
| Tools | `analyse_payment_pattern`, `calculate_arrears_trajectory`, `predict_default_probability`, `estimate_future_arrears`, `identify_risk_factors` |
| Data sources (stubbed) | Payment history from account profile (already in state), behavioural signals from customer profile |
| Arrears trajectory values | `improving` — DPD trending down; `stable` — no change; `deteriorating` — DPD trending up; `critical` — likely to reach write-off threshold |
| Key output for NBA | `default_probability` (0.0–1.0) and `arrears_trajectory` directly influence NBA action urgency and action type |

#### 2.2.5 Dispute Agent
| Property | Detail |
|---|---|
| Role | Identify open disputes, classify dispute type, retrieve resolution history, and flag any collection holds imposed by active disputes |
| Model | `claude-sonnet-4-6` |
| Inputs | `account_id`, `account_profile` (for status cross-check) |
| Outputs | `dispute_summary`: active disputes (type, opened date, status), resolution history, `collection_hold: bool`, hold reason if applicable |
| Tools | `get_active_disputes`, `get_dispute_history`, `classify_dispute_type`, `check_collection_hold_flag`, `get_resolution_timeline` |
| Data sources (stubbed) | Dispute management system, complaints register |
| Key logic | If `collection_hold = true`, NBA Agent must **not** recommend any outbound contact action |

#### 2.2.6 Next Best Action (NBA) Agent
| Property | Detail |
|---|---|
| Role | Synthesise all four upstream outputs and recommend the single best next action, with urgency calibrated by arrears prediction |
| Model | `claude-opus-4-8` (reasoning-intensive synthesis) |
| Inputs | `customer_profile`, `account_profile`, `arrears_prediction`, `dispute_summary` |
| Outputs | `nba_recommendation`: action type, channel, rationale, confidence score, alternative actions ranked |
| Tools | `evaluate_action_eligibility`, `score_action_options`, `generate_recommendation_rationale`, `validate_against_policy` |
| NBA action catalogue | `initiate_call`, `send_sms`, `send_email`, `offer_payment_plan`, `offer_settlement`, `place_on_hold`, `escalate_to_legal`, `flag_for_writeoff`, `no_action_required` |
| Hard constraints | Dispute hold → only `place_on_hold` or `no_action_required` allowed |
| Arrears signal → action guidance | `critical` trajectory + high default probability → prefer `escalate_to_legal` or `offer_settlement`; `improving` → prefer lighter-touch `send_sms` or `no_action_required` |

#### 2.2.7 Audit Agent
| Property | Detail |
|---|---|
| Role | Produce a human-readable, structured audit trail of every agent decision, input, and output within the workflow run |
| Model | `claude-haiku-4-5-20251001` (lightweight, high throughput) |
| Inputs | Complete `CollectionWorkflowState` after all agents complete |
| Outputs | Structured audit record: per-agent summary, decision lineage, timestamp, NBA rationale chain |
| Tools | `log_agent_step`, `build_decision_lineage`, `generate_audit_report` |

---

## 3. Technical Requirements

### 3.1 Language & Runtime
- **Python 3.11+**
- Async-first using `asyncio` for concurrent agent execution
- Type hints throughout (enforced via `mypy`)

### 3.2 Core Dependencies

```
# LLM & Agent Framework
anthropic>=0.40.0              # Claude API SDK (Opus/Sonnet/Haiku)
anthropic[vertex]              # Optional: Vertex AI deployment

# Orchestration & Workflow
langgraph>=0.2.0               # Agent graph orchestration (state machines)
langchain-core>=0.3.0          # Tool abstractions and message types
langchain-anthropic>=0.3.0     # LangChain <-> Anthropic integration

# UI
streamlit>=1.40.0              # Web UI framework (primary demo interface)
httpx>=0.27.0                  # Async HTTP + SSE client for Streamlit → FastAPI
plotly>=5.24.0                 # Arrears trajectory and DPD charts in UI

# API & Service Layer
fastapi>=0.115.0               # REST API for agent invocation + SSE streaming
uvicorn[standard]>=0.32.0      # ASGI server
sse-starlette>=2.1.0           # SSE response type for FastAPI
pydantic>=2.9.0                # Data validation and shared state schemas
pydantic-settings>=2.6.0       # Config management from env vars

# Data & Storage
sqlalchemy>=2.0.0              # ORM for audit logs and state persistence
alembic>=1.14.0                # Database migrations
redis>=5.2.0                   # Shared state cache between agents
psycopg2-binary>=2.9.0         # PostgreSQL driver

# Observability & Tracing
opentelemetry-sdk>=1.28.0      # Distributed tracing
opentelemetry-exporter-otlp>=1.28.0
structlog>=24.4.0              # Structured logging

# Testing
pytest>=8.3.0
pytest-asyncio>=0.24.0
pytest-mock>=3.14.0
httpx>=0.27.0                  # Async HTTP client for tests

# Code Quality
ruff>=0.8.0                    # Linting + formatting
mypy>=1.13.0                   # Static type checking
pre-commit>=4.0.0
```

### 3.3 Claude API Usage

| Agent | Model | Reason |
|---|---|---|
| Orchestrator | `claude-opus-4-8` | Pipeline management, state routing, error handling |
| Customer Profile | `claude-sonnet-4-6` | Profile synthesis and risk classification |
| Account Profile | `claude-sonnet-4-6` | Structured data retrieval and summarisation |
| Arrears Prediction | `claude-sonnet-4-6` | Pattern analysis, trajectory calculation, probabilistic reasoning |
| Dispute | `claude-sonnet-4-6` | Dispute classification and hold-flag logic |
| NBA | `claude-opus-4-8` | Reasoning-intensive synthesis of 4 inputs → single action |
| Audit | `claude-haiku-4-5-20251001` | Lightweight, high-throughput decision logging |

**Prompt caching** must be enabled on all agents that use static system prompts (compliance rules, company policies) to reduce latency and cost.

---

## 4. Project Structure

```
ai-fde-collection-assistant/
│
├── REQUIREMENTS.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── src/
│   └── collection_assistant/
│       ├── __init__.py
│       │
│       ├── agents/                        # One module per agent
│       │   ├── __init__.py
│       │   ├── orchestrator.py            # OrchestratorAgent — pipeline controller
│       │   ├── customer_profile.py        # CustomerProfileAgent
│       │   ├── account_profile.py         # AccountProfileAgent
│       │   ├── arrears_prediction.py      # ArrearsPredictionAgent
│       │   ├── dispute.py                 # DisputeAgent
│       │   ├── nba.py                     # NextBestActionAgent
│       │   └── audit.py                   # AuditAgent
│       │
│       ├── tools/                         # Tool implementations (stubbed for PoC)
│       │   ├── __init__.py
│       │   ├── customer_tools.py          # get_customer_demographics, interaction history
│       │   ├── account_tools.py           # get_account_balance, payment_history, DPD
│       │   ├── arrears_tools.py           # analyse_payment_pattern, predict_default_probability
│       │   ├── dispute_tools.py           # get_active_disputes, check_collection_hold
│       │   ├── nba_tools.py               # score_action_options, validate_against_policy
│       │   └── audit_tools.py             # log_agent_step, build_decision_lineage
│       │
│       ├── graph/                         # LangGraph workflow
│       │   ├── __init__.py
│       │   ├── collection_graph.py        # Main workflow graph (nodes + edges)
│       │   └── state.py                   # CollectionWorkflowState TypedDict
│       │
│       ├── mock_data/                     # Stubbed data sources for PoC
│       │   ├── customers.json
│       │   ├── accounts.json
│       │   └── disputes.json
│       │
│       ├── models/                        # Pydantic schemas
│       │   ├── __init__.py
│       │   ├── customer.py                # CustomerProfile
│       │   ├── account.py                 # AccountProfile
│       │   ├── arrears.py                 # ArrearsPrediction
│       │   ├── dispute.py                 # DisputeSummary
│       │   └── nba.py                     # NBARecommendation
│       │
│       ├── api/                           # FastAPI backend
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── collections.py         # POST /recommend, GET /stream, GET /audit
│       │   │   └── health.py              # GET /health
│       │   └── dependencies.py
│       │
│       ├── config.py
│       └── exceptions.py
│
├── ui/                                    # Streamlit web UI
│   ├── app.py                             # Main Streamlit entry point
│   ├── pages/
│   │   ├── 01_input.py                    # Customer/Account input form
│   │   └── 02_results.py                  # Results dashboard (if multi-page)
│   ├── components/
│   │   ├── execution_panel.py             # Live agent execution timeline
│   │   ├── customer_card.py               # Customer Profile result card
│   │   ├── account_card.py                # Account Profile result card
│   │   ├── arrears_card.py                # Arrears Prediction card + trajectory chart
│   │   ├── dispute_card.py                # Dispute Summary card
│   │   ├── nba_card.py                    # NBA Recommendation highlighted card
│   │   └── audit_panel.py                 # Expandable audit trail
│   ├── sse_client.py                      # SSE stream consumer (httpx async)
│   └── styles.css                         # Custom CSS for card styling
│
├── tests/
│   ├── unit/
│   │   ├── test_customer_profile_agent.py
│   │   ├── test_account_profile_agent.py
│   │   ├── test_arrears_prediction_agent.py
│   │   ├── test_dispute_agent.py
│   │   └── test_nba_agent.py
│   ├── integration/
│   │   └── test_collection_pipeline.py
│   └── conftest.py
│
└── docs/
    ├── agent_contracts.md
    └── nba_action_catalogue.md
```

---

## 5. Shared State Schema

All agents read from and write to a single `CollectionWorkflowState` object managed by LangGraph. Each agent writes only to its own output keys.

```python
from typing import TypedDict, Optional, Literal

class CustomerProfile(TypedDict):
    customer_id: str
    name: str
    contact_channels: list[str]              # ["mobile", "email", "post"]
    preferred_contact_time: str              # "morning" | "afternoon" | "evening"
    relationship_tenure_months: int
    prior_collection_interactions: int
    hardship_indicators: list[str]           # ["unemployment", "medical", "none"]
    risk_segment: str                        # "low" | "medium" | "high" | "hardship"

class AccountProfile(TypedDict):
    account_id: str
    product_type: str                        # "personal_loan" | "credit_card" | "mortgage" | ...
    outstanding_balance: float
    days_past_due: int
    account_status: str                      # "current" | "delinquent" | "legal" | "written_off"
    last_payment_date: Optional[str]
    last_payment_amount: Optional[float]
    payment_history_12m: list[dict]          # [{month, amount_paid, on_time: bool}]
    linked_account_ids: list[str]

class ArrearsPrediction(TypedDict):
    current_arrears_band: str                # "current" | "1-30" | "31-60" | "61-90" | "90+"
    predicted_dpd_30d: int                   # predicted days past due in 30 days
    predicted_dpd_60d: int                   # predicted days past due in 60 days
    predicted_dpd_90d: int                   # predicted days past due in 90 days
    arrears_trajectory: str                  # "improving" | "stable" | "deteriorating" | "critical"
    default_probability: float               # 0.0 – 1.0
    predicted_arrears_amount_30d: float      # projected outstanding balance in 30 days
    contributing_factors: list[str]          # e.g. ["missed_3_consecutive", "income_reduction_signal"]
    confidence: float                        # model confidence 0.0 – 1.0

class DisputeSummary(TypedDict):
    has_active_dispute: bool
    active_disputes: list[dict]              # [{id, type, opened_date, status, description}]
    resolution_history: list[dict]           # [{id, type, resolved_date, outcome}]
    collection_hold: bool                    # TRUE blocks all outbound contact
    hold_reason: Optional[str]

class NBARecommendation(TypedDict):
    action: str                              # action from catalogue (see §2.2.5)
    channel: Optional[str]                  # "mobile" | "email" | "post" | null
    rationale: str                           # human-readable explanation
    confidence_score: float                  # 0.0 – 1.0
    alternative_actions: list[dict]          # [{action, channel, rationale, score}]
    blocked_by_dispute: bool

class CollectionWorkflowState(TypedDict):
    # ── Inputs ──────────────────────────────────────────────
    customer_id: str
    account_id: str
    trigger_context: str                     # "new_delinquency" | "missed_payment" | "review"

    # ── Agent outputs ────────────────────────────────────────
    customer_profile: Optional[CustomerProfile]
    account_profile: Optional[AccountProfile]
    arrears_prediction: Optional[ArrearsPrediction]
    dispute_summary: Optional[DisputeSummary]
    nba_recommendation: Optional[NBARecommendation]

    # ── Workflow control ─────────────────────────────────────
    workflow_status: Literal["in_progress", "completed", "human_review", "error"]
    human_review_required: bool
    error_log: list[str]
    audit_trail: list[dict]                  # per-agent step records
```

---

## 6. Agent Interaction Flow

### 6.1 Standard Flow

```
Step 1 — Stage 1: Parallel data collection
  Orchestrator launches simultaneously:
    ├── Customer Profile Agent  →  populates state.customer_profile
    └── Account Profile Agent   →  populates state.account_profile

Step 2 — Stage 2: Parallel analysis (both depend on Stage 1, not on each other)
  Orchestrator launches simultaneously:
    ├── Arrears Prediction Agent
    │     └── Reads: account_profile.payment_history, customer_profile.risk_segment
    │     └── Populates state.arrears_prediction
    │         (trajectory, default_probability, predicted DPD at 30/60/90d)
    └── Dispute Agent
          └── Reads: account_id, account_profile.account_status
          └── Populates state.dispute_summary
          └── Sets dispute_summary.collection_hold = True/False

Step 3 — Stage 3: NBA synthesis (sequential, all 4 upstream outputs required)
  Orchestrator → NBA Agent
    ├── Reads: customer_profile, account_profile, arrears_prediction, dispute_summary
    ├── [If collection_hold = True] → forces action = "place_on_hold" or "no_action_required"
    ├── [Else if arrears_trajectory = "critical"] → prefers "escalate_to_legal" or "offer_settlement"
    ├── [Else if arrears_trajectory = "improving"] → prefers lighter-touch actions
    ├── [Else] → scores full action catalogue against all profile signals
    └── Populates state.nba_recommendation

Step 4 — Audit logging
  Orchestrator → Audit Agent
    └── Reads full state, writes structured per-agent decision trail

Step 5 — Return
  workflow_status = "completed"
  Return: nba_recommendation + audit_trail
```

### 6.2 Dispute Hold Path

```
Stage 1  (parallel)   Customer Profile + Account Profile agents run
Stage 2  (parallel)   Arrears Prediction runs (predicts trajectory)
                      Dispute Agent finds active dispute → collection_hold = True
Stage 3               NBA Agent sees collection_hold = True
                      → forces action = "place_on_hold" regardless of arrears trajectory
Stage 4               Audit Agent logs hold decision with dispute ID + arrears context
                      workflow_status = "completed", nba.action = "place_on_hold"
```

### 6.3 Parallel Execution Detail
- Stage 1: `asyncio.gather(customer_profile_agent(), account_profile_agent())`
- Stage 2: `asyncio.gather(arrears_prediction_agent(), dispute_agent())`
- Stage 3 onwards: strictly sequential — each depends on all prior state

---

## 7. Tool Interface Contract

All tools must conform to this interface for the Claude tool-use API:

```python
from anthropic.types import ToolParam

def build_tool_schema(name: str, description: str, input_schema: dict) -> ToolParam:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": input_schema,
            "required": list(input_schema.keys()),
        }
    }
```

Each tool implementation must:
- Accept typed Pydantic input models
- Return structured JSON-serializable output
- Raise domain-specific exceptions (never raw exceptions)
- Be independently unit-testable without a live LLM

---

## 8. Configuration

```python
# config.py — via pydantic-settings + .env

class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str
    orchestrator_model: str = "claude-opus-4-8"
    agent_model: str = "claude-sonnet-4-6"
    audit_model: str = "claude-haiku-4-5-20251001"

    # Redis (shared state cache)
    redis_url: str = "redis://localhost:6379/0"

    # PostgreSQL (audit persistence)
    database_url: str = "postgresql+psycopg2://user:pass@localhost/collections"

    # Feature flags
    enable_human_review: bool = True
    max_agent_retries: int = 3
    compliance_strict_mode: bool = True

    # Observability
    otel_endpoint: str = "http://localhost:4317"
    log_level: str = "INFO"
```

---

## 9. Non-Functional Requirements

### 9.1 Performance
- End-to-end workflow completion: < 15 seconds for standard accounts (non-escalation path)
- Concurrent workflow capacity: 50 simultaneous accounts per instance
- Agent LLM call timeout: 30 seconds with 3 retries (exponential backoff)

### 9.2 Reliability
- All agent failures must be caught and logged; workflow must degrade gracefully to human review
- Idempotent tool calls — re-running a workflow on the same account ID must not create duplicate records
- Dead-letter queue for failed workflows; retry within 1 hour

### 9.3 Compliance & Security
- No PII (names, account numbers, SSN) stored in agent prompts or LLM context beyond ephemeral session scope
- All external API calls (CRM, credit bureau) authenticated via OAuth 2.0 / API keys from Vault
- Compliance Agent blocks are hard stops — no mechanism to override programmatically
- Full audit trail persisted to immutable log store (PostgreSQL with append-only constraints)

### 9.4 Observability
- Every agent call traced end-to-end via OpenTelemetry with span attributes: `agent_name`, `account_id`, `model`, `input_tokens`, `output_tokens`, `latency_ms`
- Structured JSON logs with correlation IDs linking all agent calls within one workflow run
- Alerting on: compliance block rate > 5%, agent error rate > 1%, p99 latency > 30s

### 9.5 Testability
- Each agent testable in isolation with mocked tool calls
- Integration tests cover the full graph with stubbed LLM responses (VCR cassettes)
- Compliance Agent has 100% test coverage — every regulatory rule has an explicit test case

---

## 10. UI Requirements

### 10.1 Technology Stack
| Layer | Choice | Reason |
|---|---|---|
| UI Framework | **Streamlit** | Python-native; integrates directly with the agent backend; fast to build; real-time streaming support; professional look with minimal CSS |
| Backend API | **FastAPI** | Async; native SSE support for streaming agent events to the UI |
| Real-time transport | **Server-Sent Events (SSE)** | One-way push from server to browser; simpler than WebSocket for this use case |
| Styling | Streamlit native + `st.markdown` custom CSS | Sufficient for PoC polish |

### 10.2 UI Screens

#### Screen 1 — Input Panel
The starting screen. Clean, minimal form.

```
┌─────────────────────────────────────────────────┐
│  AI Collection Assistant                  [logo] │
├─────────────────────────────────────────────────┤
│                                                  │
│  Customer ID   [ CUST-001          ▾ ]  (or type)│
│  Account ID    [ ACC-001           ▾ ]  (or type)│
│  Trigger       [ New Delinquency   ▾ ]           │
│                                                  │
│              [ ▶  Run Analysis ]                 │
│                                                  │
│  ── Quick load: Sample scenarios ──              │
│  [ Dispute Hold ]  [ Critical Arrears ]          │
│  [ Improving Customer ]  [ Standard Case ]       │
└─────────────────────────────────────────────────┘
```

- Customer ID and Account ID are dropdowns pre-populated from `mock_data/` or free-text
- Trigger context dropdown: `New Delinquency`, `Missed Payment`, `Periodic Review`
- Quick-load buttons populate the form with pre-built mock scenarios for demo purposes

#### Screen 2 — Agent Execution Panel (live, appears on Run click)
Real-time pipeline view. Each stage updates as SSE events arrive.

```
┌─────────────────────────────────────────────────┐
│  Running analysis for CUST-001 / ACC-001         │
├─────────────────────────────────────────────────┤
│  STAGE 1 — Data Collection          [parallel]  │
│  ✅ Customer Profile Agent     1.2s  complete    │
│  ✅ Account Profile Agent      0.9s  complete    │
│                                                  │
│  STAGE 2 — Analysis             [parallel]      │
│  ⟳  Arrears Prediction Agent   running...       │
│  ✅ Dispute Agent               0.7s  complete   │
│                                                  │
│  STAGE 3 — Synthesis           [sequential]     │
│  ○  NBA Agent                  waiting...       │
│  ○  Audit Agent                waiting...       │
│                                                  │
│  ████████████░░░░░░░░  60%   ~4s remaining       │
└─────────────────────────────────────────────────┘
```

- Each agent row shows: status icon (⟳ running / ✅ done / ○ waiting / ❌ error), name, elapsed time, status label
- Progress bar shows overall pipeline completion
- Stage labels make the parallel vs sequential structure visible to the demo audience

#### Screen 3 — Results Dashboard (appears when pipeline completes)
Full results in card layout. All four agent outputs + NBA recommendation visible at once.

```
┌─────────────── CUSTOMER PROFILE ──────────────┐
│  John Smith                    Risk: ● HIGH    │
│  📱 Mobile  ✉ Email            Segment: Avoidant│
│  Best time: Morning            Tenure: 4 years │
│  Prior collections: 2          Hardship: None  │
└───────────────────────────────────────────────┘

┌─────────────── ACCOUNT PROFILE ───────────────┐
│  Personal Loan        Status: ⚠ DELINQUENT     │
│  Balance: $2,850.00   DPD: 45 days             │
│  Last payment: $120 on 2025-04-10              │
│  [Payment history sparkline ▁▂▄▆▃▁▁▁▁▁▁▁]     │
└───────────────────────────────────────────────┘

┌─────────────── ARREARS PREDICTION ────────────┐
│  Trajectory: ↗ DETERIORATING                  │
│  Default probability:  ████████░░  78%        │
│  Predicted DPD:  30d→55  60d→68  90d→82       │
│  Factors: missed_3_consecutive, balance_growth │
└───────────────────────────────────────────────┘

┌─────────────── DISPUTE SUMMARY ───────────────┐
│  Active disputes: 0     Collection hold: ✅ NO │
│  Last resolved: Billing error (2024-11)        │
└───────────────────────────────────────────────┘

┌══════════════ NEXT BEST ACTION ════════════════╗
║  ★ INITIATE CALL                               ║
║  Channel: 📱 Mobile   Confidence: 87%          ║
║                                                ║
║  Rationale:                                    ║
║  "DPD 45 with deteriorating trajectory and     ║
║   78% default probability warrants direct      ║
║   contact. No dispute hold. Customer          ║
║   reachable by mobile, prefers morning."       ║
║                                                ║
║  Alternatives:                                 ║
║  2. Send SMS (71%)   3. Payment Plan (65%)     ╚
└════════════════════════════════════════════════┘

▾ View Full Audit Trail
```

#### Screen 4 — Audit Trail (expandable panel)
Collapsible section below the results. Shows the decision lineage per agent.

```
▾ Full Audit Trail — wf-abc123  (completed in 7.8s)
  ├── ✅ Customer Profile Agent    1.2s
  │       Input:  customer_id=CUST-001
  │       Output: risk_segment=high, contact=mobile+email
  ├── ✅ Account Profile Agent     0.9s
  │       Input:  account_id=ACC-001
  │       Output: DPD=45, status=delinquent, balance=2850
  ├── ✅ Arrears Prediction Agent  2.1s
  │       Input:  payment_history (12m), risk_segment=high
  │       Output: trajectory=deteriorating, probability=0.78
  ├── ✅ Dispute Agent             0.7s
  │       Input:  account_id=ACC-001
  │       Output: active_disputes=0, collection_hold=false
  ├── ✅ NBA Agent                 2.4s
  │       Input:  all 4 profiles
  │       Output: action=initiate_call, confidence=0.87
  └── ✅ Audit Agent              0.5s
          Generated: decision lineage record audit-xyz
```

### 10.3 UX Principles
- **No raw JSON exposed** — all agent outputs rendered as human-readable cards with labels and icons
- **Progressive disclosure** — Input → Execution → Results → Audit Trail (each stage appears in sequence)
- **Real-time feedback** — user sees agents completing live; not a spinner followed by a wall of text
- **Demo-ready scenarios** — one-click quick-load buttons to show the dispute hold path and critical arrears path without typing IDs
- **Colour coding** — risk and status indicators use consistent colour: red = high/critical, amber = medium/deteriorating, green = low/improving
- **Mobile-readable** — cards stack to single column on narrow screens

### 10.4 Streamlit Implementation Notes
- Use `st.status()` for real-time agent execution display
- Use `st.metric()` for DPD, balance, default probability
- Use `st.progress()` for overall pipeline progress
- Use `st.expander()` for the audit trail
- Stream SSE events from FastAPI → parsed by `httpx` in Streamlit's async context → update `st.session_state` → `st.rerun()` to refresh UI
- All agent result cards built with `st.columns()` + `st.container()`

---

## 11. API Contract

All three endpoints are consumed by the Streamlit UI. No endpoint is intended for direct human use.

### POST `/collections/recommend`
Triggers the pipeline. Returns a `workflow_id` immediately; the UI then opens the SSE stream for live progress.

**Request:**
```json
{
  "customer_id": "CUST-001",
  "account_id": "ACC-001",
  "trigger_context": "new_delinquency"
}
```
**Response (202 Accepted):**
```json
{ "workflow_id": "wf-abc123", "status": "in_progress" }
```

---

### GET `/collections/{workflow_id}/stream`
Server-Sent Events stream. UI opens this immediately after receiving `workflow_id`.
Each event has `event: agent_update` with a JSON data payload.

**Event stream example:**
```
event: agent_update
data: {"agent": "customer_profile", "stage": 1, "status": "running", "elapsed_ms": 0}

event: agent_update
data: {"agent": "account_profile", "stage": 1, "status": "running", "elapsed_ms": 10}

event: agent_update
data: {"agent": "customer_profile", "stage": 1, "status": "complete", "elapsed_ms": 1180,
       "output": {"risk_segment": "high", "preferred_contact_time": "morning"}}

event: agent_update
data: {"agent": "account_profile", "stage": 1, "status": "complete", "elapsed_ms": 920,
       "output": {"days_past_due": 45, "account_status": "delinquent", "outstanding_balance": 2850.0}}

event: agent_update
data: {"agent": "arrears_prediction", "stage": 2, "status": "complete", "elapsed_ms": 2100,
       "output": {"arrears_trajectory": "deteriorating", "default_probability": 0.78}}

event: agent_update
data: {"agent": "dispute", "stage": 2, "status": "complete", "elapsed_ms": 680,
       "output": {"collection_hold": false, "has_active_dispute": false}}

event: agent_update
data: {"agent": "nba", "stage": 3, "status": "complete", "elapsed_ms": 2390,
       "output": {"action": "initiate_call", "channel": "mobile", "confidence_score": 0.87}}

event: workflow_complete
data: {"workflow_id": "wf-abc123", "status": "completed", "total_ms": 7840}
```

---

### GET `/collections/{workflow_id}/audit`
Returns the full structured audit trail. Called by the UI when the user expands the Audit Trail panel.

**Response:**
```json
{
  "workflow_id": "wf-abc123",
  "completed_at": "2026-06-03T09:15:32Z",
  "total_execution_ms": 7840,
  "agents": [
    {
      "agent": "customer_profile", "stage": 1, "status": "complete",
      "elapsed_ms": 1180, "input_tokens": 312, "output_tokens": 189,
      "input_summary": {"customer_id": "CUST-001"},
      "output_summary": {"risk_segment": "high", "contact_channels": ["mobile","email"]}
    }
  ],
  "nba_recommendation": {
    "action": "initiate_call", "channel": "mobile",
    "rationale": "DPD 45 with deteriorating trajectory and 78% default probability warrants direct contact. No dispute hold. Customer reachable by mobile, prefers morning.",
    "confidence_score": 0.87,
    "alternative_actions": [
      {"action": "send_sms", "score": 0.71},
      {"action": "offer_payment_plan", "score": 0.65}
    ]
  }
}
```

---

## 11. Development Phases

| Phase | Deliverable | Priority |
|---|---|---|
| Phase | Deliverable | Priority |
|---|---|---|
| Phase 1 | Project scaffold, `pyproject.toml`, config, `CollectionWorkflowState` schema, mock data JSON files | P0 |
| Phase 2 | Customer Profile Agent + Account Profile Agent + stubbed tools | P0 |
| Phase 3 | Arrears Prediction Agent — pattern analysis, trajectory, default probability | P0 |
| Phase 4 | Dispute Agent + collection hold logic | P0 |
| Phase 5 | NBA Agent with action catalogue, arrears-signal routing, and dispute hard constraints | P0 |
| Phase 6 | Orchestrator Agent + LangGraph graph (Stage 1 → Stage 2 → Stage 3 wiring) | P0 |
| Phase 7 | FastAPI backend — `POST /recommend`, `GET /stream` (SSE), `GET /audit` | P0 |
| Phase 8 | Streamlit UI — Input form, live execution panel (SSE consumer), result cards, audit trail | P0 |
| Phase 9 | Demo polish — quick-load scenarios, colour-coded risk badges, trajectory charts | P1 |
| Phase 10 | Integration tests — happy path, dispute hold path, critical arrears path, all via UI | P1 |
| Phase 11 | Observability: OTel tracing per agent call, structured logs | P2 |

---

## 12. Open Questions / Decisions Required

1. **Mock Data Fidelity** — How realistic should the stubbed customer/account/dispute data be? Should it cover edge cases (e.g., multiple active disputes, written-off accounts)?
2. **NBA Action Catalogue** — Is the catalogue in §2.2.6 complete, or are there additional actions specific to the client's workflow?
3. **Risk Segment Definitions** — What criteria define `low / medium / high / hardship` risk segments? Client-provided thresholds or FDE-defined for PoC?
4. **Dispute Hold Scope** — Does a collection hold block all contact channels, or only specific ones (e.g., legal letters still allowed)?
5. **NBA Scoring Logic** — Rules-based scoring in the NBA Agent, or should Claude reason free-form over the profiles with guardrails?
6. ~~**PoC Demo Format**~~ — **Resolved: web UI (Streamlit).** Full pipeline triggered and viewed entirely from the browser. See §10.
7. **UI Branding** — Should the Streamlit UI use client branding (logo, colour palette) or a generic Accenture/FDE theme for the demo?
8. **Arrears Chart Type** — For the predicted DPD trajectory in the UI: bar chart (30/60/90d), line chart, or gauge dial for default probability?
