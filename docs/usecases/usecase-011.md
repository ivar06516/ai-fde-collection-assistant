# UC-011: Respond to Service Incident

## Overview

| Field | Value |
|---|---|
| **ID** | UC-011 |
| **Actor** | SRE Engineer |
| **Goal** | Detect, triage, mitigate, and resolve a service incident; restore the pipeline within SLO and document the incident |
| **Priority** | P1 — demonstrates SRE incident management practices |
| **Delivery Phase** | Phase 14 (Grafana alerts), Phase 15 (UptimeRobot) |
| **Platforms** | UptimeRobot (detection), Grafana Cloud (diagnosis), Render.com (mitigation), GitHub Issues (documentation) |

---

## Preconditions

- UptimeRobot monitors configured for `/health` endpoint and Streamlit UI URL
- Grafana alerting configured with at least one active rule
- SRE engineer has access to Render.com dashboard and GitHub Actions
- Incident severity definitions known (P1–P4 from `sre_strategy.md §8.1`)

---

## Incident Severity Levels

| Severity | Definition | Example | Target Resolution |
|---|---|---|---|
| **P1 — Critical** | Service completely unavailable | API returns 500 for all requests | < 1 hour |
| **P2 — Major** | Core feature broken, partial availability | NBA agent always fails | < 4 hours |
| **P3 — Minor** | Degraded performance, within SLO | p95 latency increased but < 15s | < 1 business day |
| **P4 — Informational** | Anomaly detected, no user impact | Token usage trending up | Monitor only |

---

## Main Flow — P1 API Down Incident

| Step | Actor | Action |
|---|---|---|
| 1 | System | UptimeRobot detects `/health` returning non-200 for 2 consecutive 5-min checks → sends email alert |
| 2 | SRE Engineer | Receives alert; opens UptimeRobot dashboard; notes outage start time |
| 3 | SRE Engineer | Opens Render.com dashboard → checks service logs for crash/OOM |
| 4 | SRE Engineer | Opens Grafana Loki → queries `{service="collection-assistant-api"} \| json \| level="critical"` |
| 5 | SRE Engineer | Identifies root cause (cold-start crash / bad deploy / SQLite lock — see `sre_strategy.md §8.3`) |
| 6 | SRE Engineer | Mitigates: redeploy via Render (rollback to previous deploy) OR trigger GitHub Actions re-deploy |
| 7 | System | Service recovers; UptimeRobot sends recovery email |
| 8 | SRE Engineer | Verifies: `GET /health` returns 200; manually runs one workflow via UI |
| 9 | SRE Engineer | Creates GitHub Issue: `[INCIDENT] API Down — <date>` with timeline, root cause, resolution |
| 10 | SRE Engineer | Calculates error budget impact: downtime_minutes / 432 (7h 12m budget in 30 days for 99% SLO) |

---

## Common Failure Modes and Mitigations

| Failure | Symptoms | Mitigation |
|---|---|---|
| Render cold start | First request after 15 min idle takes ~30s | UptimeRobot keep-warm monitor pings `/health` every 5 min |
| SQLite locked | `OperationalError: database is locked` in Loki | Single Render instance enforces single writer; restart service |
| Groq API down | `agent_failed` log events for all LLM agents | Check `status.groq.com`; wait or implement circuit breaker |
| Bad deploy (regression) | Error rate spike immediately after deploy | Rollback via Render dashboard to previous deploy image |
| LangGraph state corruption | Workflow stuck in `in_progress` | 30s timeout guard in Orchestrator; dead-letter to `error_log` |

---

## Acceptance Criteria

### AC-011-01: UptimeRobot Alert Fires Within 15 Minutes of Outage
- **Given** the Render.com API service goes down (simulated by stopping the service)
- **When** 2 consecutive UptimeRobot 5-minute checks fail
- **Then** an email alert is received within 15 minutes of the service going down
- **Verified by** Phase 15 alert test: stop Render service, measure time to email receipt

### AC-011-02: Recovery Email Sent When Service Restored
- **Given** an active UptimeRobot outage alert
- **When** the service is restored and `GET /health` returns 200
- **Then** a recovery email is sent by UptimeRobot within 10 minutes of restoration
- **Verified by** Phase 15 recovery test

### AC-011-03: Rollback Restores Service Within 5 Minutes
- **Given** a bad deploy has caused the API to return 500 for all requests
- **When** the SRE engineer rolls back to the previous Render deploy (via Render dashboard)
- **Then** the service is healthy (`GET /health` = 200) within 5 minutes of initiating rollback
- **Verified by** Phase 14 deployment test with intentional bad deploy then rollback

### AC-011-04: Loki Provides Root Cause Evidence
- **Given** a P1 incident caused by an application error (not infrastructure)
- **When** Loki is queried for `level="critical"` logs during the incident window
- **Then** at least one log entry contains a stack trace or error message identifying the failing component
- **Verified by** Phase 14 observability test: trigger a known error, verify it appears in Loki

### AC-011-05: GitHub Issue Created for P1/P2 Incidents
- **Given** a P1 or P2 incident has been resolved
- **When** the post-incident review is conducted
- **Then** a GitHub Issue exists with label `incident` containing: incident timeline, root cause analysis, error budget impact, and at least one action item to prevent recurrence
- **Verified by** Manual process check; GitHub Issues page filtered by `label:incident`

### AC-011-06: Error Budget Calculation Documented
- **Given** a P1 incident has resolved
- **When** the GitHub Issue is written
- **Then** the error budget consumed is calculated as: `downtime_minutes / 432 × 100%` for the 99% availability SLO (432 min = 7h 12m budget per 30 days); this percentage is recorded in the issue
- **Verified by** Manual review of incident GitHub Issue

### AC-011-07: UptimeRobot Public Status Page is Accessible
- **Given** UptimeRobot monitors are configured
- **When** the public status page URL is opened (`stats.uptimerobot.com/...`)
- **Then** the page loads and shows the current status of both the API and UI services with uptime percentages
- **Verified by** Phase 15 setup verification; URL documented in `sre_strategy.md §11`

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §9.1 Performance NFR, §9.2 Reliability NFR, §13 Platform Strategy |
| **Deployment** | UptimeRobot (detection + public status page); Grafana Cloud Loki + Tempo (diagnosis); Render.com rollback (mitigation); GitHub Actions re-deploy (mitigation); GitHub Issues (documentation) |
| **Observability** | Loki `level="critical"` query for root cause; Tempo trace for last-good vs first-failed request comparison; `workflow_completion_status{status="error"}` Prometheus spike during incident window |
| **SRE** | Full incident response procedure in `sre_strategy.md §8`; common failure modes in `§8.3`; error budget policy in `§5`; API availability SLO 99% with 7h 12m budget/month; post-incident review required for all P1/P2 |
