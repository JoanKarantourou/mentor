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


settings = Settings()
