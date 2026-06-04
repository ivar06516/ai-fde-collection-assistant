from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    FREE_CLOUD = "free_cloud"
    LOCAL = "local"
    PREMIUM = "premium"
    HYBRID = "hybrid"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: LLMProvider = LLMProvider.FREE_CLOUD

    groq_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""

    database_url: str = "sqlite:///data/collection_assistant.db"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    streamlit_api_url: str = "http://localhost:8000"

    agent_timeout_seconds: int = 30
    agent_max_retries: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
