"""
Orchestrates multiple crawlers concurrently, deduplicates results,
persists to DB, and updates the price history ledger.
"""
import asyncio
import logging
import re
import unicodedata
import uuid
from datetime import datetime

from opentelemetry import trace
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawlers import SEARCH_CRAWLERS, GenericCrawler
from app.crawlers.base import ScrapedProduct
from app.models.product import Product, PriceListing, PriceHistory, Availability
from app.telemetry.otel import get_tracer, get_meter

logger = logging.getLogger(__name__)
tracer = get_tracer("services.crawler")
meter = get_meter("services.crawler")

save_duration = meter.create_histogram(
    "service.save.duration",
    description="Time to persist scraped results",
    unit="s",
)


def _normalize_name(name: str) -> str:
    """Lowercase, remove punctuation, normalize unicode for fuzzy matching."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s]", " ", name.lower())
    return re.sub(r"\s+", " ", name).strip()


def _map_availability(val: str) -> Availability:
    mapping = {
        "in_stock": Availability.IN_STOCK,
        "out_of_stock": Availability.OUT_OF_STOCK,
        "limited": Availability.LIMITED,
    }
    return mapping.get(val, Availability.UNKNOWN)


class CrawlerService:

    async def search_all_stores(self, query: str) -> list[ScrapedProduct]:
        """Run all search-capable crawlers concurrently for a query."""
        with tracer.start_as_current_span("crawler_service.search_all", attributes={"query": query}):
            tasks = []
            crawlers = []
            for CrawlerClass in SEARCH_CRAWLERS:
                c = CrawlerClass()
                crawlers.append(c)
                tasks.append(self._safe_search(c, query))

            results_nested = await asyncio.gather(*tasks)
            all_results: list[ScrapedProduct] = []
            for r in results_nested:
                all_results.extend(r)

            logger.info("Search '%s' returned %d raw results", query, len(all_results))
            return all_results

    async def scrape_urls(self, urls: list[str]) -> list[ScrapedProduct]:
        """Scrape a list of specific product URLs using the generic crawler."""
        with tracer.start_as_current_span("crawler_service.scrape_urls"):
            tasks = []
            for url in urls:
                crawler = GenericCrawler()
                tasks.append(self._safe_scrape(crawler, url))
            results = await asyncio.gather(*tasks)
            return [r for r in results if r is not None]

    async def _safe_search(self, crawler, query: str) -> list[ScrapedProduct]:
        try:
            async with crawler:
                return await crawler.search(query)
        except Exception as exc:
            logger.error("Crawler %s search failed: %s", crawler.store_name, exc)
            return []

    async def _safe_scrape(self, crawler, url: str) -> ScrapedProduct | None:
        try:
            async with crawler:
                return await crawler.scrape_product(url)
        except Exception as exc:
            logger.error("Crawl failed for %s: %s", url, exc)
            return None

    async def persist_results(self, db: AsyncSession, scraped: list[ScrapedProduct]) -> list[Product]:
        """
        Upsert products and price listings.
        Groups scraped results by normalized name to merge across stores.
        """
        import time
        start = time.monotonic()

        persisted: list[Product] = []

        # Group by normalized name
        groups: dict[str, list[ScrapedProduct]] = {}
        for item in scraped:
            key = _normalize_name(item.name)
            groups.setdefault(key, []).append(item)

        for norm_name, items in groups.items():
            with tracer.start_as_current_span("crawler_service.persist_group"):
                product = await self._upsert_product(db, items[0], norm_name)
                for item in items:
                    await self._upsert_listing(db, product, item)
                    await self._append_price_history(db, product, item)
                persisted.append(product)

        await db.flush()
        save_duration.record(time.monotonic() - start)
        return persisted

    async def _upsert_product(self, db: AsyncSession, item: ScrapedProduct, norm_name: str) -> Product:
        stmt = select(Product).where(Product.normalized_name == norm_name)
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()

        if product is None:
            product = Product(
                id=uuid.uuid4(),
                name=item.name,
                normalized_name=norm_name,
                description=item.description,
                category=item.category,
                brand=item.brand,
                image_url=item.image_url,
            )
            db.add(product)
        else:
            # Update fields if we have richer data
            if item.description and not product.description:
                product.description = item.description
            if item.brand and not product.brand:
                product.brand = item.brand
            if item.image_url and not product.image_url:
                product.image_url = item.image_url
            product.updated_at = datetime.utcnow()

        return product

    async def _upsert_listing(self, db: AsyncSession, product: Product, item: ScrapedProduct) -> None:
        stmt = select(PriceListing).where(
            PriceListing.product_id == product.id,
            PriceListing.store_domain == item.store_domain,
        )
        result = await db.execute(stmt)
        listing = result.scalar_one_or_none()

        if listing is None:
            listing = PriceListing(
                id=uuid.uuid4(),
                product_id=product.id,
                store_name=item.store_name,
                store_domain=item.store_domain,
                product_url=item.product_url,
                price=item.price,
                original_price=item.original_price,
                currency=item.currency,
                availability=_map_availability(item.availability),
                rating=item.rating,
                review_count=item.review_count,
                shipping_cost=item.shipping_cost,
                seller_name=item.seller_name,
                scraped_at=item.scraped_at,
            )
            db.add(listing)
        else:
            listing.price = item.price
            listing.original_price = item.original_price
            listing.availability = _map_availability(item.availability)
            listing.scraped_at = item.scraped_at
            listing.rating = item.rating or listing.rating
            listing.review_count = item.review_count or listing.review_count

    async def _append_price_history(self, db: AsyncSession, product: Product, item: ScrapedProduct) -> None:
        history = PriceHistory(
            id=uuid.uuid4(),
            product_id=product.id,
            store_domain=item.store_domain,
            price=item.price,
            currency=item.currency,
            recorded_at=item.scraped_at,
        )
        db.add(history)
