# MCP & RAG Extension Strategy — AI FDE Collection Assistant

## 1. Design Thinking: Step by Step

### Step 1 — Why MCP Here?

The current agents call Python functions directly (e.g., `get_customer_demographics` queries SQLite). This couples the agent logic to the data layer. MCP (Model Context Protocol) is Anthropic's open standard for connecting models to tools and data sources — it acts as a plug-in interface.

**The problem it solves for this PoC:** If a client wants to replace the SQLite mock with their real Salesforce CRM, every agent tool function must be rewritten. With MCP, only the MCP server changes — the agent code stays the same.

**Visual proof in the demo:** The Audit Trail shows `crm-data-server::get_customer` instead of a bare Python function call. The Streamlit sidebar shows which MCP servers are connected and live.

---

### Step 2 — Why RAG Here?

The current NBA Agent reasons over the four upstream profiles using only Claude Opus 4.8's training knowledge for policy and scoring. Three gaps exist:

| Gap | Problem | RAG Fix |
|---|---|---|
| Policy knowledge | NBA constraints are hardcoded Python rules (e.g., `if collection_hold`) | Retrieve relevant collection policy chunks before synthesis |
| No historical precedent | NBA doesn't know "in similar cases, what worked?" | Retrieve similar past cases from `workflow_audit` |
| Dispute classification | Dispute Agent classifies by LLM intuition with no reference material | Retrieve dispute resolution precedents for the classification |

**Visual proof in the demo:** The NBA Recommendation card gains a "Retrieved Context" panel showing the exact policy excerpts and similar historical cases that grounded the recommendation. This makes the AI explainable.

---

### Step 3 — Minimum Viable Stack (Zero New Infrastructure Cost)

| Component | Technology | Cost | Rationale |
|---|---|---|---|
| MCP servers | `mcp` Python SDK (stdio servers) | Free (pip package) | Runs as subprocesses; Anthropic SDK has built-in client |
| Vector store | `chromadb` (embedded, file-based) | Free | No server — like SQLite for vectors; persists to `data/chroma/` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Free (no API cost) | ~90MB model; 384-dim embeddings; fast on CPU |
| Policy documents | Synthetic markdown files in `rag/documents/` | Free | 4 documents covering policy, NBA guide, dispute guide, compliance |

All four additions require zero new cloud services and zero API costs.

---

### Step 4 — Boundaries and Scope

This is a **PoC overlay** on the existing architecture — existing agents continue to work unchanged. MCP and RAG are additive layers:
- Agents that currently call Python tools directly can optionally call MCP tools
- The NBA Agent gets a RAG pre-pass before its Opus 4.8 synthesis call
- The Dispute Agent gets a RAG lookup for dispute classification precedents

---

## 2. MCP Architecture

### 2.1 Three MCP Servers

```
┌──────────────────────────────────────────────────┐
│              Agent Process (FastAPI)              │
│                                                  │
│  Customer Profile Agent ──┐                      │
│  Account Profile Agent ───┤──► MCP Client        │
│  Dispute Agent ───────────┘    (Anthropic SDK)   │
│                                │                 │
│  NBA Agent ────────────────────┤                 │
│                                │                 │
└────────────────────────────────┼─────────────────┘
                                 │ stdio / MCP protocol
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
           ▼                     ▼                     ▼
  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐
  │  Data MCP       │  │  Policy MCP      │  │  Analytics MCP     │
  │  Server         │  │  Server          │  │  Server            │
  │  (crm-data)     │  │  (policy)        │  │  (analytics)       │
  │                 │  │                  │  │                    │
  │  Tools:         │  │  Resources:      │  │  Tools:            │
  │  get_customer   │  │  collection_     │  │  check_hold_flag   │
  │  get_account    │  │  _policy.md      │  │  eval_eligibility  │
  │  get_payments   │  │  nba_guide.md    │  │  get_similar_cases │
  │  get_disputes   │  │  dispute_guide   │  │                    │
  │  get_history    │  │  compliance.md   │  │                    │
  └─────────────────┘  └──────────────────┘  └────────────────────┘
           │                     │                     │
           ▼                     ▼                     ▼
      SQLite DB            Policy docs           workflow_audit
      (6 tables)           (markdown)             + rules engine
```

---

### 2.2 Server Definitions

#### Server 1: Data MCP Server (`src/collection_assistant/mcp_servers/data_server.py`)

