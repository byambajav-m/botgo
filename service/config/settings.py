from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )

    GITLAB_URL: str = "https://gitlab.com"
    GITLAB_TOKEN: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "embeddinggemma:latest"
    OLLAMA_LLM_MODEL: str = "gemma3:27b"

    WEAVIATE_URL: str = "http://localhost:8888"
    WEAVIATE_API_KEY: Optional[str] = None
    WEAVIATE_COLLECTION: str = "CodeContexts"

    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str =""

    APP_NAME: str = "GitLab MR Reviewer"
    LOG_LEVEL: str = "INFO"

    LANGSMITH_TRACING: bool = True
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "BotGo"
    LANGCHAIN_TRACING_V2: bool = True

settings = Settings()