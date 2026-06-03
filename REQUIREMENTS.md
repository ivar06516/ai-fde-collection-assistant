# AI FDE Collection Assistant — Multi-Agent Architecture Requirements

## 1. Project Overview

### 1.1 Purpose
The AI FDE Collection Assistant is a **Forward Deployed Engineer (FDE) proof of concept** demonstrating how a multi-agent AI system can automate and augment the debt collection lifecycle. Built as a PoC to showcase the value of agentic AI to a client, it orchestrates specialized Claude-powered agents to handle customer profiling, communication drafting, payment negotiation, compliance checks, and escalation decisions — reducing manual effort and improving collection outcomes.

### 1.2 Goals
- Demonstrate agentic AI value to the client through a working PoC of the collection workflow
- Automate routine collection workflows end-to-end using collaborative AI agents
- Ensure every action is compliant with applicable regulations (FDCPA, TCPA, GDPR, local laws)
- Personalize outreach and payment plans based on debtor profiles and behavioral signals
- Provide real-time analytics and prioritization across the collection portfolio
- Support human-in-the-loop review for high-stakes decisions

### 1.3 Scope
This is a **PoC scope** — functional enough to demonstrate the multi-agent pattern end-to-end, not production-hardened. External integrations (CRM, credit bureau) are stubbed.

- Inbound: process new delinquent accounts entering the collection queue
- Outbound: initiate and track multi-channel collection communications
- Decision support: recommend escalation paths, settlement offers, and legal actions
- Reporting: generate agent activity logs, KPIs, and compliance audit trails

---

## 2. Multi-Agent Architecture

### 2.1 Architecture Pattern
**Hierarchical Orchestration with Specialized Agents**

```
                        ┌─────────────────────────┐
                        │   Orchestrator Agent     │
                        │  (Supervisor / Router)   │
                        └────────────┬────────────┘
                                     │
          ┌──────────┬───────────────┼───────────────┬──────────────┐
          │          │               │               │              │
   ┌──────▼──┐ ┌─────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐ ┌────▼───────┐
   │Profiling│ │Communication│ │  Payment   │ │ Compliance │ │Escalation  │
   │ Agent   │ │   Agent     │ │  Plan Agent│ │   Agent    │ │  Agent     │
   └──────┬──┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └────┬───────┘
          │          │               │               │              │
          └──────────┴───────────────┼───────────────┴──────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │   Analytics & Audit      │
                        │        Agent             │
                        └─────────────────────────┘
```

**Communication pattern:** Agent-to-agent via shared state (context object) passed through the orchestrator. No direct peer-to-peer calls — all routing goes through the Orchestrator Agent.

### 2.2 Agent Definitions

#### 2.2.1 Orchestrator Agent
| Property | Detail |
|---|---|
| Role | Supervisor that receives incoming tasks, routes to sub-agents, aggregates results, and decides next steps |
| Model | `claude-opus-4-8` (highest reasoning for routing decisions) |
| Inputs | Account ID, trigger event (new delinquency, payment missed, inbound call, etc.), shared state |
| Outputs | Completed workflow result + updated shared state |
| Tools | `route_to_agent`, `merge_agent_outputs`, `update_shared_state`, `request_human_review` |
| Termination | When the workflow reaches a terminal state (resolved, escalated, requires human) |

#### 2.2.2 Customer Profiling Agent
| Property | Detail |
|---|---|
| Role | Build and enrich a 360° debtor profile from CRM, credit bureau, payment history, and behavioral data |
| Model | `claude-sonnet-4-6` |
| Inputs | Account ID, data sources list |
| Outputs | Debtor profile JSON: risk score, segment, contact preferences, hardship flags, prior interactions |
| Tools | `query_crm`, `fetch_credit_data`, `get_payment_history`, `classify_risk_segment`, `detect_hardship_indicators` |

#### 2.2.3 Communication Agent
| Property | Detail |
|---|---|
| Role | Draft personalized, regulation-compliant collection notices, emails, SMS, and call scripts |
| Model | `claude-sonnet-4-6` |
| Inputs | Debtor profile, communication channel, campaign type, compliance rules |
| Outputs | Drafted message(s) ready for dispatch, with compliance metadata |
| Tools | `draft_message`, `select_channel`, `apply_compliance_template`, `localize_message`, `schedule_dispatch` |

#### 2.2.4 Payment Plan Agent
| Property | Detail |
|---|---|
| Role | Evaluate debtor capacity and propose optimized repayment plans or settlement offers |
| Model | `claude-sonnet-4-6` |
| Inputs | Outstanding balance, debtor profile, company policy rules, hardship indicators |
| Outputs | Ranked list of payment plan options with projected recovery rates |
| Tools | `calculate_affordability`, `generate_plan_options`, `simulate_recovery`, `validate_against_policy`, `generate_offer_letter` |

