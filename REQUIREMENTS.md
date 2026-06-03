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
- Data sources (CRM, core banking, dispute management system) are represented by a SQLite DB seeded with ~100 realistic synthetic retail customers
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
| Data sources | SQLite DB — `customers` + `interaction_history` tables |

#### 2.2.3 Account Profile Agent
| Property | Detail |
|---|---|
| Role | Retrieve and summarise the full account snapshot — balances, delinquency status, product details, and payment history |
| Model | `claude-sonnet-4-6` |
| Inputs | `account_id` |
| Outputs | `account_profile`: outstanding balance, days past due (DPD), product type, payment history (last 12 months), account status (`current` / `delinquent` / `written-off` / `legal`), linked accounts, last payment date and amount |
| Tools | `get_account_balance`, `get_delinquency_status`, `get_payment_history`, `get_linked_accounts`, `get_product_details` |
| Data sources | SQLite DB — `accounts` + `payment_history` tables |

#### 2.2.4 Arrears Prediction Agent
| Property | Detail |
|---|---|
| Role | Analyse historical payment behaviour and account signals to forecast the customer's arrears trajectory and default probability over the next 30/60/90 days |
| Model | `claude-sonnet-4-6` |
| Inputs | `account_profile` (payment history, DPD, balance), `customer_profile` (risk segment, hardship indicators) |
| Outputs | `arrears_prediction`: current arrears band, predicted DPD at 30/60/90 days, arrears trajectory, default probability, predicted arrears amount, contributing risk factors, confidence score |
| Tools | `analyse_payment_pattern`, `calculate_arrears_trajectory`, `predict_default_probability`, `estimate_future_arrears`, `identify_risk_factors` |
| Data sources | Derived from `account_profile` and `customer_profile` already in state — no additional DB query needed |
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
| Data sources | SQLite DB — `disputes` table |
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
# LLM Providers (install the one matching LLM_PROVIDER env var)
anthropic>=0.40.0              # premium / hybrid NBA agent (optional for free_cloud)
langchain-anthropic>=0.3.0     # LangChain <-> Anthropic (premium / hybrid)
langchain-groq>=0.2.0          # free_cloud mode — Groq free tier (recommended default)
langchain-ollama>=0.2.0        # local mode — Ollama local models

# Orchestration & Workflow
langgraph>=0.2.0               # Agent graph orchestration (state machines)
langchain-core>=0.3.0          # Provider-agnostic LLM abstractions

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
sqlalchemy>=2.0.0              # ORM for all DB access (SQLite for PoC)
alembic>=1.14.0                # Database migrations
faker>=24.0.0                  # Synthetic data generation (seed_db.py)
redis>=5.2.0                   # Shared state cache between agents (optional for PoC)

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

### 3.3 LLM Provider Strategy

The system is **provider-agnostic** by design. A single `LLM_PROVIDER` environment variable selects the active provider. The default for the PoC is `free_cloud` (Groq — $0 cost).

Full strategy: [`docs/llm_provider_strategy.md`](docs/llm_provider_strategy.md)

#### Four Modes

| Mode | Provider | Cost | When to Use |
|---|---|---|---|
| `free_cloud` **(PoC default)** | Groq free tier | **$0** | All development, CI tests, internal demos |
| `local` | Ollama (local machine) | **$0** | Offline dev, data-sensitive environments |
| `hybrid` | Groq (agents 1–5) + Anthropic (NBA only) | ~$0.01–0.02/run | Live client demo where NBA quality matters |
| `premium` | Anthropic only | ~$0.05–0.10/run | Production pilot |

#### Per-Agent Model Assignment

| Agent | `free_cloud` (Groq) | `local` (Ollama) | `premium` (Anthropic) | `hybrid` |
|---|---|---|---|---|
| Orchestrator | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-opus-4-8` | `llama-3.3-70b-versatile` |
| Customer Profile | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-sonnet-4-6` | `llama-3.3-70b-versatile` |
| Account Profile | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-sonnet-4-6` | `llama-3.3-70b-versatile` |
| Arrears Prediction | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-sonnet-4-6` | `llama-3.3-70b-versatile` |
| Dispute | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-sonnet-4-6` | `llama-3.3-70b-versatile` |
| NBA | `llama-3.3-70b-versatile` | `llama3.1:8b` | `claude-opus-4-8` | **`claude-opus-4-8`** ← only Anthropic call |
| Audit | `llama-3.1-8b-instant` | `phi4:latest` | `claude-haiku-4-5-20251001` | `llama-3.1-8b-instant` |

#### Implementation: `LLMClientFactory`

```python
# src/collection_assistant/llm/client_factory.py
from collection_assistant.config import Settings, LLMProvider

