# UC-014: Policy RAG for NBA Recommendation

## Overview

| Field | Value |
|---|---|
| **ID** | UC-014 |
| **Actor** | System (NBA Agent — enhanced with Policy RAG pre-pass) |
| **Goal** | Before synthesising an NBA recommendation, retrieve the top 3 most relevant collection policy chunks and inject them into the NBA Agent's context so the recommendation is grounded in explicit policy documents |
| **Priority** | P1 |
| **Delivery Phase** | Phase 18 (RAG pipeline), Phase 19 (UI "Retrieved Context" panel) |
| **New Components** | `PolicyRetriever`, `HistoricalCaseRetriever`, ChromaDB `policy_docs` collection |
| **New Dependencies** | `chromadb>=0.5.0`, `sentence-transformers>=3.0.0` |

---

## Context: What Changes in the NBA Agent

**Before RAG:** NBA Agent receives only the four upstream profiles and reasons using Claude Opus 4.8's training knowledge.

**After RAG:** NBA Agent first runs a retrieval pre-pass, then injects retrieved policy chunks into the system prompt before LLM synthesis. The rationale now cites specific policy sections.

```
State (customer + account + arrears + dispute)
              │
              ▼
     RAG Query Construction
     "collection action for personal loan
      DPD 45 deteriorating high risk"
              │
              ▼
  ┌──────────────────────────────┐
  │  ChromaDB policy_docs        │
  │  all-MiniLM-L6-v2 embeddings │
  │  500-token chunks            │
  └──────────┬───────────────────┘
             │ Top 3 chunks (cosine similarity)
             ▼
  Claude Opus 4.8 synthesis
  (base state + policy context)
             │
             ▼
  NBARecommendation + retrieved_policy_chunks
```

---

## Policy Document Corpus

| Document | Key Sections | Example Chunk Retrieved |
|---|---|---|
| `collection_policy.md` | Contact windows, product-specific rules, hardship concessions, DPD escalation thresholds | "For personal loan accounts between DPD 30–60, direct phone contact is the preferred first action before escalation..." |
| `nba_action_guide.md` | Per-action guidance, expected outcomes, when to escalate | "initiate_call: Use for DPD 30–90 when customer is reachable by mobile. Expected outcome: payment arrangement in 40–70% of cases..." |
| `regulatory_compliance.md` | FDCPA principles, contact time restrictions, prohibited actions | "Contact attempts must not occur before 8am or after 9pm in the customer's timezone. Written notice required for dispute-related holds..." |

---

## Main Flow (NBA Agent Enhanced)

| Step | Action | Detail |
|---|---|---|
| 1 | **Construct RAG query** | `f"{product_type} DPD {days_past_due} {arrears_trajectory} trajectory {risk_segment} risk"` |
| 2 | **Retrieve policy chunks** | `PolicyRetriever.retrieve(query, n_results=3)` → returns `[{text, source, relevance_score}]` |
| 3 | **Retrieve similar cases** | `HistoricalCaseRetriever.retrieve(dpd, product_type, trajectory, n_results=2)` |
| 4 | **Format retrieved context** | Build markdown-formatted section: `RETRIEVED POLICY:\n{chunk1}\n{chunk2}\n{chunk3}\nSIMILAR CASES:\n{case1}\n{case2}` |
| 5 | **Inject into system prompt** | Append formatted context to base NBA system prompt |
| 6 | **LLM synthesis (Opus 4.8)** | Claude reasons over full state + policy context → produces `NBARecommendation` |
| 7 | **Attach retrieved context to output** | `nba_recommendation['retrieved_policy_chunks']` and `['retrieved_similar_cases']` added |
| 8 | **Audit Agent logs retrievals** | Retrieved chunks recorded in `workflow_audit.full_state_json` |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | ChromaDB collection empty (documents not ingested) | Skip RAG pre-pass; NBA Agent uses base prompt only; warning logged: `rag_collection_empty` |
| AF-02 | All retrieved chunks have low relevance (< 0.5) | Include chunks but add note: "Low confidence retrieval — policy context may not be directly applicable" |
| AF-03 | Embedding model fails to load | RAG pre-pass skipped; pipeline continues without retrieved context |

---

## Postconditions

- `nba_recommendation` contains two new fields: `retrieved_policy_chunks` (list of 3) and `retrieved_similar_cases` (list of 2)
- NBA rationale cites at least one policy section reference
- UI NBA card shows "Retrieved Context" expandable panel
- ChromaDB collection `policy_docs` is queried (Prometheus counter incremented)

---

## Acceptance Criteria

