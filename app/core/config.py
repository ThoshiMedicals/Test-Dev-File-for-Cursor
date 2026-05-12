from __future__ import annotations

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "news-ai-platform"
    environment: str = "dev"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/news_ai"
    redis_url: str = "redis://localhost:6379/0"

    api_key: str | None = None

    openai_api_key: str | None = None
    openai_base_url: AnyHttpUrl | None = None
    openai_model_summarize: str = "gpt-4o-mini"
    openai_model_classify: str = "gpt-4o-mini"
    openai_model_embed: str = "text-embedding-3-small"

    hf_inference_api_key: str | None = None
    hf_sentiment_model: str = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

    retention_days_events: int = 90


settings = Settings()