def get_llm(agent_name: str, settings: Settings):
    model_id = MODEL_MAP[settings.llm_provider][agent_name]
    if settings.llm_provider == LLMProvider.FREE_CLOUD:
        from langchain_groq import ChatGroq
        return ChatGroq(model=model_id, api_key=settings.groq_api_key, temperature=0)
    elif settings.llm_provider == LLMProvider.LOCAL:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_id, base_url=settings.ollama_base_url, temperature=0)
    else:  # premium or hybrid
        if "claude" in model_id:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=model_id, api_key=settings.anthropic_api_key, temperature=0)
        else:
            from langchain_groq import ChatGroq
            return ChatGroq(model=model_id, api_key=settings.groq_api_key, temperature=0)
```

#### Note on MCP With Non-Anthropic Providers
The Anthropic SDK's `mcp_servers=[]` shortcut only works with Anthropic. For Groq/Ollama, the standard `mcp` Python client (`StdioClientSession`) is used directly — fully provider-agnostic. See `docs/mcp_rag_strategy.md §2.3`.

**Prompt caching** applies only in `premium` / `hybrid` modes when Anthropic is the active provider.

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
│       ├── llm/                           # Provider-agnostic LLM abstraction
│       │   ├── __init__.py
│       │   └── client_factory.py          # get_llm(agent_name, settings) → BaseChatModel
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
│       ├── db/                            # Database layer
│       │   ├── __init__.py
│       │   ├── models.py                  # SQLAlchemy ORM models (all 6 tables)
│       │   ├── session.py                 # DB engine + session factory
│       │   └── queries/                   # Query functions called by agent tools
│       │       ├── customer_queries.py
│       │       ├── account_queries.py
│       │       ├── dispute_queries.py
│       │       └── audit_queries.py
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
│   ├── previews/                          # Static HTML design previews (open in browser)
│   │   ├── preview_01_input.html          # Screen 1: Input form
│   │   ├── preview_02_execution.html      # Screen 2: Live agent execution panel
│   │   └── preview_03_results.html        # Screen 3+4: Results dashboard + audit trail
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
├── scripts/
│   ├── seed_db.py                         # Synthetic data generator + DB ingestion
│   └── reset_db.py                        # Drop all tables and re-run seed
│
├── data/
│   └── collection_assistant.db            # SQLite DB file (git-ignored, created by seed_db.py)
│
├── migrations/                            # Alembic migration scripts
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
└── docs/
    ├── agent_contracts.md
    ├── nba_action_catalogue.md
    └── data_schema.md                     # DB table descriptions + field glossary
```

---

## 5. Data Layer

### 5.1 Database
**SQLite** via SQLAlchemy ORM — lightweight, file-based, zero-server, Python-native. Ideal for a PoC that runs locally or on a laptop demo.

| Property | Decision |
|---|---|
| Engine | SQLite 3 (built into Python stdlib) |
| ORM | SQLAlchemy 2.0 (declarative models) |
| File path | `data/collection_assistant.db` (created on first seed) |
| Migrations | Alembic — schema versioned, forward-only for PoC |
| Seeding | `scripts/seed_db.py` — generates and inserts all synthetic data |
| UI trigger | "Data Management" panel in the Streamlit sidebar |

---

### 5.2 Database Schema

