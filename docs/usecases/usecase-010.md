# UC-010: Monitor Pipeline Health and Agent Performance

## Overview

| Field | Value |
|---|---|
| **ID** | UC-010 |
| **Actor** | DevOps / SRE Engineer |
| **Goal** | Review real-time and historical metrics, logs, and traces to understand pipeline behaviour, detect anomalies, and verify SLOs are being met |
| **Priority** | P1 — operational visibility for the PoC |
| **Delivery Phase** | Phase 12 (OTel instrumentation), Phase 14 (Grafana Cloud setup) |
| **Platforms** | Grafana Cloud (free tier) — Prometheus, Loki, Tempo |

---

## Preconditions

- Grafana Cloud account created; OTLP endpoint + token saved to GitHub Secrets and Render env vars
- OpenTelemetry exporter configured in FastAPI (`src/collection_assistant/observability/`)
- At least one workflow run has been executed (data exists in Grafana)

---

## Main Flow — Dashboard Review

| Step | Actor | Action | What to Look For |
|---|---|---|---|
| 1 | SRE Engineer | Opens Grafana "FDE Collection Assistant — Pipeline" dashboard | Total runs (24h), success rate gauge, p95 latency stat |
| 2 | SRE Engineer | Checks "Agent Deep-Dive" dashboard | Per-agent latency bar; token usage stacked bar; Stage 2 parallel efficiency |
| 3 | SRE Engineer | Checks "Business Metrics" dashboard | NBA action distribution pie; arrears trajectory bar; default probability histogram |
| 4 | SRE Engineer | Opens Loki Explore | Query: `{service="collection-assistant-api"} \| json \| level="error"` — checks for recent failures |
| 5 | SRE Engineer | Opens Tempo search | Filter: `workflow_duration > 12000ms` — finds slow outlier traces |
| 6 | SRE Engineer | Inspects trace waterfall | Identifies which agent span is the bottleneck; checks attribute values |

---

## Key Grafana Dashboards

| Dashboard | Purpose | Key Panels |
|---|---|---|
| Pipeline Overview | Overall health | Total runs, success rate, p50/p95/p99 latency, error rate |
| Agent Deep-Dive | Per-agent performance | Latency heatmap, token usage by agent and model, error rate per agent |
| Business Metrics | Collection outcomes | NBA action distribution, arrears trajectory split, default probability histogram |
| Infrastructure | System health | API response time, DB query latency, concurrent workflows |

---

## Acceptance Criteria

### AC-010-01: Metrics Appear in Grafana Within 2 Minutes of Workflow Run
- **Given** a workflow run completes
- **When** 2 minutes have elapsed
- **Then** `collection_workflow_total` counter shows an incremented value in Grafana; `collection_workflow_duration_seconds` histogram contains the run's duration
- **Verified by** Phase 14 observability test: run a workflow, wait 2 min, query Prometheus

### AC-010-02: Trace Appears in Tempo With Correct Agent Spans
- **Given** a completed workflow run with known `workflow_id`
- **When** Tempo is searched by `workflow.id = "wf-abc123"`
- **Then** the trace contains 6 child spans (one per agent) with correct `agent.name` attributes; Stage 1 spans show overlapping timestamps (parallel); Stage 2 spans show overlapping timestamps; Stage 3 spans are sequential
- **Verified by** Phase 14 observability test: run a workflow, search Tempo, assert span count and ordering

### AC-010-03: Logs Appear in Loki With Correct `workflow_id`
- **Given** a completed workflow run
- **When** Loki is queried: `{service="collection-assistant-api"} | json | workflow_id="wf-abc123"`
- **Then** log lines appear for all 6 agent events: `agent_started` (×6) and `agent_complete` (×6); `workflow_started` and `workflow_complete` log lines are present
- **Verified by** Phase 14 observability test: run a workflow, query Loki, assert log line count ≥ 14

### AC-010-04: All Four Dashboards Render Without Errors
- **Given** Grafana Cloud is configured and at least 1 workflow run has been executed
- **When** all 4 dashboards are opened
- **Then** no panels show "No data" or error states; all metric queries return results
- **Verified by** Phase 14 manual verification; documented in deploy checklist (`sre_strategy.md §9`)

### AC-010-05: Alert Fires When Error Rate Exceeds Threshold
- **Given** Grafana alert rule: `agent_error_rate > 5% over 5 min`
- **When** a test failure is artificially triggered (mock LLM error in staging)
- **Then** an alert email is received within 10 minutes of the threshold being crossed; alert resolves automatically when error rate drops below threshold
- **Verified by** Phase 14 alert test in staging environment

### AC-010-06: SLO Compliance Visible on Dashboard
- **Given** the Grafana SLO dashboard is configured
- **When** the SRE engineer opens the dashboard
- **Then** the following SLOs are visible with current compliance percentage: API Availability (target ≥ 99%), p95 Pipeline Latency (target ≤ 15s), Pipeline Success Rate (target ≥ 95%); error budget remaining is shown for each
- **Verified by** Phase 14 dashboard setup verification

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §9 NFR §9.4 (Observability), §13 Platform Strategy |
| **Deployment** | Grafana Cloud free tier (10k Prometheus series, 50GB Loki, 50GB Tempo); OTel SDK in FastAPI (`src/collection_assistant/observability/`) pointing to Grafana OTLP endpoint |
| **Observability** | All 9 metrics from `observability_strategy.md §3.1`; all 8 log events from `§4.4`; all span attributes from `§5.2`; all 4 dashboards from `§6`; all 5 alert rules from `§7.2` |
| **SRE** | All 5 SLOs from `sre_strategy.md §4`; error budget tracking via Grafana SLO dashboard; this UC is the SRE engineer's primary daily tool; Grafana dashboard IS the SRE artefact shown to the client in the demo |