Wraps all SQLite `get_*` queries that were previously direct Python tool calls.

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("crm-data")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_customer",
            description="Retrieve full customer demographics and contact preferences from the customer register.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer identifier (e.g. CUST-001)"}
                },
                "required": ["customer_id"]
            }
        ),
        Tool(
            name="get_account",
            description="Retrieve account balance, DPD, product type, and account status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account identifier (e.g. ACC-001)"}
                },
                "required": ["account_id"]
            }
        ),
        Tool(
            name="get_payment_history",
            description="Retrieve the last 18 months of payment history for an account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "months": {"type": "integer", "default": 18}
                },
                "required": ["account_id"]
            }
        ),
        Tool(
            name="get_active_disputes",
            description="Retrieve all open or under_review disputes for an account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"}
                },
                "required": ["account_id"]
            }
        ),
        Tool(
            name="get_interaction_history",
            description="Retrieve prior collection interaction history for a customer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 12}
                },
                "required": ["customer_id"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Route to SQLite query functions
    ...

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

#### Server 2: Policy MCP Server (`src/collection_assistant/mcp_servers/policy_server.py`)

Exposes collection policy documents as MCP **resources** (not tools) — the NBA and Dispute agents can read them as context.

```python
from mcp.server import Server
from mcp.types import Resource, TextContent
import pathlib

server = Server("collection-policy")
DOCS_DIR = pathlib.Path("src/collection_assistant/rag/documents")

@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(uri="policy://collection_policy", name="Collection Policy", mimeType="text/markdown"),
        Resource(uri="policy://nba_action_guide", name="NBA Action Guide", mimeType="text/markdown"),
        Resource(uri="policy://dispute_resolution_guide", name="Dispute Resolution Guide", mimeType="text/markdown"),
        Resource(uri="policy://regulatory_compliance", name="Regulatory Compliance", mimeType="text/markdown"),
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    slug = uri.replace("policy://", "")
    doc_path = DOCS_DIR / f"{slug}.md"
    return doc_path.read_text()
```

#### Server 3: Analytics MCP Server (`src/collection_assistant/mcp_servers/analytics_server.py`)

Exposes rule-based analytics tools that were previously hardcoded Python logic.

```python
server = Server("collection-analytics")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="check_collection_hold",
            description="Check if an account has an active collection hold due to a dispute.",
            inputSchema={"type": "object", "properties": {"account_id": {"type": "string"}}, "required": ["account_id"]}
        ),
        Tool(
            name="evaluate_action_eligibility",
            description="Given account status and dispute hold status, return the list of NBA actions this account is eligible for.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_status": {"type": "string"},
                    "collection_hold": {"type": "boolean"},
                    "days_past_due": {"type": "integer"}
                },
                "required": ["account_status", "collection_hold", "days_past_due"]
            }
        ),
        Tool(
            name="get_similar_historical_cases",
            description="Retrieve past workflow audit records with similar DPD range, product type, and arrears trajectory to inform NBA decision.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_past_due_range": {"type": "array", "items": {"type": "integer"}, "description": "[min, max]"},
                    "product_type": {"type": "string"},
                    "arrears_trajectory": {"type": "string"},
                    "limit": {"type": "integer", "default": 3}
                },
                "required": ["days_past_due_range", "product_type", "arrears_trajectory"]
            }
        ),
    ]
```

---

### 2.3 Connecting Agents to MCP Servers

With the Anthropic Python SDK, agents connect to MCP servers before making LLM calls:

```python
# src/collection_assistant/agents/customer_profile.py
import anthropic

client = anthropic.Anthropic()

async def run_customer_profile_agent(customer_id: str) -> CustomerProfile:
    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        mcp_servers=[
            {
                "type": "stdio",
                "command": "python",
                "args": ["src/collection_assistant/mcp_servers/data_server.py"],
            }
        ],
        tools=[],  # Tools come from MCP server
        messages=[
            {"role": "user", "content": f"Build a full customer profile for customer_id={customer_id}"}
        ],
        system="You are the Customer Profile Agent. Use the available MCP tools to retrieve customer data..."
    )
    return parse_customer_profile(response)
```

---

### 2.4 MCP Demo Value

| What the Client Sees | What It Demonstrates |
|---|---|
| Audit trail shows `crm-data::get_customer` for each tool call | Tool calls are traceable to named MCP servers — production-grade observability |
| Policy documents visible in NBA context | Extensible knowledge sources: swap `policy_server.py` to point at a real policy management system |
| Streamlit sidebar shows "MCP Servers: crm-data ✅ policy ✅ analytics ✅" | Live server health visible in UI |
| "Replace SQLite with Salesforce" narrative | MCP as the integration abstraction layer |

---

## 3. RAG Architecture

### 3.1 Three RAG Pipelines

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG Layer                                 │
│                                                             │
│  ┌─────────────────┐  ┌──────────────────┐                 │
│  │  Policy RAG     │  │  Historical      │                 │
│  │  Pipeline       │  │  Case RAG        │                 │
│  │  (NBA Agent)    │  │  Pipeline        │                 │
│  │                 │  │  (NBA Agent)     │                 │
│  │  Query: profile │  │  Query: DPD +    │                 │
│  │  + trajectory   │  │  product +       │                 │
│  │                 │  │  trajectory      │                 │
│  └───────┬─────────┘  └──────┬───────────┘                 │
│          │                   │                             │
│          └──────────┬────────┘                             │
│                     │                                       │
│                     ▼                                       │
│            ChromaDB (embedded)                              │
│            data/chroma/                                     │
│            ├── collection: policy_docs                      │
│            └── collection: historical_cases                 │
│                     │                                       │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Sentence Transformer: all-MiniLM-L6-v2              │  │
│  │  (384-dim embeddings, CPU-only, free)                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────┐                                        │
│  │  Dispute RAG    │                                        │
│  │  Pipeline       │                                        │
│  │  (Dispute Agent)│                                        │
│  │                 │                                        │
│  │  Query: dispute │                                        │
│  │  description    │                                        │
│  └───────┬─────────┘                                        │
│          │                                                  │
│          ▼                                                  │
│  ChromaDB: collection: dispute_precedents                   │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.2 Document Corpus

All documents are stored as markdown in `src/collection_assistant/rag/documents/`. Chunks of 500 tokens with 50-token overlap.

| File | Contents | Used By |
|---|---|---|
| `collection_policy.md` | Approved collection actions, contact windows, hardship concessions, product-specific rules | NBA Agent Policy RAG |
| `nba_action_guide.md` | Detailed guidance for each of the 9 NBA actions: when to use, expected outcomes, escalation triggers | NBA Agent Policy RAG |
| `dispute_resolution_guide.md` | Dispute classification criteria, 5-type taxonomy with examples, resolution timelines, hold conditions | Dispute Agent Dispute RAG |
| `regulatory_compliance.md` | FDCPA/TCPA principles, prohibited contact windows, required disclosures, jurisdiction notes | NBA Agent Policy RAG |

Historical cases are seeded from `workflow_audit` table records — after ~20 runs, realistic precedents are available. For Phase 1 of the PoC, 50 synthetic historical cases are pre-seeded.

---

### 3.3 ChromaDB Setup

```python
# src/collection_assistant/rag/vectorstore.py
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

def get_chroma_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path="data/chroma")

def get_embedding_function():
    return SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

def get_collection(name: str) -> chromadb.Collection:
    client = get_chroma_client()
    ef = get_embedding_function()
    return client.get_or_create_collection(name=name, embedding_function=ef)
```

---

### 3.4 Document Ingestion Pipeline

```python
# scripts/ingest_rag_documents.py
"""
Usage:
  python scripts/ingest_rag_documents.py              # Ingest policy documents
  python scripts/ingest_rag_documents.py --historical  # Ingest historical cases from workflow_audit
"""
import pathlib
from collection_assistant.rag.vectorstore import get_collection
from collection_assistant.rag.chunker import chunk_markdown  # 500-token chunks, 50-token overlap

DOCS_DIR = pathlib.Path("src/collection_assistant/rag/documents")

def ingest_policy_documents():
    collection = get_collection("policy_docs")
    for doc_path in DOCS_DIR.glob("*.md"):
        text = doc_path.read_text()
        chunks = chunk_markdown(text, chunk_size=500, overlap=50)
        collection.add(
            documents=chunks,
            ids=[f"{doc_path.stem}_{i}" for i in range(len(chunks))],
            metadatas=[{"source": doc_path.name, "chunk": i} for i in range(len(chunks))]
        )
    print(f"Ingested {collection.count()} policy chunks")

def ingest_historical_cases():
    from collection_assistant.db.queries.audit_queries import get_completed_workflows
    collection = get_collection("historical_cases")
    cases = get_completed_workflows(limit=200)
    for case in cases:
        summary = f"Customer DPD {case.account_dpd}, {case.product_type}, " \
                  f"{case.arrears_trajectory} trajectory, NBA action: {case.nba_action}, " \
                  f"confidence: {case.nba_confidence:.2f}. Rationale: {case.nba_rationale}"
        collection.add(
            documents=[summary],
            ids=[case.workflow_id],
            metadatas={"dpd": case.account_dpd, "product_type": case.product_type,
                       "trajectory": case.arrears_trajectory, "nba_action": case.nba_action}
        )
    print(f"Ingested {collection.count()} historical cases")
```

---

### 3.5 Retriever

```python
# src/collection_assistant/rag/retriever.py
from collection_assistant.rag.vectorstore import get_collection

class PolicyRetriever:
    def __init__(self):
        self.collection = get_collection("policy_docs")

    def retrieve(self, query: str, n_results: int = 3) -> list[dict]:
        results = self.collection.query(query_texts=[query], n_results=n_results)
        return [
            {
                "text": doc,
                "source": meta["source"],
                "relevance_score": 1 - dist,  # ChromaDB returns distances
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]


class HistoricalCaseRetriever:
    def __init__(self):
        self.collection = get_collection("historical_cases")

    def retrieve(self, days_past_due: int, product_type: str,
                 arrears_trajectory: str, n_results: int = 2) -> list[dict]:
        query = f"DPD {days_past_due} {product_type} {arrears_trajectory} trajectory collection"
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"trajectory": arrears_trajectory}  # Metadata filter
        )
        return [
            {"text": doc, "nba_action": meta["nba_action"], "relevance_score": 1 - dist}
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]


class DisputeRetriever:
    def __init__(self):
        self.collection = get_collection("dispute_precedents")

    def retrieve(self, dispute_description: str, n_results: int = 2) -> list[dict]:
        results = self.collection.query(query_texts=[dispute_description], n_results=n_results)
        return [
            {"text": doc, "source": meta["source"], "relevance_score": 1 - dist}
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]
```

---

### 3.6 NBA Agent Enhancement (RAG Pre-Pass)

```python
# src/collection_assistant/agents/nba.py  (enhanced)
from collection_assistant.rag.retriever import PolicyRetriever, HistoricalCaseRetriever

policy_retriever = PolicyRetriever()
case_retriever = HistoricalCaseRetriever()

async def run_nba_agent(state: CollectionWorkflowState) -> NBARecommendation:

    # ── RAG Pre-Pass ─────────────────────────────────────────────────────────
    rag_query = (
        f"collection action for {state['account_profile']['product_type']} "
        f"DPD {state['account_profile']['days_past_due']} "
        f"{state['arrears_prediction']['arrears_trajectory']} trajectory "
        f"{state['customer_profile']['risk_segment']} risk segment"
    )

    policy_chunks = policy_retriever.retrieve(rag_query, n_results=3)
    similar_cases = case_retriever.retrieve(
        days_past_due=state['account_profile']['days_past_due'],
        product_type=state['account_profile']['product_type'],
        arrears_trajectory=state['arrears_prediction']['arrears_trajectory'],
        n_results=2
    )

    # ── Inject retrieved context into system prompt ───────────────────────────
    retrieved_context = format_retrieved_context(policy_chunks, similar_cases)

    enhanced_system_prompt = f"""
{BASE_NBA_SYSTEM_PROMPT}

---
RETRIEVED POLICY CONTEXT (from collection_policy and nba_action_guide):
{retrieved_context['policy']}

SIMILAR HISTORICAL CASES:
{retrieved_context['cases']}
---
Use the above context to inform your recommendation. Cite the relevant policy when explaining your rationale.
"""

    # ── LLM synthesis (Opus 4.8) ──────────────────────────────────────────────
    response = client.messages.create(
        model="claude-opus-4-8",
        system=enhanced_system_prompt,
        messages=[{"role": "user", "content": format_state_for_nba(state)}],
    )

    nba = parse_nba_response(response)

    # ── Attach retrieved context to NBA output (for UI display) ──────────────
    nba['retrieved_policy_chunks'] = policy_chunks   # New field
    nba['retrieved_similar_cases'] = similar_cases   # New field

    return nba
```

---

### 3.7 UI: "Retrieved Context" Panel in NBA Card

A new expandable section is added to the NBA Recommendation card in Screen 3:

```
┌══════════════ NEXT BEST ACTION ════════════════╗
║  ★ INITIATE CALL — Mobile — 87% confidence     ║
║                                                 ║
║  Rationale: "DPD 45 with deteriorating...      ║
║  Policy §3.2 supports direct contact for       ║
║  accounts between 30–60 DPD..."                ║
║                                                 ║
║  ▾ Retrieved Context (3 policy + 2 cases)      ║
║  ├─ 📄 nba_action_guide.md §2.1 (0.91)         ║
║  │     "initiate_call: appropriate for DPD     ║
║  │      30–90 when customer is reachable..."   ║
║  ├─ 📄 collection_policy.md §4 (0.88)          ║
║  │     "For high-risk customers, direct        ║
║  │      phone contact should be attempted..."  ║
║  ├─ 📋 Similar Case: wf-prev-001 (0.85)        ║
║  │     "DPD 48, personal loan, deteriorating   ║
║  │      → initiate_call, conf 0.83"            ║
╚══════════════════════════════════════════════════╝
```

---

## 4. Combined Enhanced Architecture

```
Input: customer_id + account_id
         │
         ▼
 ┌────────────────────────────┐
 │     Orchestrator Agent     │
 └────────────┬───────────────┘
              │
  ── STAGE 1: parallel ──────────────────────────────
   ┌──────────┴──────────┐
   ▼                     ▼
Customer Profile      Account Profile
Agent                 Agent
[MCP: crm-data]       [MCP: crm-data]
              │
  ── STAGE 2: parallel ──────────────────────────────
   ┌──────────┴──────────┐
   ▼                     ▼
Arrears Prediction    Dispute Agent
Agent                 [MCP: crm-data]
                      [RAG: dispute_precedents]
              │
  ── STAGE 3: sequential ────────────────────────────
              ▼
           NBA Agent
           [MCP: policy-server, analytics-server]
           [RAG: policy_docs → Top 3 chunks     ]
           [RAG: historical_cases → Top 2 cases ]
           [LLM: Claude Opus 4.8               ]
              │
              ▼
           Audit Agent
           [Logs MCP server calls + RAG retrievals]
```

---

## 5. New Dependencies

```
# MCP
mcp>=1.0.0                    # MCP server + client SDK (Anthropic's open protocol)

# RAG / Vector Store
chromadb>=0.5.0               # Embedded vector store (no server, file-based)
sentence-transformers>=3.0.0  # all-MiniLM-L6-v2 embeddings (CPU, free)
```

**Added to pyproject.toml extras:**
```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0.0"]
rag = ["chromadb>=0.5.0", "sentence-transformers>=3.0.0"]
```

---

## 6. Updated Project Structure

```
src/collection_assistant/
├── mcp_servers/
│   ├── __init__.py
│   ├── data_server.py          # CRM + banking + disputes (wraps SQLite queries)
│   ├── policy_server.py        # Policy docs as MCP resources
│   └── analytics_server.py    # Hold checks, eligibility rules, similar-case lookup
│
├── rag/
│   ├── __init__.py
│   ├── vectorstore.py          # ChromaDB client factory
│   ├── retriever.py            # PolicyRetriever, HistoricalCaseRetriever, DisputeRetriever
│   ├── ingester.py             # Document chunking + embedding pipeline
│   ├── chunker.py              # Markdown-aware text splitter (500 tokens, 50 overlap)
│   └── documents/              # Source policy documents
│       ├── collection_policy.md
│       ├── nba_action_guide.md
│       ├── dispute_resolution_guide.md
│       └── regulatory_compliance.md
│
data/
├── collection_assistant.db     # SQLite DB
└── chroma/                     # ChromaDB persistent store
    ├── policy_docs/
    ├── historical_cases/
    └── dispute_precedents/

scripts/
├── seed_db.py
├── reset_db.py
└── ingest_rag_documents.py     # NEW: chunk + embed policy docs + historical cases
```

---

## 7. Implementation Phases

| Phase | Deliverable | Priority |
|---|---|---|
| Phase 16 | MCP Data Server — wraps 5 existing SQLite tools; Customer Profile + Account Profile agents migrated to use MCP client | P1 |
| Phase 17 | MCP Policy Server + Analytics Server — policy docs as resources; hold checks + eligibility as analytics tools; Dispute + NBA agents migrated | P1 |
| Phase 18 | RAG pipeline — ChromaDB setup, document ingestion, Policy Retriever + Historical Case Retriever wired into NBA Agent; Dispute Retriever wired into Dispute Agent | P1 |
| Phase 19 | UI: "Retrieved Context" panel in NBA card (expandable); MCP server status in Streamlit sidebar; RAG retrievals in Audit Trail | P2 |
| Phase 20 | Historical case ingestion from `workflow_audit`; after 20 real runs, switch from synthetic seeds to real precedents | P2 |

---

## 8. Demo Narrative

**MCP story:** "Today, agents query a local SQLite database. With MCP, the data server is the only thing that changes when we connect to your real Salesforce CRM — the agents, the NBA logic, the UI — none of it changes."

**RAG story:** "The NBA recommendation is no longer just Claude's reasoning over raw numbers. It's grounded in your actual collection policy documents and informed by what worked in similar past cases. You can see exactly what was retrieved and why it influenced the recommendation — full explainability."

**Combined story:** "This is the architecture pattern for production-grade agentic AI in financial services: standardised tool integration via MCP, knowledge-grounded decisions via RAG, and full observability across both."
