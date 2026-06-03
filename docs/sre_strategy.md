# SRE Strategy — AI FDE Collection Assistant

## 1. Overview

Site Reliability Engineering (SRE) applies software engineering principles to infrastructure and operations. For this PoC, the SRE strategy is scoped to what is demonstrable with zero cost: **SLO definition, error budget tracking, uptime monitoring, alerting, and an incident runbook.**

**Platforms:** UptimeRobot (free) · Grafana Cloud Alerting (free) · GitHub Issues (incident tracking)

> **PoC scope note:** A full production SRE practice would include on-call rotations, paging systems (PagerDuty/OpsGenie), chaos engineering, and capacity planning. Those are referenced here for completeness but are out of scope for the PoC deployment.

---

## 2. Service Inventory

| Service | Host | Health Endpoint | Criticality |
|---|---|---|---|
| FastAPI Backend | Render.com | `GET /health` | P1 — pipeline cannot run without it |
| Streamlit UI | Streamlit Community Cloud | `/` (HTTP 200) | P2 — demo interface |
| SQLite Database | Local to API container | Internal healthcheck | P1 — data unavailability = failure |
| Grafana Cloud | SaaS | Grafana status page | P3 — observability only |

---

## 3. SLIs — Service Level Indicators

SLIs are the raw measurements from which SLOs are derived.

| SLI | Measurement Method | Source |
|---|---|---|
| **Availability** | % of `/health` checks returning HTTP 200 | UptimeRobot |
| **Pipeline latency (p95)** | 95th percentile of `collection_workflow_duration_seconds` | Grafana / Prometheus |
| **Pipeline success rate** | `completed` workflows / total workflows | Prometheus counter |
| **Agent error rate** | Failed agent calls / total agent calls | Prometheus counter |
| **NBA recommendation rate** | Workflows returning a valid NBA action / total completed workflows | Prometheus counter |

---

## 4. SLOs — Service Level Objectives

SLOs define the reliability targets we commit to maintaining. These are set conservatively for a PoC.

| SLO | Target | Measurement Window | SLI Used |
|---|---|---|---|
| **API Availability** | ≥ 99.0% | Rolling 30 days | UptimeRobot uptime % |
| **Pipeline p95 Latency** | ≤ 15 seconds | Rolling 7 days | Prometheus histogram |
| **Pipeline Success Rate** | ≥ 95% | Rolling 7 days | Prometheus counter ratio |
| **Agent Error Rate** | ≤ 2% | Rolling 24 hours | Prometheus counter ratio |
| **NBA Recommendation Rate** | ≥ 98% of completed workflows | Rolling 7 days | Prometheus counter ratio |

### SLO Rationale

| SLO | Why This Target |
|---|---|
| 99% availability | Render free tier has cold starts (~30s); 1% downtime budget accommodates occasional cold starts and deploy windows |
| 15s p95 latency | Two parallel stages + NBA synthesis; 99th percentile measured at ~12s in testing; 15s gives headroom |
| 95% pipeline success | LLM API is external; 5% budget covers transient Anthropic API errors and retry exhaustion |
| 2% agent error rate | Per-agent; each agent has 3 retries before failing, so 2% reflects genuine failures not transient blips |

---

## 5. Error Budgets

The error budget is the allowed amount of unreliability within the SLO window.

| SLO | Target | Error Budget (30 days) |
|---|---|---|
| API Availability (99%) | 99.0% | 7h 12m of downtime allowed |
| Pipeline Success Rate (95%) | 95.0% | 5 failures per 100 runs |
| Agent Error Rate (2%) | ≤ 2.0% | 2 agent failures per 100 agent calls |

### Error Budget Policy

| Budget Remaining | Action |
|---|---|
| > 50% | Normal operations; new features can be deployed |
| 25–50% | Review recent incidents; slow down risky deployments |
| < 25% | Freeze non-critical deploys; prioritise reliability fixes |
| 0% (exhausted) | Stop all feature work; focus exclusively on reliability until window resets |

