from celery import Celery
from opentelemetry.instrumentation.celery import CeleryInstrumentor

from app.core.config import settings

celery_app = Celery(
    "pricecompare",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # Fair distribution for long-running crawl tasks
    task_routes={
        "app.workers.tasks.crawl_query": {"queue": "crawl"},
        "app.workers.tasks.crawl_urls": {"queue": "crawl"},
        "app.workers.tasks.refresh_stale_prices": {"queue": "maintenance"},
    },
    beat_schedule={
        "refresh-stale-prices": {
            "task": "app.workers.tasks.refresh_stale_prices",
            "schedule": 3600.0,  # every hour
        },
    },
)

CeleryInstrumentor().instrument()
