# UC-008: Seed Synthetic Customer Database

## Overview

| Field | Value |
|---|---|
| **ID** | UC-008 |
| **Actor** | Data Admin / FDE Demo Presenter |
| **Goal** | Populate the SQLite database with ~100 realistic retail customers (including 10 mandatory named scenarios) so all collection workflow use cases have data to query |
| **Priority** | P0 — prerequisite for UC-001 through UC-007 and UC-009 |
| **Delivery Phase** | Phase 2 |
| **Script** | `scripts/seed_db.py` |
| **UI Entry Point** | Streamlit sidebar → Data Management panel |

---

## Preconditions

- Python environment installed (`pip install -e ".[dev]"`)
- `.env` file present with `DATABASE_URL` (defaults to `sqlite:///data/collection_assistant.db`)
- `data/` directory exists (script creates it if absent)

---

## Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | Data Admin | Runs `python scripts/seed_db.py` OR clicks **Seed Database** in Streamlit sidebar | Script begins; creates `data/collection_assistant.db` if absent |
| 2 | System | Alembic migration executes | All 6 tables created: `customers`, `accounts`, `payment_history`, `disputes`, `interaction_history`, `workflow_audit` |
| 3 | System | Inserts 10 mandatory named scenarios | John Smith, Sarah Jones, Michael Tan, Emily Carter, Robert Davis, Karen Wilson, David Brown, Anna Zhang, James O'Brien, Lisa Park |
| 4 | System | Generates ~90 random customers via Faker (seed = 42) | Realistic UK/AU/US names, addresses, income, employment distribution |
| 5 | System | Generates accounts, payment histories, disputes, interactions | ~150 accounts, ~2,000 payment rows, ~40 disputes, ~300 interactions |
| 6 | System | Prints/displays summary | Terminal or Streamlit sidebar shows: record counts per table |

---

## CLI Reference

```bash
python scripts/seed_db.py                 # Default: seed 100 customers (idempotent)
python scripts/seed_db.py --reset         # Drop all tables, recreate, re-seed
python scripts/seed_db.py --count 200     # Seed with 200 random customers
python scripts/seed_db.py --scenarios-only  # Insert only the 10 named scenarios
```

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | `--reset` flag passed | All 6 tables dropped then recreated; all data regenerated from scratch |
| AF-02 | `--scenarios-only` flag | Only 10 named scenarios inserted; minimal viable dataset for demo |
| AF-03 | DB already seeded (no `--reset`) | Script detects existing records; skips duplicate inserts (idempotent) |
| AF-04 | Migration fails (schema mismatch) | Alembic reports migration error; script exits non-zero; manual `--reset` required |

---

## 10 Mandatory Named Scenarios

| Customer ID | Name | Product | DPD | Scenario Type | Expected NBA |
|---|---|---|---|---|---|
| CUST-001 | John Smith | Personal Loan | 45 | Standard case — deteriorating | `initiate_call` |
| CUST-002 | Sarah Jones | Credit Card | 30 | Dispute hold | `place_on_hold` |
| CUST-003 | Michael Tan | Mortgage | 92 | Critical arrears | `escalate_to_legal` |
| CUST-004 | Emily Carter | Personal Loan | 12 | Improving customer | `no_action_required` |
| CUST-005 | Robert Davis | Personal Loan | 60 | Hardship (medical) | `offer_payment_plan` |
| CUST-006 | Karen Wilson | Credit Card | 180 | Written-off | `flag_for_writeoff` |
| CUST-007 | David Brown | Auto Loan | 35 | Multiple disputes | `place_on_hold` |
| CUST-008 | Anna Zhang | Mortgage | 120 | Legal action | `escalate_to_legal` |
| CUST-009 | James O'Brien | Personal Loan | 75 | Settlement candidate | `offer_settlement` |
| CUST-010 | Lisa Park | Credit Card | 0 | No action needed | `no_action_required` |

---

## Postconditions

- `data/collection_assistant.db` exists and is queryable
- All 10 named scenario customers and their accounts are accessible by known IDs
- Streamlit Input Panel dropdowns populated from DB
- FastAPI `/health` endpoint returns `"database": "healthy"`

---

## Acceptance Criteria

### AC-008-01: All Six Tables Created by Migration
- **Given** a fresh environment with no `collection_assistant.db`
- **When** `seed_db.py` is run
- **Then** all 6 tables exist: `customers`, `accounts`, `payment_history`, `disputes`, `interaction_history`, `workflow_audit`
- **Verified by** Phase 2 unit test querying `sqlite_master` for all 6 table names

### AC-008-02: All 10 Named Scenarios Present After Seeding
- **Given** `seed_db.py` is run (default or `--scenarios-only`)
- **When** the `customers` table is queried
- **Then** records exist for all 10 known `customer_id` values (CUST-001 through CUST-010) with correct names
- **Verified by** Phase 2 unit test selecting by customer_id for all 10

### AC-008-03: Record Counts Are Within Expected Ranges
- **Given** default seeding (`--count 100`)
- **When** seeding completes
- **Then** `customers` ≥ 100, `accounts` ≥ 100, `payment_history` ≥ 1,200, `disputes` ≥ 20, `interaction_history` ≥ 150
- **Verified by** Phase 2 unit test asserting MIN row counts per table

### AC-008-04: Seeding is Idempotent (Running Twice is Safe)
- **Given** `seed_db.py` has already been run once
- **When** `seed_db.py` is run a second time (without `--reset`)
- **Then** record counts do not change; no duplicate records created; script exits 0
- **Verified by** Phase 2 unit test running seed twice and comparing counts before/after second run

### AC-008-05: Reset Flag Drops and Recreates All Data
- **Given** a seeded DB with existing records
- **When** `seed_db.py --reset` is run
- **Then** all tables are dropped and recreated; fresh data inserted; final record counts match a fresh seed
- **Verified by** Phase 2 unit test comparing pre-reset and post-reset schemas

### AC-008-06: Faker Seed Produces Reproducible Data
- **Given** `seed_db.py` run twice on different machines with `--reset`
- **When** the `customers` table records are compared (excluding timestamps)
- **Then** first names, last names, and postcodes of records 11–100 are identical across both runs (Faker seed = 42)
- **Verified by** Phase 2 unit test comparing record fingerprints between two seeded instances

### AC-008-07: Streamlit Data Management Panel Shows Correct Counts
- **Given** a seeded DB
- **When** the Streamlit sidebar Data Management panel renders
- **Then** displayed counts for each table match the actual row counts in the DB
- **Verified by** Phase 9 UI unit test comparing panel display values to DB queries

### AC-008-08: FastAPI Health Check Confirms DB After Seeding
- **Given** `seed_db.py` has completed
- **When** `GET /health` is called
- **Then** response includes `"database": "healthy"` (DB connectivity confirmed)
- **Verified by** Phase 8 API test calling `/health` after seed

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §5.1 (SQLite decision), §5.2 (all 6 table schemas), §5.3 (10 named scenarios table), §5.4 (`seed_db.py` CLI), §5.5 (Streamlit Data Management panel) |
| **Deployment** | SQLite file at `data/collection_assistant.db` on Render.com; seed script must run as deploy startup hook (Render ephemeral filesystem resets on each deploy) |
| **Observability** | Startup log event `seed_completed` with table row counts; Grafana Data Management panel shows live DB stats; `GET /health` DB check |
| **SRE** | Prerequisite for all P0 use cases — empty DB = 100% pipeline failure rate; deploy checklist item: "SQLite DB seeded before service accepts traffic"; Render cold-deploy wipes ephemeral disk — seed runs on every fresh deploy |