### AC-014-01: RAG Query Returns Non-Empty Results
- **Given** policy documents are ingested into ChromaDB `policy_docs` collection
- **When** `PolicyRetriever.retrieve("personal loan DPD 45 deteriorating high risk")` is called
- **Then** result is a list of exactly 3 chunks; each has `text` (non-empty string), `source` (filename), `relevance_score` (float 0.0–1.0)
- **Verified by** Phase 18 unit test asserting retrieval result structure

### AC-014-02: Retrieved Chunks Are Topically Relevant
- **Given** the query is "DPD 45 deteriorating trajectory initiate_call personal_loan"
- **When** retrieval runs
- **Then** at least 1 of the 3 returned chunks comes from `nba_action_guide.md` (the most directly relevant document for NBA action selection)
- **Verified by** Phase 18 unit test asserting at least 1 chunk `source == "nba_action_guide.md"`

### AC-014-03: NBA Rationale References Policy Context
- **Given** policy chunks are retrieved and injected into the NBA Agent's system prompt
- **When** Claude Opus 4.8 generates the rationale
- **Then** `nba_recommendation.rationale` contains at least one reference to retrieved context (e.g., "According to collection policy...", "Per the NBA action guide...", or a direct policy-consistent statement not derivable from the state alone)
- **Verified by** Phase 18 integration test with qualitative rationale assertion

### AC-014-04: Retrieved Context Stored in NBA Output
- **Given** a completed pipeline run with RAG enabled
- **When** `state.nba_recommendation` is inspected
- **Then** `nba_recommendation['retrieved_policy_chunks']` is a list of 3 items; `nba_recommendation['retrieved_similar_cases']` is a list of ≥ 1 item; both are present in `workflow_audit.full_state_json`
- **Verified by** Phase 18 integration test asserting new NBA output fields

### AC-014-05: UI "Retrieved Context" Panel is Visible
- **Given** a pipeline run completes with RAG-enabled NBA Agent
- **When** Screen 3 Results Dashboard renders
- **Then** the NBA Recommendation card shows an expandable "▾ Retrieved Context" section; when expanded, it shows: (1) at least 2 policy chunk snippets with source filenames and relevance scores, (2) at least 1 similar historical case
- **Verified by** Phase 19 Streamlit UI test (HTML preview: `ui/previews/preview_03_results.html`)

### AC-014-06: RAG Does Not Change NBA Action for Dispute Hold Scenario
- **Given** Sarah Jones (CUST-002) with `collection_hold = True`
- **When** RAG-enhanced NBA Agent runs
- **Then** `nba_recommendation.action = "place_on_hold"` regardless of retrieved policy context — the hard constraint overrides RAG
- **Verified by** Phase 18 integration test for Sarah Jones asserting RAG does not override hold constraint

### AC-014-07: RAG Pre-Pass Adds < 2s Latency
- **Given** ChromaDB collection with ~1,500 policy chunks (typical after 4 documents chunked at 500 tokens)
- **When** `PolicyRetriever.retrieve()` + `HistoricalCaseRetriever.retrieve()` runs
- **Then** combined retrieval time is < 2 seconds (CPU embedding + ChromaDB cosine search)
- **Verified by** Phase 18 performance test timing retrieval on typical hardware

### AC-014-08: Documents Ingested Reproducibly
- **Given** `python scripts/ingest_rag_documents.py` is run twice on the same documents
- **When** ChromaDB `policy_docs` collection is queried after each run
- **Then** collection count is identical after both runs (idempotent ingestion); duplicate chunks not created
- **Verified by** Phase 18 idempotency test

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §14 MCP & RAG Extensions, `docs/mcp_rag_strategy.md §3` RAG Architecture |
| **Deployment** | ChromaDB at `data/chroma/` on Render.com (ephemeral disk — `ingest_rag_documents.py` must run at startup alongside `seed_db.py`); `sentence-transformers` model downloaded at first startup (~90MB, cached at `~/.cache/`) |
| **Observability** | `rag_retrieval_duration_ms{pipeline="policy"}` new Prometheus histogram; `rag_chunks_retrieved{collection="policy_docs"}` counter; retrieved chunk text + scores logged in Loki at DEBUG level; `stage3.nba` Tempo span gains `rag.policy_chunks_retrieved = 3` attribute |
| **SRE** | RAG must degrade gracefully (AF-01, AF-03) — pipeline success rate SLO not impacted if RAG fails; Render ephemeral disk means ChromaDB must be re-ingested on every fresh deploy (same pattern as SQLite seed); ingest script added to deploy startup sequence |
