# UC-013: MCP Tool Discovery and Execution

## Overview

| Field | Value |
|---|---|
| **ID** | UC-013 |
| **Actor** | System (Customer Profile Agent, Account Profile Agent, Dispute Agent — via MCP Client) |
| **Goal** | Agents discover and call tools exposed by MCP servers instead of calling Python functions directly, demonstrating the pluggable integration layer |
| **Priority** | P1 |
| **Delivery Phase** | Phase 16 (Data MCP Server), Phase 17 (Policy + Analytics MCP Servers) |
| **Protocol** | Model Context Protocol (MCP) — open standard (provider-agnostic) |
| **New Dependencies** | `mcp>=1.0.0` |

---

## Context: What Changes from the Baseline

**Before MCP:** Agents call Python functions directly:
```python
# Direct Python call (current)
result = get_customer_demographics(customer_id)
```

**After MCP:** Agents use the `mcp` Python client (`StdioClientSession`) to call tools on MCP servers:
```python
# Via MCP protocol (new)
response = client.beta.messages.create(
    model="llama-3.3-70b-versatile",
    mcp_servers=[{"type": "stdio", "command": "python",
                  "args": ["src/.../data_server.py"]}],
    ...
)
```

The agent code and the tool logic are now decoupled by the MCP protocol. Swapping the data source (SQLite → Salesforce) means replacing only the MCP server, not the agent.

---

## Three MCP Servers

| Server | Name | Tools / Resources | Used By |
|---|---|---|---|
| Data Server | `crm-data` | `get_customer`, `get_account`, `get_payment_history`, `get_active_disputes`, `get_interaction_history` | Customer Profile, Account Profile, Dispute agents |
| Policy Server | `collection-policy` | Resources: `collection_policy.md`, `nba_action_guide.md`, `dispute_resolution_guide.md`, `regulatory_compliance.md` | NBA Agent, Dispute Agent |
| Analytics Server | `collection-analytics` | `check_collection_hold`, `evaluate_action_eligibility`, `get_similar_historical_cases` | NBA Agent, Dispute Agent |

---

## Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | System | Agent process starts; `mcp` client initialises `StdioClientSession` | Client spawns MCP server subprocess (`python data_server.py`) via stdio |
| 2 | System | SDK calls `list_tools` on each MCP server | Server returns tool schemas (name, description, inputSchema) |
| 3 | System | Groq Llama model receives tool list from MCP server as available tools | Model can now call any tool from the server using the standard tool-use protocol |
| 4 | System | Model calls `get_customer(customer_id="CUST-001")` | MCP server receives call → queries SQLite → returns JSON result |
| 5 | System | Model processes result; calls additional tools as needed | Each tool call traced in Audit Trail with server name prefix (`crm-data::get_customer`) |
| 6 | System | Model returns final structured output | MCP servers remain running for reuse; subprocess stays alive for pipeline duration |
| 7 | System | Audit Agent logs MCP server names alongside tool calls | `full_state_json` includes `mcp_server_calls: [{server, tool, latency_ms}]` |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | MCP server subprocess fails to start | Agent falls back to direct Python tool call (graceful degradation); warning logged |
| AF-02 | MCP server returns unknown tool | SDK error; agent retries or uses fallback |
| AF-03 | Policy server resource file missing | Server returns 404-equivalent; NBA Agent uses base system prompt without retrieved context |

---

## Postconditions

- All tool calls in the Audit Trail show MCP server prefix (`server::tool_name`)
- Streamlit sidebar "MCP Servers" panel shows each server with green ✅ status
- Tool call latency tracked separately for MCP overhead vs. DB/LLM time

---

## Acceptance Criteria

### AC-013-01: Data Server Lists All Five Tools
- **Given** `data_server.py` is started
- **When** MCP `list_tools` is called
- **Then** server returns exactly 5 tools: `get_customer`, `get_account`, `get_payment_history`, `get_active_disputes`, `get_interaction_history`
- **Verified by** Phase 16 MCP server unit test calling `list_tools` and asserting tool names

### AC-013-02: `get_customer` Returns Correct Data via MCP
- **Given** `CUST-001` is seeded in the SQLite DB
- **When** `get_customer(customer_id="CUST-001")` is called via MCP protocol
- **Then** tool returns a JSON object with `first_name = "John"`, `last_name = "Smith"`, `risk_segment = "high"`
- **Verified by** Phase 16 MCP server integration test with real DB

### AC-013-03: Tool Calls Appear in Audit Trail With Server Prefix
- **Given** a completed pipeline run using MCP-enabled agents
- **When** `GET /collections/{workflow_id}/audit` is called
- **Then** at least one agent step in the audit contains an `mcp_calls` array where each entry has `server` (e.g., `"crm-data"`) and `tool` (e.g., `"get_customer"`)
- **Verified by** Phase 16 integration test asserting audit trail MCP metadata

### AC-013-04: Policy Server Exposes Four Resources
- **Given** `policy_server.py` is started with `rag/documents/` directory present
- **When** MCP `list_resources` is called
- **Then** server returns 4 resources with URIs: `policy://collection_policy`, `policy://nba_action_guide`, `policy://dispute_resolution_guide`, `policy://regulatory_compliance`
- **Verified by** Phase 17 MCP server unit test

### AC-013-05: Analytics Server `evaluate_action_eligibility` Enforces Hold Constraint
- **Given** `collection_hold = True` is passed to `evaluate_action_eligibility`
- **When** the tool executes
- **Then** returned eligible actions list contains only `["place_on_hold", "no_action_required"]`; all outbound contact actions are excluded
- **Verified by** Phase 17 unit test asserting eligibility filter with hold = True

### AC-013-06: MCP Fallback on Server Failure
- **Given** the Data MCP server process is killed mid-pipeline
- **When** an agent attempts to call a tool
- **Then** the agent falls back to direct Python tool call; warning log event emitted: `mcp_server_unavailable`; pipeline completes normally
- **Verified by** Phase 16 chaos test: kill server subprocess, assert pipeline still completes

### AC-013-07: Streamlit Sidebar Shows MCP Server Status
- **Given** a pipeline run is triggered from the UI
- **When** the Execution Panel is visible
- **Then** the Streamlit sidebar shows "MCP Servers" section with ✅ for each server that responded to `list_tools` and ❌ for any that failed
- **Verified by** Phase 19 UI test

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §14 (MCP & RAG Extensions), `docs/mcp_rag_strategy.md §2` (MCP Architecture) |
| **Deployment** | MCP servers run as Python subprocesses co-located with FastAPI on Render.com; `mcp>=1.0.0` added to `pyproject.toml` |
| **Observability** | `mcp_tool_call_duration_ms` new Prometheus histogram per `{server, tool}`; `mcp_server_name` span attribute on all Tempo tool-call spans; `mcp_calls` array in Audit Trail JSON |
| **SRE** | MCP server failure must degrade gracefully (AC-013-06); fallback ensures pipeline success rate SLO ≥ 95% is maintained even if MCP servers are unavailable; MCP server health visible in Streamlit sidebar |
