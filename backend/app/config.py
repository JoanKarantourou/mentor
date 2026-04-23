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

    # Azure OpenAI — embeddings
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_KEY: SecretStr | None = None
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"

    @model_validator(mode="after")
    def _require_azure_openai_fields(self) -> "Settings":
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
        return self


settings = Settings()