#### 2.2.5 Compliance Agent
| Property | Detail |
|---|---|
| Role | Validate every proposed action against regulatory requirements before execution |
| Model | `claude-sonnet-4-6` |
| Inputs | Proposed action, jurisdiction, account flags (do-not-contact, bankruptcy, minor, etc.) |
| Outputs | Compliance verdict (approved / blocked / conditional), required disclosures, risk flags |
| Tools | `check_fdcpa_rules`, `check_tcpa_rules`, `check_gdpr_consent`, `validate_disclosure`, `log_compliance_event` |

#### 2.2.6 Escalation Agent
| Property | Detail |
|---|---|
| Role | Determine when and how to escalate accounts — to field agents, legal teams, or external collectors |
| Model | `claude-sonnet-4-6` |
| Inputs | Debtor profile, communication history, payment history, risk score, days past due |
| Outputs | Escalation recommendation with rationale, priority tier, recommended next action |
| Tools | `evaluate_escalation_triggers`, `assign_priority_tier`, `route_to_legal`, `route_to_field_agent`, `flag_for_writeoff` |

#### 2.2.7 Analytics & Audit Agent
| Property | Detail |
|---|---|
| Role | Log all agent actions, generate KPI summaries, detect anomalies, produce compliance audit trails |
| Model | `claude-haiku-4-5-20251001` (lightweight, high throughput for logging) |
| Inputs | Agent execution logs, outcomes, timestamps |
| Outputs | Structured audit records, KPI dashboards data, anomaly alerts |
| Tools | `log_agent_action`, `compute_kpis`, `detect_anomaly`, `generate_audit_report`, `push_to_dashboard` |

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
| Orchestrator | `claude-opus-4-8` | Complex multi-step reasoning, routing logic |
| Profiling | `claude-sonnet-4-6` | Data synthesis and classification |
| Communication | `claude-sonnet-4-6` | Language quality for customer-facing content |
| Payment Plan | `claude-sonnet-4-6` | Numerical reasoning + policy adherence |
| Compliance | `claude-sonnet-4-6` | Rule interpretation accuracy |
| Escalation | `claude-sonnet-4-6` | Risk-based decision making |
| Analytics | `claude-haiku-4-5-20251001` | High-throughput, low-cost logging |

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
│       │   ├── orchestrator.py            # OrchestratorAgent
│       │   ├── profiling.py               # CustomerProfilingAgent
│       │   ├── communication.py           # CommunicationAgent
│       │   ├── payment_plan.py            # PaymentPlanAgent
│       │   ├── compliance.py              # ComplianceAgent
│       │   ├── escalation.py              # EscalationAgent
│       │   └── analytics.py              # AnalyticsAuditAgent
│       │
│       ├── tools/                         # Tool implementations called by agents
│       │   ├── __init__.py
│       │   ├── crm_tools.py               # CRM query / update tools
│       │   ├── payment_tools.py           # Affordability calc, plan generation
│       │   ├── compliance_tools.py        # FDCPA/TCPA rule checks
│       │   ├── communication_tools.py     # Channel dispatch, templating
│       │   ├── escalation_tools.py        # Routing, priority tiers
│       │   └── analytics_tools.py         # Logging, KPI, audit
│       │
│       ├── graph/                         # LangGraph workflow definitions
│       │   ├── __init__.py
│       │   ├── collection_graph.py        # Main workflow graph
│       │   └── state.py                   # Shared state schema (TypedDict)
│       │
│       ├── models/                        # Pydantic data models
│       │   ├── __init__.py
│       │   ├── account.py                 # Account, DebtorProfile
│       │   ├── workflow.py                # WorkflowResult, AgentOutput
│       │   └── compliance.py              # ComplianceVerdict
│       │
│       ├── api/                           # FastAPI layer
│       │   ├── __init__.py
│       │   ├── main.py                    # App factory
│       │   ├── routes/
│       │   │   ├── collections.py         # POST /collections/process
│       │   │   └── health.py              # GET /health
│       │   └── dependencies.py            # DI for agent instances
│       │
│       ├── config.py                      # Settings via pydantic-settings
│       └── exceptions.py                  # Domain exceptions
│
├── tests/
│   ├── unit/
│   │   ├── agents/
│   │   ├── tools/
│   │   └── models/
│   ├── integration/
│   │   └── test_collection_workflow.py
│   └── conftest.py
│
└── docs/
    ├── agent_contracts.md
    ├── tool_reference.md
    └── compliance_rules.md
```

---

## 5. Shared State Schema

All agents read from and write to a single `CollectionWorkflowState` object managed by LangGraph:

```python
from typing import TypedDict, Optional, Literal
from pydantic import BaseModel