```sql
-- Customers master table
CREATE TABLE customers (
    customer_id       TEXT PRIMARY KEY,              -- e.g. CUST-001
    first_name        TEXT NOT NULL,
    last_name         TEXT NOT NULL,
    date_of_birth     DATE NOT NULL,
    age               INTEGER NOT NULL,
    gender            TEXT,                          -- M | F | Other
    email             TEXT,
    mobile_number     TEXT,
    city              TEXT,
    state             TEXT,
    postcode          TEXT,
    employment_status TEXT,                          -- employed | unemployed | self_employed | retired
    annual_income     REAL,
    relationship_since DATE NOT NULL,               -- customer tenure start date
    risk_segment      TEXT NOT NULL,                -- low | medium | high | hardship
    preferred_channel TEXT DEFAULT 'mobile',        -- mobile | email | post
    preferred_time    TEXT DEFAULT 'morning',       -- morning | afternoon | evening
    hardship_flag     INTEGER DEFAULT 0,            -- 0 | 1
    hardship_reason   TEXT,                         -- unemployment | medical | family | none
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounts
CREATE TABLE accounts (
    account_id           TEXT PRIMARY KEY,           -- e.g. ACC-001
    customer_id          TEXT NOT NULL REFERENCES customers(customer_id),
    product_type         TEXT NOT NULL,              -- personal_loan | credit_card | mortgage | auto_loan | overdraft
    account_status       TEXT NOT NULL,              -- current | delinquent | legal | written_off | closed
    outstanding_balance  REAL NOT NULL DEFAULT 0,
    original_balance     REAL NOT NULL,
    credit_limit         REAL,                       -- credit_card / overdraft only
    interest_rate        REAL,
    days_past_due        INTEGER DEFAULT 0,
    delinquency_start    DATE,
    last_payment_date    DATE,
    last_payment_amount  REAL,
    next_due_date        DATE,
    next_due_amount      REAL,
    opened_date          DATE NOT NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Monthly payment history (12+ months per account)
CREATE TABLE payment_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      TEXT NOT NULL REFERENCES accounts(account_id),
    payment_month   TEXT NOT NULL,                   -- YYYY-MM
    amount_due      REAL NOT NULL,
    amount_paid     REAL NOT NULL DEFAULT 0,
    on_time         INTEGER NOT NULL,                -- 1 = on time, 0 = late/missed
    payment_date    DATE,
    UNIQUE(account_id, payment_month)
);

-- Disputes
CREATE TABLE disputes (
    dispute_id       TEXT PRIMARY KEY,               -- e.g. DISP-001
    account_id       TEXT NOT NULL REFERENCES accounts(account_id),
    customer_id      TEXT NOT NULL REFERENCES customers(customer_id),
    dispute_type     TEXT NOT NULL,                  -- billing_error | fraud_claim | identity_theft | service_dispute | payment_dispute
    status           TEXT NOT NULL,                  -- open | under_review | resolved | escalated
    opened_date      DATE NOT NULL,
    resolved_date    DATE,
    description      TEXT,
    collection_hold  INTEGER DEFAULT 1,              -- 1 = blocks collection, 0 = does not
    resolution       TEXT,                           -- upheld | rejected | partial | pending
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Prior collection interaction history
CREATE TABLE interaction_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id      TEXT NOT NULL REFERENCES customers(customer_id),
    account_id       TEXT NOT NULL REFERENCES accounts(account_id),
    interaction_type TEXT NOT NULL,                  -- call | sms | email | letter | field_visit
    interaction_date TIMESTAMP NOT NULL,
    outcome          TEXT,                           -- contacted | no_answer | promise_to_pay | refused | payment_arranged
    agent_notes      TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NBA workflow audit log (written by Audit Agent at end of each run)
CREATE TABLE workflow_audit (
    workflow_id      TEXT PRIMARY KEY,
    customer_id      TEXT NOT NULL,
    account_id       TEXT NOT NULL,
    trigger_context  TEXT NOT NULL,
    nba_action       TEXT,
    nba_channel      TEXT,
    nba_confidence   REAL,
    nba_rationale    TEXT,
    full_state_json  TEXT,                           -- full CollectionWorkflowState as JSON
    status           TEXT NOT NULL,
    total_ms         INTEGER,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 5.3 Synthetic Data Specification

**Volume:** ~100 customers, ~150 accounts, ~2,000 payment history records, ~40 disputes, ~300 interaction records.

**Generator:** `scripts/seed_db.py` uses [Faker](https://faker.readthedocs.io/) to produce realistic UK/AU/US retail names, addresses, and contact details. Every record is deterministic (fixed random seed) so the demo is reproducible.

**Mandatory demo scenarios** (10 named customers, always present after seeding):

| Scenario | Customer | Product | DPD | Status | Trajectory | Disputes | Notes |
|---|---|---|---|---|---|---|---|
| Standard case | John Smith | Personal Loan | 45 | Delinquent | Deteriorating | None | Core demo path |
| Dispute hold | Sarah Jones | Credit Card | 30 | Delinquent | Stable | 1 open (billing) | `collection_hold=True` |
| Critical arrears | Michael Tan | Mortgage | 92 | Delinquent | Critical | None | Default prob > 0.90 |
| Improving customer | Emily Carter | Personal Loan | 12 | Delinquent | Improving | None | Low risk, paying down |
| Hardship | Robert Davis | Personal Loan | 60 | Delinquent | Stable | None | `hardship_flag=True`, medical |
| Written-off | Karen Wilson | Credit Card | 180 | Written Off | Critical | None | NBA → flag_for_writeoff |
| Multiple disputes | David Brown | Auto Loan | 35 | Delinquent | Stable | 2 open | Double hold |
| Legal action | Anna Zhang | Mortgage | 120 | Legal | Critical | None | NBA → escalate_to_legal |
| Settlement candidate | James O'Brien | Personal Loan | 75 | Delinquent | Deteriorating | None | High balance, NBA → offer_settlement |
| No action needed | Lisa Park | Credit Card | 0 | Current | Improving | None | Recently resolved via payment plan |

**Remaining ~90 customers:** randomised across product types, DPD ranges, risk segments, employment statuses, and geographies to give the UI realistic variety in the dropdowns.

**Realistic field ranges:**
- Annual income: £18,000–£120,000 (normal distribution, median £42,000)
- Outstanding balance: £500–£85,000 (varies by product)
- Account tenure: 6 months–15 years
- Payment history: last 18 months per account
- Age: 22–72 years
- Employment: 62% employed, 12% self-employed, 14% retired, 12% unemployed

---

### 5.4 Ingestion Script

**File:** `scripts/seed_db.py`

```python
# Usage
python scripts/seed_db.py               # seed with default 100 customers
python scripts/seed_db.py --reset       # drop all tables, recreate, re-seed
python scripts/seed_db.py --count 200   # seed with 200 customers
python scripts/seed_db.py --scenarios-only  # seed only the 10 named demo scenarios
```

The script:
1. Creates the SQLite DB at `data/collection_assistant.db` if not present
2. Runs Alembic migrations to ensure schema is current
3. Generates synthetic data using `Faker` with `seed(42)` for reproducibility
4. Inserts 10 mandatory named scenarios first, then `--count` random customers
5. Prints a summary table of inserted records by table

---

### 5.5 UI Data Management Panel

Accessible from the **Streamlit sidebar** (not the main page). Collection agents do not need it during normal use — it is for demo setup and reset.

```
┌─── Data Management ──────────────────────────┐
│  Database: data/collection_assistant.db       │
│                                               │
│  Customers     102  ●  Accounts       148    │
│  Payment rows 1,987  ●  Disputes        38   │
│  Interactions   312  ●  Audit runs       7   │
│                                               │
│  [ ▶ Seed Database ]  [ ⚠ Reset & Reseed ]   │
│                                               │
│  ▾ Preview records                            │
│  [ Customers ▾ ]  [ Filter by segment ▾ ]    │
│  ┌─────────┬───────────────┬──────────────┐  │
│  │ ID      │ Name          │ Risk Segment │  │
│  │ CUST-001│ John Smith    │ HIGH         │  │
│  │ CUST-002│ Sarah Jones   │ MEDIUM       │  │
│  └─────────┴───────────────┴──────────────┘  │
└───────────────────────────────────────────────┘
```

- **Seed Database** — runs `seed_db.py` as a subprocess; shows progress spinner; refreshes stats on completion
- **Reset & Reseed** — confirms with a warning dialog before dropping all data
- **Preview records** — read-only table view with column sort and segment filter; useful for picking `customer_id` values to test

---

## 6. Shared State Schema

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
    # LLM Provider (free_cloud | local | hybrid | premium)
    llm_provider: str = "free_cloud"       # DEFAULT: Groq free tier — zero cost

    # Groq (free_cloud / hybrid non-NBA agents)
    groq_api_key: str = ""                 # Free at console.groq.com — no credit card

    # Anthropic (premium / hybrid NBA agent only)
    anthropic_api_key: str = ""            # Leave blank for free_cloud mode

    # Ollama (local mode — no key needed)
    ollama_base_url: str = "http://localhost:11434"

    # SQLite
    database_url: str = "sqlite:///data/collection_assistant.db"

    # Feature flags
    enable_human_review: bool = True
    max_agent_retries: int = 3

    # Observability
    grafana_otlp_endpoint: str = ""
    grafana_otlp_token: str = ""
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
| Styling | Streamlit native + `.streamlit/config.toml` + `st.markdown` custom CSS | Accenture/FDE theme applied globally |
| Theme | **Generic Accenture / FDE theme** — no client branding | Purple (`#A100FF`) primary accent, black nav, white cards |

