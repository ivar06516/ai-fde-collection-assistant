# LLM Provider Strategy — AI FDE Collection Assistant

## 1. Problem Statement

Using Anthropic Claude for all 7 agents in every pipeline run incurs token costs that are unnecessary for a PoC. This document defines a **provider-agnostic architecture** that defaults to zero-cost free LLMs while keeping Anthropic as an optional upgrade path for the most reasoning-intensive agent.

---

## 2. What Is Anthropic-Specific Today?

| Component | Anthropic-Specific? | Can Be Swapped? |
|---|---|---|
| Claude model IDs (`claude-sonnet-4-6`, `claude-opus-4-8`) | Yes | Yes — replace with any provider's model ID |
| Anthropic SDK MCP client wrapper | Yes | Yes — use `mcp` Python client directly (provider-agnostic) |
| Prompt caching (`cache_control` header) | Yes | Drop entirely for PoC; not needed |
| Tool use / function calling | No — standard across providers | Already abstracted by LangChain |
| Structured output (JSON) | No — all major providers support | No change needed |
| LangGraph orchestration | No | Unchanged |
| FastAPI / Streamlit / SQLite / ChromaDB | No | Unchanged |
| All 6 database tables | No | Unchanged |
| RAG pipeline (ChromaDB + sentence-transformers) | No | Unchanged |

**Conclusion:** Only the model ID and SDK client need to change. The entire pipeline architecture, agents, tools, MCP servers, RAG, and UI are model-agnostic.

---

## 3. Free Provider Comparison

| Provider | Free Tier | Best Free Model | Tool Use | Structured Output | Latency | Data Privacy |
|---|---|---|---|---|---|---|
| **Groq** | 14,400 req/day, 6,000 tokens/min | Llama 3.3 70B | ✅ Excellent | ✅ JSON mode | ⚡ Very fast (LPU) | Data sent to Groq |
| **Ollama** (local) | Unlimited (local) | Llama 3.2 3B / Phi-4 / Mistral 7B | ✅ Good (3B+) | ✅ JSON mode | 🐢 CPU-only without GPU | ✅ Stays on machine |
| **Google Gemini Flash** | 15 RPM / 1M TPM free | Gemini 1.5 Flash | ✅ Good | ✅ JSON mode | ⚡ Fast | Data sent to Google |
| **Mistral (free tier)** | Rate-limited | Mistral 7B | ⚠️ Limited | ⚠️ Variable | Medium | Data sent to Mistral |
| **HuggingFace Inference** | Rate-limited | Various | ⚠️ Variable | ⚠️ Variable | Slow | Data sent to HF |
| **Anthropic (paid)** | No free tier | Claude Opus 4.8 | ✅ Best-in-class | ✅ Best | ⚡ Fast | Data sent to Anthropic |

---

## 4. Recommended Strategy: Three-Mode Provider Config

### Mode 1 — `free_cloud` (Default for PoC demo) → Groq
- All 7 agents use **Groq Llama 3.3 70B**
- OpenAI-compatible API: minimal code change via `langchain-groq`
- 14,400 requests/day free — more than enough for demos and testing
- **Cost: $0**

### Mode 2 — `local` (Development / offline) → Ollama
- All 7 agents use local **Llama 3.2 3B** (fast on CPU) or **Llama 3.1 8B** (better quality, GPU preferred)
- Runs via `langchain-ollama`
- No internet required; data never leaves the machine
- **Cost: $0 always**

### Mode 3 — `premium` (Client demo with highest quality) → Anthropic
- NBA Agent only uses **Claude Opus 4.8** (most reasoning-intensive)
- All other agents use **Claude Sonnet 4.6**
- Keeps quality highest where it matters most
- **Cost: tokens per run (≈ $0.01–0.05 per workflow run)**

### Mode 4 — `hybrid` (Best of both) → Groq + Anthropic NBA only
- Agents 1–5 (data collection, arrears, dispute) → Groq Llama 3.3 70B
- NBA Agent only → Anthropic Claude Opus 4.8
- Audit Agent → Groq Llama 3.1 8B (or Haiku equivalent)
- **Cost reduction: ~80% vs all-Anthropic**

---

## 5. Per-Agent Model Assignment

| Agent | `free_cloud` (Groq) | `local` (Ollama) | `premium` (Anthropic) | `hybrid` |
|---|---|---|---|---|
| Orchestrator | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-opus-4-8` | `llama-3.3-70b-versatile` |
| Customer Profile | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-sonnet-4-6` | `llama-3.3-70b-versatile` |
| Account Profile | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-sonnet-4-6` | `llama-3.3-70b-versatile` |
| Arrears Prediction | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-sonnet-4-6` | `llama-3.3-70b-versatile` |
| Dispute | `llama-3.3-70b-versatile` | `llama3.2:3b` | `claude-sonnet-4-6` | `llama-3.3-70b-versatile` |
| NBA | `llama-3.3-70b-versatile` | `llama3.1:8b` | `claude-opus-4-8` | **`claude-opus-4-8`** |
| Audit | `llama-3.1-8b-instant` | `phi4:latest` | `claude-haiku-4-5-20251001` | `llama-3.1-8b-instant` |

