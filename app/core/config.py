from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://aiqa:aiqa_dev_only@localhost:5432/aiqa"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 60
    llm_provider: str = "groq"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    llm_timeout_seconds: float = 30
    llm_max_retries: int = 2
    llm_fallback_enabled: bool = False
    fallback_provider: str = ""
    fallback_api_key: str = ""
    fallback_model: str = "openai/gpt-oss-20b"
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    redis_fail_mode: str = "open"
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if value and len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        return value

    @field_validator("redis_fail_mode")
    @classmethod
    def validate_redis_mode(cls, value: str) -> str:
        if value not in {"open", "closed"}:
            raise ValueError("REDIS_FAIL_MODE must be 'open' or 'closed'")
        return value

    @field_validator("llm_provider", "fallback_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if value and value not in {"openai", "groq"}:
            raise ValueError("LLM providers currently supported are 'groq' and 'openai'")
        return value

    @model_validator(mode="after")
    def require_production_secret(self):
        if self.app_env.lower() in {"production", "prod"} and (
            len(self.jwt_secret_key) < 32 or "replace-with" in self.jwt_secret_key.lower()
        ):
            raise ValueError(
                "Production requires a unique JWT_SECRET_KEY of at least 32 characters"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
