# DevOps Strategy — AI FDE Collection Assistant

## 1. Overview

This document defines the DevOps strategy for the FDE Collection Assistant PoC. All infrastructure is zero-cost and requires no credit card. The pipeline demonstrates production-grade DevOps practices within a free-tier constraint.

**Platforms:** GitHub · GitHub Actions · Render.com · Streamlit Community Cloud · GitHub Container Registry (GHCR)

---

## 2. Repository & Branch Strategy

### 2.1 Branch Model

```
main          ← production-ready; protected; deploys to prod
  │
  └── develop ← integration branch; deploys to staging
        │
        ├── feature/agent-customer-profile
        ├── feature/nba-agent
        ├── fix/dispute-hold-logic
        └── chore/update-dependencies
```

| Branch | Protection Rules | Auto-Deploy Target |
|---|---|---|
| `main` | Requires PR + 1 review + all checks green | Render prod + Streamlit prod |
| `develop` | Requires all checks green | Render staging |
| `feature/*` | Checks run on PR open | No auto-deploy |

### 2.2 Commit Convention
Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     new capability or agent
fix:      bug fix
chore:    dependency/config change
docs:     documentation only
test:     test additions or corrections
refactor: code restructure, no behaviour change
ci:       changes to GitHub Actions workflows
```

### 2.3 PR Workflow
1. Create `feature/*` branch from `develop`
2. Open PR → triggers CI checks automatically
3. PR requires: all checks green + 1 approval
4. Squash-merge into `develop`
5. Promote `develop` → `main` via PR for production release

---

## 3. CI/CD Pipeline (GitHub Actions)

### 3.1 Pipeline Overview

```
Trigger: push to any branch / PR opened
│
├── Job 1: lint-and-typecheck    (fast, ~1 min)
│   ├── ruff check src/ tests/
│   └── mypy src/
│
├── Job 2: test                  (depends on Job 1, ~3 min)
│   ├── pytest tests/unit/
│   ├── pytest tests/integration/ (with mock LLM responses)
│   └── coverage report → fail if < 80%
│
├── Job 3: build                 (depends on Job 2, main/develop only)
│   ├── docker build -t ghcr.io/ivar06516/collection-api:$SHA
│   ├── docker build -t ghcr.io/ivar06516/collection-ui:$SHA
│   └── docker push → GHCR
│
├── Job 4: deploy-staging        (depends on Job 3, develop branch only)
│   └── trigger Render staging deploy webhook
│
└── Job 5: deploy-prod           (depends on Job 3, main branch only)
    ├── trigger Render prod deploy webhook
    └── notify Streamlit Community Cloud (git push auto-triggers)
```

### 3.2 Workflow File — `.github/workflows/ci.yml`

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: ghcr.io
  API_IMAGE: ghcr.io/${{ github.repository }}/collection-api
  UI_IMAGE:  ghcr.io/${{ github.repository }}/collection-ui

jobs:

  lint-and-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff mypy
      - run: ruff check src/ tests/
      - run: mypy src/

  test:
    needs: lint-and-typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov=src --cov-fail-under=80 -v
      - uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/

  build:
    needs: test
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build & push API image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.api
          push: true
          tags: ${{ env.API_IMAGE }}:${{ github.sha }},${{ env.API_IMAGE }}:latest
      - name: Build & push UI image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.ui
          push: true
          tags: ${{ env.UI_IMAGE }}:${{ github.sha }},${{ env.UI_IMAGE }}:latest

  deploy-staging:
    needs: build
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Trigger Render staging deploy
        run: |
          curl -X POST "${{ secrets.RENDER_STAGING_DEPLOY_HOOK }}"

  deploy-prod:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Trigger Render prod deploy
        run: |
          curl -X POST "${{ secrets.RENDER_PROD_DEPLOY_HOOK }}"
```

---

## 4. Docker Containerisation

### 4.1 File Structure

```
docker/
├── Dockerfile.api    ← FastAPI backend
├── Dockerfile.ui     ← Streamlit UI
└── docker-compose.yml  ← local development
```

### 4.2 Dockerfile.api

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[api]"

COPY src/ src/
COPY data/ data/

EXPOSE 8000
CMD ["uvicorn", "collection_assistant.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
```

### 4.3 Dockerfile.ui

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[ui]"

COPY ui/ ui/
COPY .streamlit/ .streamlit/

EXPOSE 8501
CMD ["streamlit", "run", "ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
```

### 4.4 docker-compose.yml (local dev)

```yaml
version: "3.9"
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./data:/app/data       # persist SQLite DB
      - ./src:/app/src         # hot-reload

  ui:
    build:
      context: .
      dockerfile: docker/Dockerfile.ui
    ports: ["8501:8501"]
    environment:
      - API_URL=http://api:8000
    depends_on: [api]
```

---

## 5. Deployment Targets

### 5.1 Streamlit Community Cloud (UI)

| Property | Value |
|---|---|
| URL | `https://fde-collection-assistant.streamlit.app` |
| Trigger | Auto-deploy on push to `main` (git integration) |
| Secrets | Managed in Streamlit Cloud secrets (TOML format) |
| Config | `.streamlit/config.toml` for Accenture theme |
| Limitation | Public repo required for free tier |

**Streamlit secrets format (`.streamlit/secrets.toml` — git-ignored):**
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
API_URL           = "https://fde-collection-api.onrender.com"
```

### 5.2 Render.com (FastAPI Backend)

| Property | Value |
|---|---|
| Service type | Web Service |
| Runtime | Docker (pulls from GHCR) |
| Deploy trigger | Webhook from GitHub Actions on `main`/`develop` push |
| Environment | `ANTHROPIC_API_KEY`, `DATABASE_URL`, `OTEL_ENDPOINT` set in Render dashboard |
| Free tier caveat | Service sleeps after 15 min idle; cold-start ~30s (acceptable for PoC) |
| Health check | `GET /health` — Render uses this to verify deploy success |

**render.yaml (infrastructure-as-code):**
```yaml
services:
  - type: web
    name: fde-collection-api
    runtime: docker
    dockerfilePath: docker/Dockerfile.api
    healthCheckPath: /health
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false               # set manually in Render dashboard
      - key: DATABASE_URL
        value: sqlite:///data/collection_assistant.db
      - key: LOG_LEVEL
        value: INFO
```

---

## 6. Environment Strategy

| Environment | Branch | API Host | UI Host | Data |
|---|---|---|---|---|
| Local | any | `localhost:8000` | `localhost:8501` | `data/local.db` |
| Staging | `develop` | `staging-api.onrender.com` | N/A | seeded staging DB |
| Production | `main` | `fde-collection-api.onrender.com` | `fde-collection-assistant.streamlit.app` | seeded prod DB |

---

## 7. Secrets Management

| Secret | Where Stored | How Accessed |
|---|---|---|
| `ANTHROPIC_API_KEY` | GitHub Secrets + Render env + Streamlit secrets | `os.environ` via pydantic-settings |
| `RENDER_PROD_DEPLOY_HOOK` | GitHub Secrets | Used in CI deploy step only |
| `RENDER_STAGING_DEPLOY_HOOK` | GitHub Secrets | Used in CI deploy step only |
| `GRAFANA_OTLP_ENDPOINT` | Render env vars | OTel exporter config |
| `GRAFANA_OTLP_TOKEN` | GitHub Secrets + Render env | OTel exporter auth header |

**Rules:**
- Never commit secrets to git — `.env` and `secrets.toml` are git-ignored
- Rotate API keys if accidentally exposed — invalidate immediately in Anthropic console
- Use GitHub environment protection rules to restrict prod secrets to `main` branch only

---

## 8. Local Development Setup

```bash
# 1. Clone and install
git clone https://github.com/ivar06516/ai-fde-collection-assistant.git
cd ai-fde-collection-assistant
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY

# 3. Seed the database
python scripts/seed_db.py

# 4a. Run with docker-compose (recommended)
docker-compose up

# 4b. Run services individually
uvicorn collection_assistant.api.main:app --reload --port 8000
streamlit run ui/app.py
```

---

## 9. Key Files Reference

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Full CI/CD pipeline |
| `docker/Dockerfile.api` | FastAPI container |
| `docker/Dockerfile.ui` | Streamlit container |
| `docker/docker-compose.yml` | Local dev orchestration |
| `render.yaml` | Render.com IaC config |
| `.streamlit/config.toml` | Accenture theme + app config |
| `scripts/seed_db.py` | Synthetic data ingestion |
| `.env.example` | Environment variable template |
