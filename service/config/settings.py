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
    LLM_MODEL: str = ""

    APP_NAME: str = "BotGo"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "GitLab MR Reviewer"

    LAMINAR_BASE_URL: str = "http://localhost"
    LAMINAR_HTTP_PORT: int = 8000
    LAMINAR_GRPC_PORT: int = 8001
    LAMINAR_PROJECT_API_KEY: str = "y8RPCDg22GxxlCYBwFjHKO9MD6FiBn36b6RG7AKeQgiysjnkmlDVvIZsBVGQlf8b"


    MONGO_URI:str = "mongodb://localhost:27017"
    MONGO_DB_NAME:str = "botgo"

settings = Settings()