### 10.2 UI Screens

> **HTML Previews** — Static design previews for all screens are in `ui/previews/`. Open in any browser to review layout and UX before development begins.

#### Screen 1 — Input Panel
**Preview file:** [`ui/previews/preview_01_input.html`](ui/previews/preview_01_input.html)
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
**Preview file:** [`ui/previews/preview_02_execution.html`](ui/previews/preview_02_execution.html)
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

#### Screen 3 — Results Dashboard + Audit Trail (appears when pipeline completes)
**Preview file:** [`ui/previews/preview_03_results.html`](ui/previews/preview_03_results.html)
Full results in card layout. All four agent outputs + NBA recommendation visible at once. Audit trail is an expandable section at the bottom of this same page.

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

┌─────────────── ARREARS PREDICTION ──────────────────────────────────┐
│  Trajectory: ↗ DETERIORATING              Band: 31–60 days          │
│                                                                      │
│  ┌──────────────────────────┐  ┌───────────────────────────────────┐ │
│  │  Default Probability     │  │  DPD Forecast (days)              │ │
│  │                          │  │                              • 82 │ │
│  │        78%               │  │                        • 68       │ │
│  │    [GAUGE DIAL]          │  │              • 55                 │ │
│  │  ╰────────────╯          │  │  • 45  ░░░░░░░░░░░░░░░░░░░░░░░   │ │
│  │    HIGH RISK             │  │  Now  +30d   +60d   +90d         │ │
│  │  (needle → 78%)          │  │  [SVG area line chart]           │ │
│  └──────────────────────────┘  └───────────────────────────────────┘ │
│                                                                      │
│  Contributing Risk Factors     [horizontal bar chart]               │
│  missed_3_consecutive  ████████████████░░░░░  45%                   │
│  balance_growth        ████████████░░░░░░░░░  30%                   │
│  avg_payment_declining █████████░░░░░░░░░░░░  25%                   │
└──────────────────────────────────────────────────────────────────────┘

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

