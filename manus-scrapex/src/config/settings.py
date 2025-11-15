"""
Application configuration settings
"""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "manus-scrapex"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_secret_key: str = Field(default="change-this-secret-key-in-production")

    # LLM Services
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "scrapex"
    postgres_password: str = "scrapex_password"
    postgres_db: str = "scrapex_db"

    @property
    def postgres_url(self) -> str:
        """PostgreSQL connection URL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # MongoDB
    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_user: str = "scrapex"
    mongodb_password: str = "scrapex_password"
    mongodb_db: str = "scrapex_db"

    @property
    def mongodb_url(self) -> str:
        """MongoDB connection URL"""
        return (
            f"mongodb://{self.mongodb_user}:{self.mongodb_password}"
            f"@{self.mongodb_host}:{self.mongodb_port}/{self.mongodb_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    @property
    def redis_url(self) -> str:
        """Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Celery
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    @property
    def broker_url(self) -> str:
        """Celery broker URL"""
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        """Celery result backend URL"""
        return self.celery_result_backend or self.redis_url

    # Proxy Services
    proxy_service_enabled: bool = False
    proxy_service_api_key: Optional[str] = None
    proxy_service_url: Optional[str] = None
    proxy_list: Optional[str] = None

    # CAPTCHA Solving
    captcha_service_enabled: bool = False
    captcha_service_api_key: Optional[str] = None
    captcha_service_url: Optional[str] = None

    # Monitoring
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "development"
    prometheus_port: int = 9090

    # Feature Flags
    feature_deepseek_primary: bool = True
    feature_gpt4_fallback: bool = True
    feature_vision_extraction: bool = False
    feature_self_healing: bool = True
    feature_batch_processing: bool = True

    # Performance
    max_concurrent_requests: int = 100
    request_timeout: int = 30
    browser_pool_size: int = 10
    cache_ttl: int = 3600

    # Scraping Limits
    max_retries: int = 3
    retry_delay: int = 2
    rate_limit_per_domain: int = 10

    # ML Models
    ml_model_path: str = "./models"
    dispatcher_model: str = "dispatcher_model.pkl"


# Global settings instance
settings = Settings()
