"""
Celery tasks for background crawling and price maintenance.
"""
import asyncio
import logging
import uuid
from datetime import datetime

from celery import shared_task
from opentelemetry import trace

from app.core.config import settings
from app.telemetry.otel import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer("workers.tasks")


def _run_async(coro):
    """Run an async coroutine in a Celery (sync) task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="app.workers.tasks.crawl_query",
    max_retries=2,
    default_retry_delay=30,
    time_limit=300,
    soft_time_limit=270,
)
def crawl_query(self, job_id: str, query: str):
    """Crawl all supported stores for a keyword query, persist results."""
    return _run_async(_crawl_query_async(self, job_id, query))


@shared_task(
    bind=True,
    name="app.workers.tasks.crawl_urls",
    max_retries=2,
    default_retry_delay=30,
    time_limit=300,
    soft_time_limit=270,
)
def crawl_urls(self, job_id: str, query: str, urls: list[str]):
    """Crawl specific product URLs, persist results."""
    return _run_async(_crawl_urls_async(self, job_id, query, urls))


@shared_task(name="app.workers.tasks.refresh_stale_prices")
def refresh_stale_prices():
    """Periodic task: re-crawl products not updated in the last hour."""
    return _run_async(_refresh_stale_prices_async())


async def _crawl_query_async(task, job_id: str, query: str):
    from app.core.database import AsyncSessionLocal
    from app.models.product import CrawlJob, CrawlStatus
    from app.services.crawler_service import CrawlerService
    from sqlalchemy import select

    with tracer.start_as_current_span("task.crawl_query", attributes={"job_id": job_id, "query": query}):
        async with AsyncSessionLocal() as db:
            # Mark job in-progress
            result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = CrawlStatus.IN_PROGRESS
                job.celery_task_id = task.request.id
                await db.commit()

            try:
                service = CrawlerService()
                scraped = await service.search_all_stores(query)
                products = await service.persist_results(db, scraped)
                await db.commit()

                if job:
                    job.status = CrawlStatus.COMPLETED
                    job.results_count = len(products)
                    job.completed_at = datetime.utcnow()
                    await db.commit()

                logger.info("Crawl job %s completed: %d products", job_id, len(products))
                return {"status": "completed", "results": len(products)}

            except Exception as exc:
                logger.exception("Crawl job %s failed: %s", job_id, exc)
                if job:
                    job.status = CrawlStatus.FAILED
                    job.error_message = str(exc)
                    job.completed_at = datetime.utcnow()
                    await db.commit()
                raise task.retry(exc=exc)


async def _crawl_urls_async(task, job_id: str, query: str, urls: list[str]):
    from app.core.database import AsyncSessionLocal
    from app.models.product import CrawlJob, CrawlStatus
    from app.services.crawler_service import CrawlerService
    from sqlalchemy import select

    with tracer.start_as_current_span("task.crawl_urls", attributes={"job_id": job_id}):
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = CrawlStatus.IN_PROGRESS
                job.celery_task_id = task.request.id
                await db.commit()

            try:
                service = CrawlerService()
                scraped = await service.scrape_urls(urls)
                products = await service.persist_results(db, scraped)
                await db.commit()

                if job:
                    job.status = CrawlStatus.COMPLETED
                    job.results_count = len(products)
                    job.completed_at = datetime.utcnow()
                    await db.commit()

                return {"status": "completed", "results": len(products)}

            except Exception as exc:
                logger.exception("URL crawl job %s failed: %s", job_id, exc)
                if job:
                    job.status = CrawlStatus.FAILED
                    job.error_message = str(exc)
                    job.completed_at = datetime.utcnow()
                    await db.commit()
                raise task.retry(exc=exc)


async def _refresh_stale_prices_async():
    from app.core.database import AsyncSessionLocal
    from app.models.product import Product, PriceListing
    from app.services.crawler_service import CrawlerService
    from sqlalchemy import select
    from datetime import timedelta

    stale_threshold = datetime.utcnow() - timedelta(hours=1)

    async with AsyncSessionLocal() as db:
        stmt = (
            select(PriceListing.product_url, PriceListing.store_domain)
            .where(PriceListing.scraped_at < stale_threshold)
            .limit(50)
        )
        result = await db.execute(stmt)
        stale = result.all()

        if not stale:
            return {"refreshed": 0}

        urls = [row.product_url for row in stale]
        service = CrawlerService()
        scraped = await service.scrape_urls(urls)
        await service.persist_results(db, scraped)
        await db.commit()

        logger.info("Refreshed %d stale prices", len(scraped))
        return {"refreshed": len(scraped)}
