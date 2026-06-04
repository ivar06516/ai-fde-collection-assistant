# Use Case Index — AI FDE Collection Assistant

Each use case is a standalone document structured with: Overview, Preconditions, Main Flow, Alternative Flows, Postconditions, **Acceptance Criteria (Given/When/Then)**, and a Traceability Matrix mapping to Requirements, Deployment, Observability, and SRE.

---

## Use Case Files

| ID | File | Title | Actor | Priority | Phase |
|---|---|---|---|---|---|
| UC-001 | [usecase-001.md](usecase-001.md) | Run Full Collection Analysis | Collection Agent | P0 | 7–9 |
| UC-002 | [usecase-002.md](usecase-002.md) | Build Customer Profile | System | P0 | 3 |
| UC-003 | [usecase-003.md](usecase-003.md) | Build Account Profile | System | P0 | 3 |
| UC-004 | [usecase-004.md](usecase-004.md) | Predict Arrears Trajectory | System | P0 | 4 |
| UC-005 | [usecase-005.md](usecase-005.md) | Detect Disputes and Collection Hold | System | P0 | 5 |
| UC-006 | [usecase-006.md](usecase-006.md) | Generate Next Best Action Recommendation | System | P0 | 6 |
| UC-007 | [usecase-007.md](usecase-007.md) | Review Audit Trail and Decision Lineage | Compliance Officer | P0 | 7–9 |
| UC-008 | [usecase-008.md](usecase-008.md) | Seed Synthetic Customer Database | Data Admin / FDE | P0 | 2 |
| UC-009 | [usecase-009.md](usecase-009.md) | Load Quick-Demo Scenario | FDE / Demo Presenter | P1 | 10 |
| UC-010 | [usecase-010.md](usecase-010.md) | Monitor Pipeline Health and Agent Performance | DevOps / SRE | P1 | 12, 14 |
| UC-011 | [usecase-011.md](usecase-011.md) | Respond to Service Incident | SRE Engineer | P1 | 14–15 |
| UC-012 | [usecase-012.md](usecase-012.md) | Deploy New Version via CI/CD Pipeline | DevOps Engineer | P1 | 13 |
| UC-013 | [usecase-013.md](usecase-013.md) | MCP Tool Discovery and Execution | System | P1 | 16–17 |
| UC-014 | [usecase-014.md](usecase-014.md) | Policy RAG for NBA Recommendation | System | P1 | 18–19 |
| UC-015 | [usecase-015.md](usecase-015.md) | Dispute Precedent RAG and Historical Case Retrieval | System | P1 | 18–20 |

---

## Acceptance Criteria Count

| Use Case | AC Count | Notes |
|---|---|---|
| UC-001 | 7 | Covers full pipeline happy path, SSE ordering, error degradation, audit record |
| UC-002 | 6 | Covers demographics retrieval, risk classification, hardship detection, missing customer |
| UC-003 | 6 | Covers balance/DPD, payment history, account status mapping, DB latency |
| UC-004 | 8 | Covers trajectory, default probability, DPD forecasts, contributing factors, 3 UI charts |
| UC-005 | 7 | Covers hold detection, multiple disputes, resolved disputes, NBA hard constraint |
| UC-006 | 9 | Covers catalogue constraint, dispute hold, critical/improving routing, rationale, confidence |
| UC-007 | 7 | Covers agent listing, I/O summaries, elapsed times, DB persistence, hold visibility |
| UC-008 | 8 | Covers table creation, named scenarios, record counts, idempotency, reset, reproducibility |
| UC-009 | 6 | Covers button → field population, all 4 demo scenario outcomes, no auto-submit |
| UC-010 | 6 | Covers metrics, traces, logs, dashboards, alerting, SLO compliance |
| UC-011 | 7 | Covers alert timing, recovery email, rollback SLA, Loki root cause, GitHub Issue, status page |
| UC-012 | 9 | Covers lint/type/test/coverage gates, GHCR push, staging deploy, prod deploy, rollback, budget policy |
| UC-013 | 7 | MCP server list_tools, tool call via protocol, audit prefix, policy resources, analytics hold, fallback |
| UC-014 | 8 | Policy RAG retrieval, relevance, rationale citation, UI panel, hold not overridden, latency, idempotency |
| UC-015 | 8 | Dispute precedent accuracy, historical case filter, UI visibility, real ingestion, composition |
| **Total** | **101** | |

