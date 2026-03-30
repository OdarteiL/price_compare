from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "PriceCompare"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/pricecompare"
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://redis:6379/0"
    cache_ttl_seconds: int = 300  # 5 minutes
    price_cache_ttl_seconds: int = 1800  # 30 minutes

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # Crawler
    crawler_concurrency: int = 10
    crawler_timeout_seconds: int = 30
    crawler_retry_attempts: int = 3
    crawler_retry_delay_seconds: float = 2.0
    max_pages_per_domain: int = 5
    rate_limit_delay_seconds: float = 1.5

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "pricecompare-api"
    otel_environment: str = "development"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://frontend:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