---

## 6. Code Changes Required

### 6.1 Updated `config.py`

```python
# src/collection_assistant/config.py
from enum import Enum
from pydantic_settings import BaseSettings

class LLMProvider(str, Enum):
    FREE_CLOUD = "free_cloud"   # Groq (default)
    LOCAL = "local"             # Ollama
    PREMIUM = "premium"         # Anthropic only
    HYBRID = "hybrid"           # Groq + Anthropic NBA

class Settings(BaseSettings):
    # Provider selection
    llm_provider: LLMProvider = LLMProvider.FREE_CLOUD

    # Anthropic (premium / hybrid NBA agent only)
    anthropic_api_key: str = ""

    # Groq (free_cloud / hybrid non-NBA)
    groq_api_key: str = ""      # Free at console.groq.com

    # Ollama (local — no key needed)
    ollama_base_url: str = "http://localhost:11434"

    # Model IDs per agent per provider
    # (resolved by LLMClientFactory — no manual config needed)
    ...
```

### 6.2 `LLMClientFactory`

```python
# src/collection_assistant/llm/client_factory.py
from langchain_core.language_models import BaseChatModel
from collection_assistant.config import Settings, LLMProvider

# Model ID mapping per provider
MODEL_MAP = {
    LLMProvider.FREE_CLOUD: {
        "orchestrator":       "llama-3.3-70b-versatile",
        "customer_profile":   "llama-3.3-70b-versatile",
        "account_profile":    "llama-3.3-70b-versatile",
        "arrears_prediction": "llama-3.3-70b-versatile",
        "dispute":            "llama-3.3-70b-versatile",
        "nba":                "llama-3.3-70b-versatile",
        "audit":              "llama-3.1-8b-instant",
    },
    LLMProvider.LOCAL: {
        "orchestrator":       "llama3.2:3b",
        "customer_profile":   "llama3.2:3b",
        "account_profile":    "llama3.2:3b",
        "arrears_prediction": "llama3.2:3b",
        "dispute":            "llama3.2:3b",
        "nba":                "llama3.1:8b",
        "audit":              "phi4:latest",
    },
    LLMProvider.PREMIUM: {
        "orchestrator":       "claude-opus-4-8",
        "customer_profile":   "claude-sonnet-4-6",
        "account_profile":    "claude-sonnet-4-6",
        "arrears_prediction": "claude-sonnet-4-6",
        "dispute":            "claude-sonnet-4-6",
        "nba":                "claude-opus-4-8",
        "audit":              "claude-haiku-4-5-20251001",
    },
    LLMProvider.HYBRID: {
        "orchestrator":       "llama-3.3-70b-versatile",
        "customer_profile":   "llama-3.3-70b-versatile",
        "account_profile":    "llama-3.3-70b-versatile",
        "arrears_prediction": "llama-3.3-70b-versatile",
        "dispute":            "llama-3.3-70b-versatile",
        "nba":                "claude-opus-4-8",          # Only Anthropic call
        "audit":              "llama-3.1-8b-instant",
    },
}

def get_llm(agent_name: str, settings: Settings) -> BaseChatModel:
    model_id = MODEL_MAP[settings.llm_provider][agent_name]
    provider = settings.llm_provider

    if provider == LLMProvider.FREE_CLOUD:
        from langchain_groq import ChatGroq
        return ChatGroq(model=model_id, api_key=settings.groq_api_key, temperature=0)

    elif provider == LLMProvider.LOCAL:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_id, base_url=settings.ollama_base_url, temperature=0)

    elif provider in (LLMProvider.PREMIUM, LLMProvider.HYBRID):
        if "claude" in model_id:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=model_id, api_key=settings.anthropic_api_key, temperature=0)
        else:
            from langchain_groq import ChatGroq
            return ChatGroq(model=model_id, api_key=settings.groq_api_key, temperature=0)
```

### 6.3 Updated Agent Usage

Before (Anthropic-only):
```python
# Hard-coded to Anthropic
client = anthropic.Anthropic()
response = client.messages.create(model="claude-sonnet-4-6", ...)
```

After (provider-agnostic via LangChain):
```python
from collection_assistant.llm.client_factory import get_llm
from collection_assistant.config import get_settings

llm = get_llm("customer_profile", get_settings())
response = llm.invoke(messages)   # Works for Groq, Ollama, Anthropic
```

### 6.4 MCP With Non-Anthropic Models

The Anthropic SDK's `mcp_servers=[]` parameter only works with Anthropic. For Groq/Ollama, use the standard `mcp` Python client directly:

```python
# src/collection_assistant/mcp_servers/client.py
from mcp.client.stdio import StdioClientSession
from mcp.client.stdio import stdio_client

async def call_mcp_tool(server_script: str, tool_name: str, arguments: dict) -> dict:
    """Provider-agnostic MCP tool call."""
    async with stdio_client(["python", server_script]) as (read, write):
        async with StdioClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result.content
```

This replaces the Anthropic SDK's `mcp_servers=[]` shortcut with the standard `mcp` client — fully provider-agnostic.

---

## 7. Environment Variable Setup

### For `free_cloud` mode (Groq — default PoC):
```bash
LLM_PROVIDER=free_cloud
GROQ_API_KEY=gsk_...          # Free at console.groq.com — no credit card needed
ANTHROPIC_API_KEY=             # Leave blank
```

### For `local` mode (Ollama):
```bash
LLM_PROVIDER=local
OLLAMA_BASE_URL=http://localhost:11434
# Install: curl -fsSL https://ollama.ai/install.sh | sh
# Pull model: ollama pull llama3.2:3b
```

### For `premium` mode (Anthropic):
```bash
LLM_PROVIDER=premium
ANTHROPIC_API_KEY=sk-ant-...
```

### For `hybrid` mode:
```bash
LLM_PROVIDER=hybrid
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...   # NBA Agent only
```

---

## 8. Updated Dependencies

```toml
# pyproject.toml

[project.optional-dependencies]
# LLM provider extras — install the one you need
anthropic_provider = [
    "anthropic>=0.40.0",
    "langchain-anthropic>=0.3.0",
]
groq_provider = [
    "langchain-groq>=0.2.0",
]
ollama_provider = [
    "langchain-ollama>=0.2.0",
]

# Default PoC install (free)
poc = [
    "langchain-groq>=0.2.0",    # free_cloud mode
    "langchain-ollama>=0.2.0",  # local mode
]
```

**Install for zero-cost PoC:**
```bash
pip install -e ".[poc]"         # Groq + Ollama only — no Anthropic SDK needed
```

**Install for hybrid mode:**
```bash
pip install -e ".[poc,anthropic_provider]"
```

---

## 9. Cost Analysis

| Mode | Cost Per Workflow Run | Cost Per 100 Runs | When to Use |
|---|---|---|---|
| `free_cloud` (Groq) | $0.00 | $0.00 | Default PoC — all development, all demo dry-runs |
| `local` (Ollama) | $0.00 | $0.00 | Offline development, data-sensitive demos |
| `hybrid` (Groq + Anthropic NBA) | ~$0.01–0.02 | ~$1–2 | Live client demos where NBA quality matters |
| `premium` (All Anthropic) | ~$0.05–0.10 | ~$5–10 | Production or highest-stakes demonstrations |

---

## 10. Quality Trade-offs

| Agent | Quality on Free (Groq Llama 3.3 70B) | Risk | Mitigation |
|---|---|---|---|
| Customer Profile | ✅ Excellent — simple data retrieval + classification | Low | None needed |
| Account Profile | ✅ Excellent — structured data summarisation | Low | None needed |
| Arrears Prediction | ✅ Good — numerical analysis | Medium | Add explicit calculation instructions in system prompt |
| Dispute | ✅ Good — classification with RAG context | Low | RAG precedents compensate |
| NBA | ⚠️ Good but less nuanced than Opus | Medium-High | Use `hybrid` mode for live demos; `free_cloud` for testing |
| Audit | ✅ Excellent — structured logging, simple reasoning | Low | None needed |

**Verdict:** For PoC development and testing, `free_cloud` mode produces outputs that demonstrate the architecture correctly. For the final client demo where NBA recommendation quality is showcased, use `hybrid` mode (NBA = Anthropic Opus, everything else = Groq free).

---

## 11. Streamlit UI: Provider Indicator

Add a provider badge to the Streamlit sidebar showing which LLM is active:

```python
# ui/app.py
with st.sidebar:
    provider = settings.llm_provider
    colors = {
        "free_cloud": "🟢 Groq (Free)",
        "local":      "🟡 Ollama (Local)",
        "hybrid":     "🔵 Hybrid",
        "premium":    "🟣 Anthropic",
    }
    st.info(f"LLM Provider: **{colors[provider]}**")
```

---

## 12. Summary Recommendation

| Scenario | Recommended Mode |
|---|---|
| Local development and unit testing | `local` (Ollama Llama 3.2 3B) |
| CI/CD integration tests | `free_cloud` (Groq — fast, no hardware needed) |
| Internal FDE demo / PoC walkthrough | `free_cloud` (Groq — $0, full pipeline quality) |
| Live client demo (NBA quality critical) | `hybrid` (Groq + Anthropic NBA only) |
| Production pilot | `premium` (All Anthropic) |

**Default for this PoC: `LLM_PROVIDER=free_cloud` (Groq)** — zero cost, no credit card, full pipeline functionality.