class CollectionWorkflowState(TypedDict):
    # Input
    account_id: str
    trigger_event: str                       # new_delinquency | missed_payment | inbound_call
    jurisdiction: str                        # e.g. "US-CA", "UK", "AU-NSW"

    # Profiling Agent output
    debtor_profile: Optional[dict]
    risk_score: Optional[float]              # 0.0 (low risk) to 1.0 (high risk)
    segment: Optional[str]                   # hardship | willing | avoidant | unreachable

    # Compliance Agent output
    compliance_verdict: Optional[str]        # approved | blocked | conditional
    required_disclosures: Optional[list]
    blocked_channels: Optional[list]

    # Communication Agent output
    drafted_messages: Optional[list]
    scheduled_dispatch: Optional[dict]

    # Payment Plan Agent output
    payment_plan_options: Optional[list]
    recommended_plan: Optional[dict]

    # Escalation Agent output
    escalation_required: Optional[bool]
    escalation_tier: Optional[str]           # field_agent | legal | writeoff
    escalation_rationale: Optional[str]

    # Workflow control
    workflow_status: Literal["in_progress", "resolved", "escalated", "human_review", "blocked"]
    human_review_required: bool
    error_log: list
    audit_trail: list
```

---

## 6. Agent Interaction Flow

### 6.1 Happy Path — New Delinquency

```
1. Trigger: New account enters the collection queue
2. Orchestrator receives account_id + trigger_event
3. Orchestrator → Profiling Agent
   - Builds debtor_profile, risk_score, segment
4. Orchestrator → Compliance Agent
   - Checks jurisdiction rules, contact restrictions
   - Returns: approved channels, required disclosures
5. [If compliance = blocked] → workflow_status = "blocked", exit
6. Orchestrator → Communication Agent
   - Drafts personalized message for approved channels
7. Orchestrator → Payment Plan Agent (parallel with Communication if possible)
   - Generates plan options based on debtor profile
8. Orchestrator → Escalation Agent
   - Evaluates whether to escalate immediately (DPD > threshold, prior legal flag, etc.)
9. [If escalation_required] → route to appropriate team, exit
10. Orchestrator → Analytics Agent
    - Logs full audit trail, computes KPIs
11. Workflow complete: status = "resolved" or "in_progress"
```

### 6.2 Parallel Execution
Steps 7 and 8 (Payment Plan + Escalation assessment) run concurrently using `asyncio.gather()` to minimize latency.

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

### POST `/collections/process`
Trigger a new collection workflow for an account.

**Request:**
```json
{
  "account_id": "ACC-20250603-001",
  "trigger_event": "new_delinquency",
  "jurisdiction": "US-CA",
  "metadata": {
    "days_past_due": 45,
    "outstanding_balance": 2850.00,
    "currency": "USD"
  }
}
```

**Response:**
```json
{
  "workflow_id": "wf-uuid-here",
  "account_id": "ACC-20250603-001",
  "status": "resolved",
  "risk_score": 0.72,
  "segment": "avoidant",
  "compliance_verdict": "approved",
  "recommended_action": "send_payment_plan_offer",
  "escalation_required": false,
  "audit_trail_id": "audit-uuid-here",
  "execution_time_ms": 8420
}
```

### GET `/collections/{workflow_id}/audit`
Retrieve the full audit trail for a workflow run.

---

## 11. Development Phases

| Phase | Deliverable | Priority |
|---|---|---|
| Phase 1 | Project scaffold, config, shared state schema, base agent class | P0 |
| Phase 2 | Profiling Agent + Compliance Agent + tool stubs | P0 |
| Phase 3 | Orchestrator Agent + LangGraph workflow graph | P0 |
| Phase 4 | Communication Agent + Payment Plan Agent | P1 |
| Phase 5 | Escalation Agent + Analytics/Audit Agent | P1 |
| Phase 6 | FastAPI layer + full integration tests | P1 |
| Phase 7 | Observability (OTel tracing, dashboards) | P2 |
| Phase 8 | Human-in-the-loop review UI | P2 |

---

## 12. Open Questions / Decisions Required

1. **LLM Provider Redundancy** — Should we support a fallback provider (e.g., Vertex AI Claude) for availability SLA?
2. **State Persistence Strategy** — Redis ephemeral state during a workflow run vs. full PostgreSQL persistence from the start?
3. **Compliance Rule Source** — Static Python rule engine vs. dynamic rules fetched from a policy service?
4. **Human Review Interface** — CLI-based approval queue for Phase 1, or a minimal web UI from the start?
5. **CRM Integration** — Which CRM system (Salesforce, SAP, custom) drives the tool implementation in Phase 2?
6. **Data Residency** — PII tokenization strategy for accounts where GDPR applies?
