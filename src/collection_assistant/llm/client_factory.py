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
    LLMProvider.PREMIUM: {
        "orchestrator":       "claude-sonnet-4-6",
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
        "nba":                "claude-opus-4-8",
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
    if "claude" in model_id:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model_id, api_key=settings.anthropic_api_key, temperature=0)

    from langchain_groq import ChatGroq
    return ChatGroq(model=model_id, api_key=settings.groq_api_key, temperature=0)