#### Screen 4 — Audit Trail (expandable panel, part of Screen 3)
**Preview file:** [`ui/previews/preview_03_results.html`](ui/previews/preview_03_results.html) — scroll to bottom and expand the audit section.
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

### 10.3 Accenture / FDE Branding Spec

**Resolved (Open Question #7): Generic Accenture/FDE theme — no client branding.**

#### Colour Palette
| Token | Hex | Usage |
|---|---|---|
| `--acn-purple` | `#A100FF` | Primary accent — buttons, active states, highlights, progress fills |
| `--acn-black` | `#000000` | Navigation bar background, primary text headings |
| `--acn-white` | `#FFFFFF` | Card backgrounds, page background |
| `--acn-gray-light` | `#F2F2F2` | Page background, input fields, table zebra rows |
| `--acn-gray-mid` | `#E0E0E0` | Borders, dividers |
| `--acn-gray-text` | `#666666` | Secondary / muted text |
| Risk — High | `#DC2626` | High risk badges, critical status |
| Risk — Medium | `#D97706` | Medium risk, deteriorating trajectory |
| Risk — Low | `#16A34A` | Low risk, improving trajectory, success states |
| Risk — Hardship | `#7C3AED` | Hardship segment badge |

#### Typography
- **Font:** System sans-serif stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`)
- **Headings:** Bold weight, black
- **Body:** Regular weight, `#333333`
- **Labels / caps:** 500 weight, `#666666`, `letter-spacing: 0.06em`

#### Streamlit Theme Config (`.streamlit/config.toml`)
```toml
[theme]
primaryColor        = "#A100FF"
backgroundColor     = "#FFFFFF"
secondaryBackgroundColor = "#F2F2F2"
textColor           = "#000000"
font                = "sans serif"
```

#### Header Identity
```
┌──────────────────────────────────────────────────────┐
│  ▌▌  Accenture  │  FDE Collection Assistant  [FDE PoC]│
└──────────────────────────────────────────────────────┘
```
- Black nav bar with the Accenture wordmark (text only, no image asset required)
- Vertical purple bar (`▌▌`) before "Accenture" to reference the brand mark
- `FDE PoC` badge in purple on black

#### HTML Previews
All three preview files in `ui/previews/` use the Accenture/FDE theme.
See [`ui/previews/preview_01_input.html`](ui/previews/preview_01_input.html), [`preview_02_execution.html`](ui/previews/preview_02_execution.html), [`preview_03_results.html`](ui/previews/preview_03_results.html).

---

### 10.4 UX Principles
- **No raw JSON exposed** — all agent outputs rendered as human-readable cards with labels and icons
- **Progressive disclosure** — Input → Execution → Results → Audit Trail (each stage appears in sequence)
- **Real-time feedback** — user sees agents completing live; not a spinner followed by a wall of text
- **Demo-ready scenarios** — one-click quick-load buttons to show the dispute hold path and critical arrears path without typing IDs
- **Colour coding** — risk and status indicators use consistent colour: red = high/critical, amber = medium/deteriorating, green = low/improving
- **Mobile-readable** — cards stack to single column on narrow screens

### 10.5 Streamlit Implementation Notes
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
| Phase 1 | Project scaffold, `pyproject.toml`, config, `CollectionWorkflowState` schema | P0 |
| Phase 2 | SQLite schema (6 tables), SQLAlchemy models, Alembic migration, `seed_db.py` with 10 named demo scenarios + ~90 random customers | P0 |
| Phase 3 | Customer Profile Agent + Account Profile Agent — querying `customers`, `accounts`, `payment_history`, `interaction_history` tables | P0 |
| Phase 4 | Arrears Prediction Agent — analysis over payment history from state | P0 |
| Phase 5 | Dispute Agent — querying `disputes` table, collection hold logic | P0 |
| Phase 6 | NBA Agent with action catalogue, arrears-signal routing, dispute hard constraints | P0 |
| Phase 7 | Orchestrator Agent + LangGraph graph (Stage 1 → Stage 2 → Stage 3 wiring) | P0 |
| Phase 8 | FastAPI backend — `POST /recommend`, `GET /stream` (SSE), `GET /audit` | P0 |
| Phase 9 | Streamlit UI — Input form (populated from DB), live execution panel, result cards, audit trail, Data Management sidebar panel | P0 |
| Phase 10 | Demo polish — quick-load scenarios, colour-coded badges, Plotly trajectory charts | P1 |
| Phase 11 | Integration tests — all 10 named scenarios verified end-to-end via UI | P1 |
| Phase 12 | Observability: OTel tracing per agent call, structured logs | P2 |

---

## 12. Open Questions / Decisions Required

1. ~~**Mock Data Fidelity**~~ — **Resolved:** Synthetic data generated by script, ingested into SQLite, and surfaced via a Data Management panel in the UI. Coverage: ~100 realistic retail customers, all edge cases included. See §5.
2. **NBA Action Catalogue** — Is the catalogue in §2.2.6 complete, or are there additional actions specific to the client's workflow?
3. **Risk Segment Definitions** — What criteria define `low / medium / high / hardship` risk segments? Client-provided thresholds or FDE-defined for PoC?
4. **Dispute Hold Scope** — Does a collection hold block all contact channels, or only specific ones (e.g., legal letters still allowed)?
5. **NBA Scoring Logic** — Rules-based scoring in the NBA Agent, or should Claude reason free-form over the profiles with guardrails?
6. ~~**PoC Demo Format**~~ — **Resolved: web UI (Streamlit).** Full pipeline triggered and viewed entirely from the browser. See §10.
7. ~~**UI Branding**~~ — **Resolved: Generic Accenture/FDE theme.** Accenture purple (`#A100FF`) primary accent, black nav, white cards. No client branding. `.streamlit/config.toml` defined in §10.3.
8. ~~**Arrears Chart Type**~~ — **Resolved: three charts combined in one card.** Semicircle gauge dial (default probability), SVG area line chart (DPD trajectory Now→+30d→+60d→+90d), and ranked horizontal bar chart (contributing risk factors by weight). See `ui/previews/preview_03_results.html` arrears card and §10.2.

---

## 13. Deployment & Platform Strategy

### 13.1 Decision
**Zero-cost, no credit-card-required stack** chosen to demonstrate DevOps, Observability, and SRE pillars end-to-end on a PoC budget.

| Responsibility | Platform | Free Tier |
|---|---|---|
| Source control + CI/CD | GitHub + GitHub Actions | Unlimited public repos; 2,000 min/month private |
| Streamlit UI hosting | Streamlit Community Cloud | Free for public GitHub repos; no cold-start sleep |
| FastAPI backend hosting | Render.com | 750 hrs/month web service; auto-deploy from GitHub |
| Observability (metrics + logs + traces) | Grafana Cloud | 10k Prometheus series, 50 GB Loki logs, 50 GB Tempo traces, 14-day retention |
| SRE uptime monitoring | UptimeRobot | 50 monitors, 5-min checks, public status page |
| Container registry | GitHub Container Registry (GHCR) | Free for public repos |

### 13.2 End-to-End Platform Architecture

```
Developer → GitHub (push / PR)
                │
                ▼
      GitHub Actions CI/CD
      ┌────────────────────────────────────┐
      │  lint (ruff) → typecheck (mypy)    │
      │  → test (pytest)                   │
      │  → docker build → push GHCR        │
      │  → deploy API  → Render.com        │
      │  → deploy UI   → Streamlit Cloud   │
      └────────────────────────────────────┘
                │                  │
                ▼                  ▼
        Render.com           Streamlit Community Cloud
        FastAPI backend      Streamlit UI
                │                  │
                └────────┬─────────┘
                         │ OpenTelemetry (OTLP)
                         ▼
                Grafana Cloud (free)
                ├── Prometheus  agent metrics, latency, tokens
                ├── Loki        structured JSON logs
                ├── Tempo       distributed traces (per workflow run)
                └── Dashboards + Alerts (email / webhook)
                         │
                         ▼
                UptimeRobot → /health monitor
                Public status page (SRE artefact)
```

### 13.3 Strategy Documents

Full strategy for each pillar is defined in dedicated docs:

| Pillar | Strategy Document |
|---|---|
| DevOps | [`docs/devops_strategy.md`](docs/devops_strategy.md) — CI/CD pipeline, branch strategy, Docker, environments, secrets |
| Observability | [`docs/observability_strategy.md`](docs/observability_strategy.md) — Metrics, Logs, Traces, Grafana dashboards, alerting |
| SRE | [`docs/sre_strategy.md`](docs/sre_strategy.md) — SLOs, SLIs, error budgets, incident runbook, uptime monitoring |

### 13.4 Development Phase Addition

| Phase | Deliverable | Priority |
|---|---|---|
| Phase 13 | Dockerise both services; GitHub Actions pipeline (lint → test → build → deploy) | P1 |
| Phase 14 | Grafana Cloud setup — OTel exporter config, dashboards, alert rules | P1 |
| Phase 15 | UptimeRobot monitors, public status page, SLO tracking dashboard | P2 |

---

## 14. MCP & RAG Extensions

### 14.1 Purpose
Two PoC extensions that showcase advanced agentic patterns on top of the existing pipeline — zero additional infrastructure cost, additive and non-breaking to the baseline.

| Extension | Pattern Demonstrated | Demo Narrative |
|---|---|---|
| **MCP (Model Context Protocol)** | Pluggable tool integration layer | "Swap SQLite for Salesforce CRM by replacing only the MCP server — agents unchanged" |
| **RAG (Retrieval-Augmented Generation)** | Knowledge-grounded AI decisions | "NBA recommendations are grounded in your actual policy documents and informed by real historical outcomes — fully explainable" |

### 14.2 MCP Architecture

Three MCP servers run as stdio subprocesses alongside FastAPI. Agents use the Anthropic SDK MCP client instead of calling Python functions directly.

| Server | Name | Exposes |
|---|---|---|
| Data Server | `crm-data` | 5 tools: `get_customer`, `get_account`, `get_payment_history`, `get_active_disputes`, `get_interaction_history` |
| Policy Server | `collection-policy` | 4 resources: `collection_policy.md`, `nba_action_guide.md`, `dispute_resolution_guide.md`, `regulatory_compliance.md` |
| Analytics Server | `collection-analytics` | 3 tools: `check_collection_hold`, `evaluate_action_eligibility`, `get_similar_historical_cases` |

Full design: [`docs/mcp_rag_strategy.md §2`](docs/mcp_rag_strategy.md)

### 14.3 RAG Architecture

Three RAG pipelines backed by **ChromaDB** (embedded, file-based) with **sentence-transformers/all-MiniLM-L6-v2** embeddings (free, CPU-only).

| Pipeline | Collection | Documents | Used By |
|---|---|---|---|
| Policy RAG | `policy_docs` | 4 policy markdown files, 500-token chunks | NBA Agent — pre-pass before Opus synthesis |
| Historical Case RAG | `historical_cases` | 50 synthetic pre-seeded cases + real `workflow_audit` records (Phase 20) | NBA Agent — empirical precedents |
| Dispute Precedent RAG | `dispute_precedents` | `dispute_resolution_guide.md` | Dispute Agent — classification accuracy |

**NBA Agent enhancement:** RAG pre-pass injects top 3 policy chunks + top 2 similar cases into system prompt. The NBA Recommendation card in the UI gains a "Retrieved Context" expandable panel.

Full design: [`docs/mcp_rag_strategy.md §3`](docs/mcp_rag_strategy.md)

### 14.4 New Dependencies

```
# MCP
mcp>=1.0.0                    # MCP server + client SDK

# RAG
chromadb>=0.5.0               # Embedded vector store (no server, file-based)
sentence-transformers>=3.0.0  # Free CPU embeddings (all-MiniLM-L6-v2, ~90MB)
```

### 14.5 New Project Structure

```
src/collection_assistant/
├── mcp_servers/
│   ├── data_server.py          # CRM + banking + disputes (wraps SQLite)
│   ├── policy_server.py        # Policy docs as MCP resources
│   └── analytics_server.py    # Hold checks, eligibility, similar-case lookup
│
└── rag/
    ├── vectorstore.py          # ChromaDB client factory
    ├── retriever.py            # PolicyRetriever, HistoricalCaseRetriever, DisputeRetriever
    ├── ingester.py             # Chunking + embedding pipeline
    ├── chunker.py              # 500-token markdown-aware splitter
    └── documents/              # Policy source documents
        ├── collection_policy.md
        ├── nba_action_guide.md
        ├── dispute_resolution_guide.md
        └── regulatory_compliance.md

data/
└── chroma/                     # ChromaDB persistent store
    ├── policy_docs/
    ├── historical_cases/
    └── dispute_precedents/

scripts/
└── ingest_rag_documents.py     # Chunk + embed docs; optionally ingest workflow_audit
```

### 14.6 MCP & RAG Use Cases

| Use Case | File | Capability |
|---|---|---|
| UC-013 | [`docs/usecases/usecase-013.md`](docs/usecases/usecase-013.md) | MCP tool discovery, protocol execution, audit trail prefixing |
| UC-014 | [`docs/usecases/usecase-014.md`](docs/usecases/usecase-014.md) | Policy RAG pre-pass for NBA Agent, "Retrieved Context" UI panel |
| UC-015 | [`docs/usecases/usecase-015.md`](docs/usecases/usecase-015.md) | Dispute precedent RAG + historical case retrieval for NBA Agent |

### 14.7 Additional Development Phases

| Phase | Deliverable | Priority |
|---|---|---|
| Phase 16 | MCP Data Server wrapping 5 SQLite tools; Customer Profile + Account Profile agents migrated to MCP client | P1 |
| Phase 17 | MCP Policy Server + Analytics Server; Dispute + NBA agents migrated; MCP server status in Streamlit sidebar | P1 |
| Phase 18 | RAG pipeline — ChromaDB setup, document ingestion, Policy + Historical Case + Dispute Precedent retrievers wired into agents | P1 |
| Phase 19 | UI: "Retrieved Context" panel in NBA card; RAG retrievals in Audit Trail | P2 |
| Phase 20 | Real historical case ingestion from `workflow_audit` after ≥ 20 pipeline runs | P2 |
