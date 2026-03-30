"""
Price comparison and analysis logic.
"""
import logging
import statistics
import uuid

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis import cache_get, cache_set
from app.core.config import settings
from app.models.product import Product, PriceListing, PriceHistory, Availability
from app.schemas.product import PriceAnalysis, PriceListingOut, PriceHistoryPoint, ProductSummary
from app.telemetry.otel import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer("services.comparison")


class ComparisonService:

    async def search_products(self, db: AsyncSession, query: str, max_results: int = 20) -> list[ProductSummary]:
        cache_key = f"search:{query.lower()}:{max_results}"
        cached = await cache_get(cache_key)
        if cached:
            return [ProductSummary(**item) for item in cached]

        with tracer.start_as_current_span("comparison.search", attributes={"query": query}):
            stmt = (
                select(Product)
                .where(Product.normalized_name.ilike(f"%{query.lower()}%"))
                .options(selectinload(Product.listings))
                .limit(max_results)
            )
            result = await db.execute(stmt)
            products = result.scalars().all()

            summaries = []
            for p in products:
                active_listings = [l for l in p.listings if l.is_active]
                if not active_listings:
                    continue
                best = min(active_listings, key=lambda l: l.price)
                summaries.append(ProductSummary(
                    id=p.id,
                    name=p.name,
                    brand=p.brand,
                    image_url=p.image_url,
                    best_price=best.price,
                    best_price_store=best.store_name,
                    currency=best.currency,
                    listing_count=len(active_listings),
                ))

            await cache_set(cache_key, [s.model_dump() for s in summaries], ttl=settings.cache_ttl_seconds)
            return summaries

    async def get_analysis(self, db: AsyncSession, product_id: uuid.UUID) -> PriceAnalysis | None:
        cache_key = f"analysis:{product_id}"
        cached = await cache_get(cache_key)
        if cached:
            return PriceAnalysis(**cached)

        with tracer.start_as_current_span("comparison.analyze", attributes={"product_id": str(product_id)}):
            stmt = (
                select(Product)
                .where(Product.id == product_id)
                .options(
                    selectinload(Product.listings),
                    selectinload(Product.price_history),
                )
            )
            result = await db.execute(stmt)
            product = result.scalar_one_or_none()
            if not product:
                return None

            active_listings = [l for l in product.listings if l.is_active]
            if not active_listings:
                return None

            prices = [l.price for l in active_listings]
            best = min(active_listings, key=lambda l: l.price)
            worst = max(active_listings, key=lambda l: l.price)

            # Price history — last 30 days, ordered chronologically
            history_stmt = (
                select(PriceHistory)
                .where(PriceHistory.product_id == product_id)
                .order_by(PriceHistory.recorded_at)
            )
            history_result = await db.execute(history_stmt)
            history = history_result.scalars().all()

            analysis = PriceAnalysis(
                product_id=product.id,
                product_name=product.name,
                lowest_price=min(prices),
                highest_price=max(prices),
                average_price=round(statistics.mean(prices), 2),
                median_price=round(statistics.median(prices), 2),
                best_deal=PriceListingOut.model_validate(best),
                savings_vs_highest=round(worst.price - best.price, 2),
                savings_percent=round((1 - best.price / worst.price) * 100, 1) if worst.price > 0 else 0,
                listings=[PriceListingOut.model_validate(l) for l in sorted(active_listings, key=lambda l: l.price)],
                price_history=[PriceHistoryPoint.model_validate(h) for h in history],
                in_stock_count=sum(1 for l in active_listings if l.availability == Availability.IN_STOCK),
                total_listing_count=len(active_listings),
            )

            await cache_set(cache_key, analysis.model_dump(), ttl=settings.price_cache_ttl_seconds)
            return analysis

    async def get_product_with_listings(self, db: AsyncSession, product_id: uuid.UUID) -> Product | None:
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.listings))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
