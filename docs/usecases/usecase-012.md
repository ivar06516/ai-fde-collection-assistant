# UC-012: Deploy New Version via CI/CD Pipeline

## Overview

| Field | Value |
|---|---|
| **ID** | UC-012 |
| **Actor** | DevOps Engineer |
| **Goal** | Push a code change to GitHub and have it automatically linted, type-checked, tested, containerised, and deployed to both Render.com (API) and Streamlit Community Cloud (UI) without any manual steps |
| **Priority** | P1 — demonstrates DevOps pipeline maturity |
| **Delivery Phase** | Phase 13 |
| **Platforms** | GitHub Actions (CI/CD), GHCR (registry), Render.com (API deploy), Streamlit Community Cloud (UI deploy) |

---

## Preconditions

- Code change is committed on a `feature/*` branch
- `.github/workflows/ci.yml` is present and configured
- `RENDER_PROD_DEPLOY_HOOK` and `RENDER_STAGING_DEPLOY_HOOK` are set as GitHub Secrets
- Anthropic API key is set in both Render.com environment and GitHub Secrets
- Branch protection: `main` and `develop` require all checks to pass before merge

---

## CI/CD Pipeline Stages

```
Push / PR Open
      │
      ├─ Job 1: lint-and-typecheck    (~1 min)
      │    ├─ ruff check src/ tests/
      │    └─ mypy src/
      │
      ├─ Job 2: test                  (~3 min, depends on Job 1)
      │    ├─ pytest tests/ --cov=src --cov-fail-under=80
      │    └─ upload coverage report as artefact
      │
      ├─ Job 3: build                 (main/develop only, depends on Job 2)
      │    ├─ docker build Dockerfile.api → push ghcr.io/.../collection-api:$SHA
      │    └─ docker build Dockerfile.ui  → push ghcr.io/.../collection-ui:$SHA
      │
      ├─ Job 4: deploy-staging        (develop only, depends on Job 3)
      │    └─ curl Render staging webhook
      │
      └─ Job 5: deploy-prod           (main only, depends on Job 3)
           ├─ curl Render prod webhook
           └─ Streamlit Cloud auto-deploys from main push
```

---

## Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | DevOps Engineer | Opens PR from `feature/*` to `develop` | GitHub Actions triggers CI (Jobs 1 + 2) |
| 2 | System | Jobs 1 + 2 pass | PR status checks show green; merge is unblocked |
| 3 | DevOps Engineer | Gets 1 reviewer approval; merges PR to `develop` | GitHub Actions triggers Jobs 1 + 2 + 3 + 4 (staging deploy) |
| 4 | System | Staging deploy succeeds | Render staging URL is healthy |
| 5 | DevOps Engineer | Opens PR from `develop` to `main` | All checks run again; 1 reviewer required |
| 6 | DevOps Engineer | Merges to `main` | GitHub Actions triggers Jobs 1 + 2 + 3 + 5 (prod deploy) |
| 7 | System | Render prod deploy + Streamlit auto-deploy complete | Both production services are running new version |
| 8 | DevOps Engineer | Runs reliability review checklist (`sre_strategy.md §9`) | Grafana metrics healthy; `/health` returns 200; error budget OK |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | `ruff check` finds lint error | Job 1 fails; PR merge is blocked; developer fixes lint issue |
| AF-02 | `mypy` finds type error | Job 1 fails; PR merge is blocked |
| AF-03 | `pytest` fails | Job 2 fails; PR merge is blocked; coverage report uploaded for review |
| AF-04 | Coverage < 80% | Job 2 fails with `--cov-fail-under=80`; developer adds tests |
| AF-05 | Docker build fails | Job 3 fails; staging and prod deploys do not trigger |
| AF-06 | Render deploy fails | Render automatically rolls back to previous image; `GET /health` check on the new deploy fails; alert fires |
| AF-07 | Error budget < 25% | Deploy freeze policy: do not merge non-critical PRs until budget recovers |

---

## Acceptance Criteria

### AC-012-01: Lint Failure Blocks PR Merge
- **Given** a PR with a `ruff` lint violation (e.g., unused import)
- **When** GitHub Actions runs Job 1
- **Then** Job 1 fails; the PR merge button is disabled; the PR shows a failed status check
- **Verified by** Phase 13 CI test: commit a known lint violation, assert PR is blocked

