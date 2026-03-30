"""
Platform-wide analytics: top searches, cheapest stores, price trends.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_get, cache_set
from app.models.product import PriceListing, PriceHistory, CrawlJob, CrawlStatus
from app.telemetry.otel import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer("services.analytics")


class AnalyticsService:

    async def get_platform_stats(self, db: AsyncSession) -> dict:
        cache_key = "analytics:platform_stats"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        with tracer.start_as_current_span("analytics.platform_stats"):
            from app.models.product import Product
            product_count = (await db.execute(select(func.count(Product.id)))).scalar_one()
            listing_count = (await db.execute(select(func.count(PriceListing.id)))).scalar_one()
            crawl_count = (await db.execute(
                select(func.count(CrawlJob.id)).where(CrawlJob.status == CrawlStatus.COMPLETED)
            )).scalar_one()

            stats = {
                "total_products": product_count,
                "total_listings": listing_count,
                "completed_crawls": crawl_count,
            }
            await cache_set(cache_key, stats, ttl=120)
            return stats

    async def get_cheapest_stores(self, db: AsyncSession, limit: int = 10) -> list[dict]:
        cache_key = f"analytics:cheapest_stores:{limit}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        with tracer.start_as_current_span("analytics.cheapest_stores"):
            stmt = (
                select(
                    PriceListing.store_name,
                    PriceListing.store_domain,
                    func.avg(PriceListing.price).label("avg_price"),
                    func.count(PriceListing.id).label("listing_count"),
                )
                .where(PriceListing.is_active == True)
                .group_by(PriceListing.store_name, PriceListing.store_domain)
                .order_by(func.avg(PriceListing.price))
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.all()
            data = [
                {
                    "store_name": r.store_name,
                    "store_domain": r.store_domain,
                    "avg_price": round(float(r.avg_price), 2),
                    "listing_count": r.listing_count,
                }
                for r in rows
            ]
            await cache_set(cache_key, data, ttl=300)
            return data

    async def get_price_trend(self, db: AsyncSession, product_id: str, days: int = 30) -> list[dict]:
        cache_key = f"analytics:trend:{product_id}:{days}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(
                func.date_trunc("day", PriceHistory.recorded_at).label("day"),
                PriceHistory.store_domain,
                func.avg(PriceHistory.price).label("avg_price"),
                func.min(PriceHistory.price).label("min_price"),
            )
            .where(
                PriceHistory.product_id == product_id,
                PriceHistory.recorded_at >= since,
            )
            .group_by("day", PriceHistory.store_domain)
            .order_by("day")
        )
        result = await db.execute(stmt)
        rows = result.all()
        data = [
            {
                "day": str(r.day.date()),
                "store_domain": r.store_domain,
                "avg_price": round(float(r.avg_price), 2),
                "min_price": round(float(r.min_price), 2),
            }
            for r in rows
        ]
        await cache_set(cache_key, data, ttl=600)
        return data