**Budget tracking:** Grafana Cloud dashboard "SLO & Error Budget" updated in real time from Prometheus metrics.

---

## 6. Uptime Monitoring (UptimeRobot)

### 6.1 Monitors Configured

| Monitor | URL | Type | Interval | Alert |
|---|---|---|---|---|
| API Health | `https://fde-collection-api.onrender.com/health` | HTTP(S) | 5 min | Email on down |
| UI Availability | `https://fde-collection-assistant.streamlit.app` | HTTP(S) | 5 min | Email on down |
| API Response Time | Same as API Health | Keyword check + response time | 5 min | Alert if > 10s |

### 6.2 Public Status Page

UptimeRobot generates a free public status page at:
`https://stats.uptimerobot.com/fde-collection-assistant`

The status page shows:
- Current operational status of both services
- 90-day uptime history
- Incident history

This is the **SRE artefact** to show stakeholders during the demo.

### 6.3 Health Endpoint Implementation

```python
# src/collection_assistant/api/routes/health.py
from fastapi import APIRouter
from sqlalchemy import text
from collection_assistant.db.session import get_db

router = APIRouter()

@router.get("/health")
async def health_check():
    # Check DB connectivity
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "0.1.0",
    }
```

---

## 7. Alerting Strategy

### 7.1 Alert Routing

```
Grafana Alerting (metric threshold breached)
    │
    ├── Critical alerts  → Email (immediate)
    │                    → GitHub Issue auto-created (via webhook)
    │
    └── Warning alerts   → Email (batched, 15 min digest)

UptimeRobot (service down)
    │
    └── Email (immediate on down, email on recovery)
```

### 7.2 Alert Definitions

**Critical (immediate action required):**

| Alert | Condition | Resolution |
|---|---|---|
| API Down | `/health` non-200 for 2 consecutive 5-min checks | Check Render logs; cold start vs crash |
| Pipeline Failure Surge | Error rate > 10% over 5 min | Check Grafana traces; likely LLM API issue |
| Error Budget Exhausted | SLO error budget drops to 0% | Freeze deploys; investigate root cause |

**Warning (investigate within 1 business day):**

| Alert | Condition | Resolution |
|---|---|---|
| High Latency | p95 pipeline latency > 15s over 10 min | Check agent-level traces for bottleneck |
| Token Spike | Token usage rate doubles vs 1h moving avg | Check for retry loops or prompt bloat |
| Dispute Hold Surge | Hold rate > 30% of runs over 1h | May indicate bad seed data; check disputes table |

---

## 8. Incident Response Runbook

### 8.1 Incident Severity Levels

| Severity | Definition | Example |
|---|---|---|
| P1 — Critical | Service completely unavailable | API returns 500 for all requests |
| P2 — Major | Core feature broken but service partially available | NBA agent always fails; pipeline returns error |
| P3 — Minor | Degraded performance or partial failure | p95 latency increased but within SLO |
| P4 — Informational | Anomaly detected, no user impact yet | Token usage trending up over 48h |

### 8.2 Incident Response Steps

```
1. DETECT
   UptimeRobot / Grafana alert fires → email received

2. TRIAGE (within 15 min)
   ├── Check UptimeRobot status page — is the service up?
   ├── Check Grafana dashboard — which metric triggered?
   ├── Check Loki logs — find the error event
   └── Check Tempo traces — which agent span failed?

3. CLASSIFY SEVERITY
   Assign P1–P4 based on table above

4. COMMUNICATE
   ├── P1/P2: Create GitHub Issue with label `incident`
   │         Title: [INCIDENT] <brief description> — <date>
   └── P3/P4: Add note to ongoing monitoring log

5. MITIGATE (stop the bleeding)
   ├── If API down on Render → check Render dashboard → redeploy if needed
   ├── If LLM API errors → check Anthropic status page → wait or reduce load
   ├── If DB corrupt → run `python scripts/reset_db.py` to reseed
   └── If bad deploy → roll back via Render dashboard (previous deploy)

6. RESOLVE
   Fix root cause → deploy fix → verify with Grafana

7. POST-INCIDENT REVIEW (within 48h for P1/P2)
   Document in GitHub Issue:
   - Timeline of events
   - Root cause
   - Error budget impact
   - Actions to prevent recurrence
```