### AC-012-02: Type Error Blocks PR Merge
- **Given** a PR introducing a `mypy` type error (e.g., passing `str` where `int` expected)
- **When** GitHub Actions runs Job 1
- **Then** Job 1 fails and the PR is blocked from merge
- **Verified by** Phase 13 CI test: commit a known type error, assert PR is blocked

### AC-012-03: Test Failure Blocks PR Merge
- **Given** a PR that breaks an existing unit test
- **When** GitHub Actions runs Job 2
- **Then** Job 2 fails with the failing test name reported; PR is blocked
- **Verified by** Phase 13 CI test: commit a change that breaks a known test

### AC-012-04: Coverage Below 80% Blocks Merge
- **Given** a PR that removes tests reducing coverage below 80%
- **When** GitHub Actions runs Job 2 with `--cov-fail-under=80`
- **Then** Job 2 fails with coverage percentage shown; PR is blocked
- **Verified by** Phase 13 CI test: remove a test file and verify coverage gate triggers

### AC-012-05: Docker Images Pushed to GHCR on Main/Develop
- **Given** a PR merges to `develop` and all jobs pass
- **When** Job 3 runs
- **Then** two Docker images are pushed to GHCR with the commit SHA tag: `ghcr.io/ivar06516/collection-api:$SHA` and `ghcr.io/ivar06516/collection-ui:$SHA`; the `latest` tag is also updated
- **Verified by** Phase 13 CI test: check GHCR for images with correct SHA tag after merge

### AC-012-06: Staging Deploys Automatically on Develop Push
- **Given** a merge to `develop` that passes all jobs
- **When** Job 4 (deploy-staging) runs
- **Then** Render staging service receives the deploy webhook; staging deploy completes within 5 minutes; staging `GET /health` returns `{"status": "healthy"}`
- **Verified by** Phase 13 staging deploy test: merge to develop, poll staging health endpoint

### AC-012-07: Production Deploys Automatically on Main Push
- **Given** a merge to `main` that passes all jobs
- **When** Job 5 (deploy-prod) runs
- **Then** Render prod deploy completes within 5 minutes; prod `GET /health` returns `{"status": "healthy"}`; Streamlit Community Cloud auto-deploys the new UI within 3 minutes of the `main` push
- **Verified by** Phase 13 prod deploy test: merge to main, poll both prod health endpoint and Streamlit URL

### AC-012-08: Rollback Restores Previous Version
- **Given** a bad deploy causes the prod API to fail health checks
- **When** the SRE engineer initiates a rollback via the Render dashboard (previous deploy)
- **Then** the previous version is live within 5 minutes; `GET /health` returns 200
- **Verified by** Phase 13 rollback test with intentional bad deploy image

### AC-012-09: Error Budget Policy Enforced Before Deploy
- **Given** the error budget for API Availability drops below 25%
- **When** a DevOps engineer attempts to merge a non-critical PR
- **Then** the deploy freeze policy is applied (documented in `sre_strategy.md §5`): non-critical merges are paused; only reliability-fixing PRs proceed
- **Verified by** Manual process gate; documented in `devops_strategy.md §X` deploy checklist

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §13 Deployment & Platform Strategy, §13.4 Phase 13 deliverable |
| **Deployment** | GitHub Actions (`ci.yml` — `devops_strategy.md §3.2`); GHCR (container registry — `§3.2`); Render.com webhook deploy (`§5.2`); Streamlit Community Cloud git-push auto-deploy (`§5.1`) |
| **Observability** | Post-deploy: Grafana metrics healthy within 2 min (`UC-010 AC-010-01`); no `ERROR` level Loki logs in first 5 min; Tempo traces visible for first post-deploy workflow run |
| **SRE** | Deploy reliability checklist in `sre_strategy.md §9`; error budget policy gates production deploy (`§5`); branch protection rules enforce test coverage; AC-012-08 rollback is the SRE mitigation for a bad deploy; this UC represents the operational flywheel: DevOps pipeline → Observability verification → SRE gating |
