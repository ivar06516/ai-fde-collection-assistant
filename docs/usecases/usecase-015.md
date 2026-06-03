# UC-015: Dispute Precedent RAG and Historical Case Retrieval

## Overview

| Field | Value |
|---|---|
| **ID** | UC-015 |
| **Actor** | System (Dispute Agent + NBA Agent — enhanced with precedent retrieval) |
| **Goal** | (1) Dispute Agent retrieves classification precedents to aid dispute type identification; (2) NBA Agent retrieves similar past workflow outcomes to inform action selection with real historical evidence |
| **Priority** | P1 |
| **Delivery Phase** | Phase 18 (RAG pipelines), Phase 20 (real historical cases from `workflow_audit`) |
| **New Components** | `DisputeRetriever`, `HistoricalCaseRetriever`, ChromaDB collections: `dispute_precedents`, `historical_cases` |

---

## Two Sub-Use Cases

### UC-015A: Dispute Precedent RAG (Dispute Agent)

Dispute type classification currently relies solely on Groq Llama 3.3 70B reasoning. With a Dispute Precedent RAG, the agent retrieves similar past disputes before classifying — reducing misclassification.

**Document corpus:** `dispute_resolution_guide.md` — contains:
- 5-type taxonomy with example descriptions per type
- Key linguistic signals per dispute type (e.g., "charge I did not authorise" → `billing_error` or `fraud_claim`)
- Resolution procedure and collection hold criteria per type
- Escalation triggers (identity theft → escalate immediately; billing error → verify first)

**RAG Query:** dispute description text → retrieve top 2 matching dispute handling procedures

---

### UC-015B: Historical Case Retrieval (NBA Agent)

After ~20 pipeline runs, the `workflow_audit` table contains real precedents. The Historical Case Retriever queries cases with similar DPD, product type, and trajectory to provide the NBA Agent with empirical outcome data.

**In Phase 18 (before real runs accumulate):** 50 synthetic historical cases are pre-seeded by `scripts/seed_historical_cases.py`.

**In Phase 20 (after real runs):** `scripts/ingest_rag_documents.py --historical` ingests real `workflow_audit` records into ChromaDB.

---

## Main Flow — UC-015A: Dispute Precedent Retrieval

| Step | Action | Detail |
|---|---|---|
| 1 | Dispute Agent retrieves each active dispute's description | From `disputes.description` in SQLite via MCP Data Server |
| 2 | **RAG query** per dispute | `DisputeRetriever.retrieve(dispute_description, n_results=2)` |
| 3 | **Retrieved precedents injected** into classification prompt | "Similar disputes were classified as: {type}. Key signals: {signals}" |
| 4 | `classify_dispute_type()` LLM call | Groq Llama 3.3 70B classifies with precedent context → higher accuracy for edge cases |
| 5 | Classification result + retrieved precedents stored | `dispute_summary['classification_precedents']` added for Audit Trail |

---

## Main Flow — UC-015B: Historical Case Retrieval

| Step | Action | Detail |
|---|---|---|
| 1 | NBA Agent constructs case retrieval query | `f"DPD {days_past_due} {product_type} {arrears_trajectory}"` |
| 2 | `HistoricalCaseRetriever.retrieve(...)` | Filters by `trajectory = arrears_trajectory` metadata; returns top 2 by cosine similarity |
| 3 | Retrieved cases formatted | Each case: "Previous case: DPD 48, personal loan, deteriorating → `initiate_call` (conf 0.83), outcome: payment arrangement" |
| 4 | Injected into NBA Agent context | Alongside policy chunks from UC-014 |
| 5 | NBA rationale may reference precedent | "In 2 similar cases with DPD 40–50, deteriorating trajectory, `initiate_call` was effective" |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | `dispute_precedents` collection is empty | Dispute classification proceeds without retrieval; base LLM reasoning only |
| AF-02 | `historical_cases` collection has < 3 records | NBA Agent uses what's available; note added to rationale: "Limited historical precedent available" |
| AF-03 | No cases match the trajectory filter | Fall back to unfiltered cosine search |
| AF-04 | Phase 20 not yet reached (< 20 real runs) | Synthetic pre-seeded cases used as temporary historical dataset |

---

## Postconditions

- `dispute_summary` contains `classification_precedents` field (list of retrieved dispute procedures)
- `nba_recommendation` contains `retrieved_similar_cases` field (list of historical case summaries)
- Both retrievals logged in Audit Trail
- ChromaDB collections `dispute_precedents` and `historical_cases` queried (Prometheus counters incremented)

---

## Acceptance Criteria

