from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    GITLAB_URL: str = "https://gitlab.com"
    GITLAB_TOKEN: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_LLM_MODEL: str = "gemma3:27b"

    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: Optional[str] = None
    WEAVIATE_COLLECTION: str = "CodeContexts"

    APP_NAME: str = "GitLab MR Reviewer"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()