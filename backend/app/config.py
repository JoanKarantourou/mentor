from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@db:5432/mentor"
    LLM_PROVIDER: str = "stub"
    EMBEDDING_PROVIDER: str = "stub"
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "dev"

    BLOB_STORE: str = "local"
    BLOB_STORE_ROOT: str = "/data/blobs"

    TEST_DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@db:5432/mentor_test"

    CHUNK_TARGET_TOKENS: int = 512
    CHUNK_OVERLAP_TOKENS: int = 64
    EMBEDDING_BATCH_SIZE: int = 50
    EMBEDDING_MAX_RETRIES: int = 5

    # OpenAI (direct API — embeddings)
    OPENAI_API_KEY: SecretStr | None = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Anthropic (chat / generation)
    ANTHROPIC_API_KEY: SecretStr | None = None
    ANTHROPIC_DEFAULT_MODEL: str = "claude-haiku-4-5"
    ANTHROPIC_STRONG_MODEL: str = "claude-sonnet-4-5"

    # Retrieval / confidence
    RETRIEVAL_TOP_K: int = 8
    RETRIEVAL_MIN_TOP_SIMILARITY: float = 0.25
    RETRIEVAL_MIN_AVG_SIMILARITY: float = 0.20
    RETRIEVAL_AVG_WINDOW: int = 5

    # Chat
    CHAT_MAX_CONTEXT_CHUNKS: int = 8
    CHAT_MAX_OUTPUT_TOKENS: int = 2048

    # Azure OpenAI — embeddings
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_KEY: SecretStr | None = None
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"

    # Web search
    WEB_SEARCH_PROVIDER: Literal["stub", "tavily"] = "stub"
    TAVILY_API_KEY: SecretStr | None = None
    TAVILY_SEARCH_DEPTH: Literal["basic", "advanced"] = "basic"
    WEB_SEARCH_MAX_RESULTS: int = 5

    # Upload limits
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

    @model_validator(mode="after")
    def _require_provider_credentials(self) -> "Settings":
        if self.LLM_PROVIDER == "anthropic":
            if self.ANTHROPIC_API_KEY is None:
                raise ValueError("LLM_PROVIDER=anthropic requires: ANTHROPIC_API_KEY")
        if self.EMBEDDING_PROVIDER == "openai":
            if self.OPENAI_API_KEY is None:
                raise ValueError("EMBEDDING_PROVIDER=openai requires: OPENAI_API_KEY")
        if self.EMBEDDING_PROVIDER == "azure_openai":
            missing = [
                name
                for name, val in [
                    ("AZURE_OPENAI_ENDPOINT", self.AZURE_OPENAI_ENDPOINT),
                    ("AZURE_OPENAI_API_KEY", self.AZURE_OPENAI_API_KEY),
                    ("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", self.AZURE_OPENAI_EMBEDDING_DEPLOYMENT),
                ]
                if val is None
            ]
            if missing:
                raise ValueError(
                    f"EMBEDDING_PROVIDER=azure_openai requires: {', '.join(missing)}"
                )
        if self.WEB_SEARCH_PROVIDER == "tavily":
            if self.TAVILY_API_KEY is None:
                raise ValueError("WEB_SEARCH_PROVIDER=tavily requires: TAVILY_API_KEY")
        return self


settings = Settings()