### AC-015-01: Dispute Retriever Returns Relevant Procedure
- **Given** `dispute_resolution_guide.md` is ingested into `dispute_precedents` collection
- **When** `DisputeRetriever.retrieve("charge appeared on my statement that I did not make")` is called
- **Then** at least 1 of the 2 returned chunks is from the `billing_error` or `fraud_claim` section of the guide (matching linguistic signals "charge I did not make")
- **Verified by** Phase 18 unit test asserting returned chunk contains "billing_error" or "fraud_claim" keyword

### AC-015-02: Dispute Classification Accuracy Improves With RAG
- **Given** 10 test dispute descriptions spanning all 5 types
- **When** classification is run with RAG context vs. without
- **Then** RAG-enhanced classification achieves ≥ 80% accuracy across 5 types (vs. baseline measured without RAG); edge cases (e.g., "payment misapplied" which could be `payment_dispute` or `billing_error`) are correctly distinguished with retrieval
- **Verified by** Phase 18 classification accuracy test with labelled fixtures

### AC-015-03: Historical Case Retriever Returns Cases With Same Trajectory
- **Given** 50 pre-seeded synthetic cases in `historical_cases` collection with `trajectory` metadata
- **When** `HistoricalCaseRetriever.retrieve(days_past_due=45, product_type="personal_loan", arrears_trajectory="deteriorating")` is called
- **Then** returned cases have `metadata.trajectory = "deteriorating"` (metadata filter applied); at least 1 case with a DPD within ±20 days of 45 is returned
- **Verified by** Phase 18 unit test asserting trajectory metadata filter

### AC-015-04: Historical Cases Visible in NBA Card UI
- **Given** a completed pipeline run with historical RAG enabled
- **When** the NBA Recommendation card's "Retrieved Context" panel is expanded
- **Then** at least 1 historical case entry is visible showing: case DPD, product type, NBA action taken, and confidence score
- **Verified by** Phase 19 Streamlit UI test

### AC-015-05: Real Historical Cases Ingested From `workflow_audit`
- **Given** ≥ 20 completed workflow runs in `workflow_audit` table
- **When** `python scripts/ingest_rag_documents.py --historical` is run
- **Then** `historical_cases` ChromaDB collection count increases by the number of new completed workflow records; each ingested document has metadata: `dpd`, `product_type`, `trajectory`, `nba_action`
- **Verified by** Phase 20 ingestion test after accumulating 20 real runs

### AC-015-06: Dispute Precedents in Audit Trail
- **Given** a dispute with description text is active on an account
- **When** the Dispute Agent runs with RAG enabled and `GET /audit` is called
- **Then** the `dispute` agent step in the audit trail includes a `classification_precedents` array with at least 1 retrieved chunk and its source filename
- **Verified by** Phase 18 integration test asserting Dispute Agent audit output

### AC-015-07: Both RAG Pipelines Compose Without Conflict
- **Given** a pipeline run where both UC-014 (Policy RAG) and UC-015 (Dispute + Historical Case RAG) are active
- **When** the full pipeline runs
- **Then** the NBA Agent's `retrieved_policy_chunks` and `retrieved_similar_cases` both have data; no interference between the two retrieval operations; total RAG overhead < 3 seconds
- **Verified by** Phase 18 full-pipeline integration test timing RAG component

### AC-015-08: Dispute Hold is Unaffected by Dispute RAG
- **Given** David Brown (CUST-007) with 2 active disputes both having `collection_hold = 1`
- **When** Dispute Agent runs with RAG precedent retrieval
- **Then** `dispute_summary.collection_hold = True` regardless of retrieved precedents; the hold flag is determined by the DB `collection_hold` field, not RAG
- **Verified by** Phase 18 integration test for David Brown asserting hold is not overridden by RAG

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §14 MCP & RAG Extensions, `docs/mcp_rag_strategy.md §3.1` (three RAG pipelines), `§3.2` (document corpus) |
| **Deployment** | ChromaDB `dispute_precedents` and `historical_cases` collections at `data/chroma/`; `scripts/ingest_rag_documents.py` handles both; Phase 20 requires `--historical` flag to re-ingest from live `workflow_audit` data |
| **Observability** | `rag_retrieval_duration_ms{pipeline="dispute_precedents"}` and `{pipeline="historical_cases"}` histograms; `rag_chunks_retrieved` counters per collection; `classification_precedents` logged in Dispute Agent Loki events; Tempo: `stage2.dispute` span gains `rag.precedents_retrieved` attribute |
| **SRE** | Graceful degradation mandatory (AF-01, AF-02) — neither Dispute classification accuracy nor NBA recommendation rate SLO should be impacted if RAG collections are empty; historical cases re-ingestion (Phase 20) is a background maintenance task, not a deploy dependency |
