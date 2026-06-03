# AI FDE Collection Assistant — Multi-Agent Architecture Requirements

## 1. Project Overview

### 1.1 Purpose
The AI FDE Collection Assistant is a **Forward Deployed Engineer (FDE) proof of concept** demonstrating how a multi-agent AI system can power intelligent, context-aware debt collection. Five specialized agents collaborate — each owning a distinct domain of intelligence — and feed their outputs into a Next Best Action engine that decides the optimal intervention for each customer.

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

- Given a customer/account ID, run all five agents in the correct dependency order and return a structured NBA recommendation
- Data sources (CRM, core banking, dispute management system) are stubbed with realistic mock data
- No live channel dispatch — NBA output is the final artefact
- Human-readable audit trail logged for every agent decision step

---

## 2. Multi-Agent Architecture

### 2.1 Architecture Pattern
**Sequential Pipeline with Two Parallel Stages → NBA Synthesis**

```
  Input: customer_id + account_id
           │
           ▼
  ┌─────────────────────────┐
  │    Orchestrator Agent   │  ← Manages pipeline, shared state, error handling
  └────────────┬────────────┘
               │
    ── STAGE 1: parallel ──────────────────────────────
     ┌─────────┴──────────┐
     │                    │
     ▼                    ▼
┌──────────────┐   ┌──────────────┐
│  Customer    │   │  Account     │
│  Profile     │   │  Profile     │
│  Agent       │   │  Agent       │
└──────┬───────┘   └──────┬───────┘
       │                  │
       └────────┬─────────┘
                │  (both complete)
    ── STAGE 2: parallel ──────────────────────────────
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
┌───────────────┐  ┌─────────────────┐
│  Arrears      │  │  Dispute        │
│  Prediction   │  │  Agent          │
│  Agent        │  │                 │
└───────┬───────┘  └────────┬────────┘
        │                   │
        └──────────┬────────┘
                   │  (both complete)
    ── STAGE 3: sequential ────────────────────────────
                   ▼
          ┌────────────────┐
          │  Next Best     │  ← Synthesises all 4 upstream outputs
          │  Action (NBA)  │
          │  Agent         │
          └───────┬────────┘
                  │
                  ▼
          ┌────────────────┐
          │  Audit Agent   │  ← Logs full decision trail
          └───────┬────────┘
                  │
                  ▼
  Output: NBA recommendation + audit trail
```

**Communication pattern:** All agents share a single `CollectionWorkflowState` object.
- **Stage 1 (parallel):** Customer Profile + Account Profile — no inter-dependency
- **Stage 2 (parallel):** Arrears Prediction + Dispute Agent — both depend only on Stage 1 outputs, not on each other
- **Stage 3 (sequential):** NBA Agent consumes all four upstream outputs; Audit Agent runs last

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

# API & Service Layer
fastapi>=0.115.0               # REST API for agent invocation
uvicorn[standard]>=0.32.0      # ASGI server
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
│       ├── api/                           # FastAPI layer
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── collections.py         # POST /collections/recommend
│       │   │   └── health.py              # GET /health
│       │   └── dependencies.py
│       │
│       ├── config.py
│       └── exceptions.py
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

## 10. API Contract

### POST `/collections/recommend`
Run the full multi-agent pipeline for a customer/account and return the NBA recommendation.

**Request:**
```json
{
  "customer_id": "CUST-001",
  "account_id": "ACC-20250603-001",
  "trigger_context": "new_delinquency"
}
```

**Response:**
```json
{
  "workflow_id": "wf-uuid-here",
  "status": "completed",
  "customer_profile": {
    "risk_segment": "high",
    "preferred_contact_time": "morning",
    "hardship_indicators": ["none"]
  },
  "account_profile": {
    "outstanding_balance": 2850.00,
    "days_past_due": 45,
    "account_status": "delinquent",
    "product_type": "personal_loan"
  },
  "dispute_summary": {
    "has_active_dispute": false,
    "collection_hold": false
  },
  "nba_recommendation": {
    "action": "initiate_call",
    "channel": "mobile",
    "rationale": "Customer is reachable by mobile in the morning, no dispute hold, DPD 45 warrants direct contact before escalation.",
    "confidence_score": 0.87,
    "alternative_actions": [
      {"action": "send_sms", "channel": "mobile", "score": 0.71},
      {"action": "offer_payment_plan", "channel": "email", "score": 0.65}
    ]
  },
  "execution_time_ms": 7840
}
```

### GET `/collections/{workflow_id}/audit`
Retrieve the full per-agent decision audit trail for a workflow run.

---

## 11. Development Phases

| Phase | Deliverable | Priority |
|---|---|---|
| Phase 1 | Project scaffold, `pyproject.toml`, config, `CollectionWorkflowState` schema, mock data JSON files | P0 |
| Phase 2 | Customer Profile Agent + Account Profile Agent + stubbed tools | P0 |
| Phase 3 | Arrears Prediction Agent — pattern analysis, trajectory, default probability | P0 |
| Phase 4 | Dispute Agent + collection hold logic | P0 |
| Phase 5 | NBA Agent with action catalogue, arrears-signal routing, and dispute hard constraints | P0 |
| Phase 6 | Orchestrator Agent + LangGraph graph (Stage 1 parallel → Stage 2 parallel → Stage 3 sequential) | P0 |
| Phase 7 | Audit Agent + full pipeline integration tests (happy path, dispute hold, critical arrears path) | P0 |
| Phase 8 | FastAPI layer (`POST /collections/recommend`, `GET /audit`) | P1 |
| Phase 9 | Observability: OTel tracing per agent call, structured logs | P2 |

---

## 12. Open Questions / Decisions Required

1. **Mock Data Fidelity** — How realistic should the stubbed customer/account/dispute data be? Should it cover edge cases (e.g., multiple active disputes, written-off accounts)?
2. **NBA Action Catalogue** — Is the catalogue in §2.2.5 complete, or are there additional actions specific to the client's workflow?
3. **Risk Segment Definitions** — What criteria define `low / medium / high / hardship` risk segments? Client-provided thresholds or FDE-defined for PoC?
4. **Dispute Hold Scope** — Does a collection hold block all contact channels, or only specific ones (e.g., legal letters still allowed)?
5. **NBA Scoring Logic** — Rules-based scoring in the NBA Agent, or should Claude reason free-form over the profiles with guardrails?
6. **PoC Demo Format** — Is the deliverable a REST API demo, a CLI walkthrough, or a notebook showing the pipeline end-to-end?