---

## Traceability — Where Each Dimension Lives

### Requirements → Use Cases
| `REQUIREMENTS.md` Section | Use Cases |
|---|---|
| §2.2.1 Orchestrator Agent | UC-001 |
| §2.2.2 Customer Profile Agent | UC-002 |
| §2.2.3 Account Profile Agent | UC-003 |
| §2.2.4 Arrears Prediction Agent | UC-004 |
| §2.2.5 Dispute Agent | UC-005 |
| §2.2.6 NBA Agent | UC-006 |
| §2.2.7 Audit Agent | UC-007 |
| §5 Data Layer | UC-008 |
| §10.2 UI Screens | UC-001, UC-007, UC-009 |
| §11 API Contract | UC-001, UC-007 |
| §13 Deployment Strategy | UC-010, UC-011, UC-012 |
| §14 MCP & RAG Extensions | UC-013, UC-014, UC-015 |
| `docs/mcp_rag_strategy.md §2` MCP Architecture | UC-013 |
| `docs/mcp_rag_strategy.md §3` RAG Architecture | UC-014, UC-015 |

### Deployment Platforms → Use Cases
| Platform | Use Cases |
|---|---|
| Render.com (FastAPI + SQLite) | UC-001 through UC-008 |
| Streamlit Community Cloud (UI) | UC-001, UC-007, UC-009 |
| Groq API (free) | UC-002, UC-003, UC-004, UC-005, UC-006, UC-007 |
| GitHub Actions | UC-012 |
| Grafana Cloud | UC-010, UC-011 |
| UptimeRobot | UC-010, UC-011 |
| MCP Servers (stdio subprocess, Render.com) | UC-013 |
| ChromaDB at `data/chroma/` (Render.com) | UC-014, UC-015 |
| sentence-transformers (CPU, Render.com) | UC-014, UC-015 |

### Observability Signals → Use Cases
| Signal | Use Cases |
|---|---|
| `collection_workflow_total` counter | UC-001, UC-009 |
| `agent_execution_duration_seconds` histogram | UC-002, UC-003, UC-004, UC-005, UC-006 |
| `arrears_trajectory_distribution` counter | UC-004, UC-010 |
| `dispute_hold_triggered_total` counter | UC-005, UC-010 |
| `nba_action_recommended_total` counter | UC-006, UC-010 |
| Loki `workflow_id` query | UC-007, UC-011 |
| Tempo trace waterfall | UC-001, UC-010, UC-011 |
| `mcp_tool_call_duration_ms` histogram | UC-013 |
| `rag_retrieval_duration_ms` histogram | UC-014, UC-015 |
| `rag_chunks_retrieved` counter | UC-014, UC-015 |

### SRE Concerns → Use Cases
| SRE Concern | Use Cases |
|---|---|
| p95 latency ≤ 15s SLO | UC-001, UC-006 |
| Pipeline success rate ≥ 95% SLO | UC-001 |
| Agent error rate ≤ 2% SLO | UC-002, UC-003, UC-004, UC-005, UC-006 |
| NBA recommendation rate ≥ 98% | UC-006 |
| Dispute hold zero-tolerance | UC-005 |
| Error budget policy | UC-012 |
| Incident runbook | UC-011 |
| Deploy checklist | UC-010, UC-012 |
| MCP graceful degradation | UC-013 |
| RAG graceful degradation | UC-014, UC-015 |
| ChromaDB re-ingest on Render cold deploy | UC-014, UC-015 |

---

## Source Document

The original combined use case document is at [`docs/usecase.md`](../usecase.md).
Individual use case files in this directory are the canonical reference.