### 8.3 Common Failure Modes & Mitigations

| Failure Mode | Symptoms | Mitigation |
|---|---|---|
| Anthropic API timeout | NBA / Orchestrator agent times out; `agent_failed` logs | 3 retries with exponential backoff (already configured). If persistent, Anthropic status page |
| Render cold start | First request after 15 min idle takes ~30s | UptimeRobot ping every 5 min keeps it warm (use a dedicated keep-warm monitor) |
| SQLite locked | `OperationalError: database is locked` in logs | SQLite allows only one writer; ensure single-instance deploy (Render free = 1 instance) |
| LangGraph state corruption | Workflow stuck in `in_progress` | Timeout guard in Orchestrator (30s max per agent); dead-letter log in `error_log` field |
| OTel exporter failure | Metrics/traces missing in Grafana | Non-fatal; pipeline continues. Alert if traces missing for > 30 min |
| Streamlit session timeout | UI shows blank / disconnected | User refreshes page; stateless design means no data loss |

---

## 9. Reliability Review Checklist

Run this before every production deploy:

**Code:**
- [ ] All tests passing (`pytest` green in CI)
- [ ] No new `mypy` type errors
- [ ] `ruff` lint clean
- [ ] Health endpoint tested locally

**Deployment:**
- [ ] Render staging deploy succeeded before promoting to prod
- [ ] Environment variables verified in Render dashboard
- [ ] Anthropic API key valid (test with a quick `/health` call after deploy)
- [ ] SQLite DB seeded on fresh deploy (`seed_db.py` run)

**Observability:**
- [ ] Metrics appearing in Grafana after deploy
- [ ] At least one trace visible in Tempo
- [ ] No error-level logs in Loki in first 5 min post-deploy

**SRE:**
- [ ] UptimeRobot showing "Up" for both services
- [ ] Error budget not in critical zone (> 25% remaining)
- [ ] No open P1/P2 incidents

---

## 10. SRE Maturity Model (PoC vs Production)

This table shows what is implemented in the PoC vs what a production SRE practice would add.

| Capability | PoC (Implemented) | Production (Future) |
|---|---|---|
| Uptime monitoring | UptimeRobot (5-min checks) | Synthetic monitoring every 30s, multi-region |
| Alerting | Email via Grafana + UptimeRobot | PagerDuty / OpsGenie with on-call rotation |
| SLO tracking | Grafana dashboard | Automated SLO reports, stakeholder reviews |
| Error budgets | Manual tracking in Grafana | Automated policy enforcement in CI/CD |
| Incident management | GitHub Issues | Full incident platform (Incident.io, Statuspage.io) |
| Chaos engineering | Not implemented | Regular game days, fault injection testing |
| Capacity planning | Not required (serverless) | Horizontal scaling strategy, load testing |
| Runbook | This document | Automated runbook in OpsWiki, runbook automation |

---

## 11. Key Links (Populate After Setup)

| Resource | URL |
|---|---|
| Public status page | `https://stats.uptimerobot.com/fde-collection-assistant` |
| Grafana dashboard | `https://your-org.grafana.net/d/collection-pipeline` |
| Render dashboard | `https://dashboard.render.com` |
| Streamlit Cloud | `https://share.streamlit.io` |
| GitHub Actions | `https://github.com/ivar06516/ai-fde-collection-assistant/actions` |
| Incident log | `https://github.com/ivar06516/ai-fde-collection-assistant/issues?label=incident` |
| Anthropic status | `https://status.anthropic.com` |
