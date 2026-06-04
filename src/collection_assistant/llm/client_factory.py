from langchain_core.language_models import BaseChatModel

from collection_assistant.config import LLMProvider, Settings

MODEL_MAP: dict[LLMProvider, dict[str, str]] = {
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
    # premium / hybrid: future upgrade paths — not active for PoC
    # Add Anthropic model IDs here when upgrading beyond free_cloud
    LLMProvider.PREMIUM: {
        "orchestrator":       "llama-3.3-70b-versatile",
        "customer_profile":   "llama-3.3-70b-versatile",
        "account_profile":    "llama-3.3-70b-versatile",
        "arrears_prediction": "llama-3.3-70b-versatile",
        "dispute":            "llama-3.3-70b-versatile",
        "nba":                "llama-3.3-70b-versatile",
        "audit":              "llama-3.1-8b-instant",
    },
    LLMProvider.HYBRID: {
        "orchestrator":       "llama-3.3-70b-versatile",
        "customer_profile":   "llama-3.3-70b-versatile",
        "account_profile":    "llama-3.3-70b-versatile",
        "arrears_prediction": "llama-3.3-70b-versatile",
        "dispute":            "llama-3.3-70b-versatile",
        "nba":                "llama-3.3-70b-versatile",
        "audit":              "llama-3.1-8b-instant",
    },
}


def get_llm(agent_name: str, settings: Settings) -> BaseChatModel:
    model_id = MODEL_MAP[settings.llm_provider][agent_name]
    provider = settings.llm_provider

    if provider == LLMProvider.FREE_CLOUD:
        from langchain_groq import ChatGroq
        return ChatGroq(model=model_id, api_key=settings.groq_api_key, temperature=0)

    if provider == LLMProvider.LOCAL:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_id, base_url=settings.ollama_base_url, temperature=0)

    # premium or hybrid
    # Groq handles all modes in PoC (premium/hybrid are future upgrade paths)
    from langchain_groq import ChatGroq
    return ChatGroq(model=model_id, api_key=settings.groq_api_key, temperature=0)
