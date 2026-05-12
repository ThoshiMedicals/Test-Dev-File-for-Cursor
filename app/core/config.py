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

    # Waitlist / Coming Soon — use Fernet key from `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
    waitlist_fernet_key: str | None = None
    waitlist_hmac_secret: str | None = None

    # Live headlines (https://newsapi.org/)
    news_api_key: str | None = None
    news_api_country: str = "us"
    news_api_page_size: int = 40

    # Currents API (https://currentsapi.services/) — Authorization header API key
    currents_api_key: str | None = None
    currents_language: str = "en"

    # Celery Beat: run `news.sync_all_live_news` on this interval (minutes). 0 = disabled.
    news_sync_interval_minutes: int = 0

    # Optional outbound email for alerts (SMTP). Leave host empty to skip sends.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    # CDN / edge: short cache for read-heavy JSON (Cloudflare respects Cache-Control).
    api_cache_control_seconds: int = 60


settings = Settings()

