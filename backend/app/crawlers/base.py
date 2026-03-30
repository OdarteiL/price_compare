"""
Base crawler with rate limiting, retry logic, robots.txt compliance,
and full OpenTelemetry instrumentation.
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.telemetry.otel import get_tracer, get_meter

logger = logging.getLogger(__name__)
tracer = get_tracer("crawlers.base")
meter = get_meter("crawlers.base")

# Metrics
crawl_requests_total = meter.create_counter(
    "crawler.requests.total",
    description="Total crawl requests",
    unit="1",
)
crawl_errors_total = meter.create_counter(
    "crawler.errors.total",
    description="Total crawl errors",
    unit="1",
)
crawl_duration = meter.create_histogram(
    "crawler.request.duration",
    description="Crawl request duration",
    unit="s",
)
products_scraped = meter.create_counter(
    "crawler.products.scraped",
    description="Total products scraped",
    unit="1",
)


@dataclass
class ScrapedProduct:
    store_name: str
    store_domain: str
    product_url: str
    name: str
    price: float
    currency: str = "USD"
    original_price: float | None = None
    availability: str = "unknown"
    image_url: str | None = None
    description: str | None = None
    brand: str | None = None
    category: str | None = None
    rating: float | None = None
    review_count: int | None = None
    shipping_cost: float | None = None
    seller_name: str | None = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)


class RateLimiter:
    """Per-domain rate limiter."""

    def __init__(self, delay: float = settings.rate_limit_delay_seconds):
        self._delay = delay
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, domain: str) -> None:
        async with self._lock:
            last = self._last_request.get(domain, 0)
            elapsed = time.monotonic() - last
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
            self._last_request[domain] = time.monotonic()


class RobotsTxtChecker:
    """Async robots.txt compliance checker with caching."""

    def __init__(self):
        self._cache: dict[str, RobotFileParser] = {}

    async def can_fetch(self, session: aiohttp.ClientSession, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._cache:
            parser = RobotFileParser()
            robots_url = f"{base}/robots.txt"
            try:
                async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        parser.parse(text.splitlines())
                    else:
                        parser.allow_all = True
            except Exception:
                parser.allow_all = True
            self._cache[base] = parser
        return self._cache[base].can_fetch("*", url)


_ua = UserAgent()
_rate_limiter = RateLimiter()
_robots_checker = RobotsTxtChecker()


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent": _ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


class BaseCrawler(ABC):
    """Abstract base for all site crawlers."""

    store_name: str = ""
    store_domain: str = ""
    supports_search: bool = True

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=settings.crawler_concurrency, ssl=False)
        timeout = aiohttp.ClientTimeout(total=settings.crawler_timeout_seconds)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=_build_headers(),
        )
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    async def fetch_html(self, url: str) -> str | None:
        """Fetch HTML with rate limiting, robots.txt, and retry."""
        parsed = urlparse(url)
        domain = parsed.netloc

        # Robots.txt check
        if not await _robots_checker.can_fetch(self._session, url):
            logger.warning("robots.txt disallows fetching %s", url)
            return None

        # Rate limit
        await _rate_limiter.wait(domain)

        start = time.monotonic()
        with tracer.start_as_current_span(
            "crawler.fetch_html",
            attributes={"http.url": url, "crawler.domain": domain, "crawler.store": self.store_name},
        ) as span:
            try:
                html = await self._fetch_with_retry(url)
                duration = time.monotonic() - start
                crawl_requests_total.add(1, {"store": self.store_name, "status": "success"})
                crawl_duration.record(duration, {"store": self.store_name})
                span.set_status(Status(StatusCode.OK))
                return html
            except Exception as exc:
                duration = time.monotonic() - start
                crawl_errors_total.add(1, {"store": self.store_name, "error": type(exc).__name__})
                crawl_duration.record(duration, {"store": self.store_name})
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                logger.error("Fetch failed for %s: %s", url, exc)
                return None

    @retry(
        stop=stop_after_attempt(settings.crawler_retry_attempts),
        wait=wait_exponential(multiplier=settings.crawler_retry_delay_seconds, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def _fetch_with_retry(self, url: str) -> str:
        async with self._session.get(url, headers=_build_headers()) as resp:
            resp.raise_for_status()
            return await resp.text()

    def parse_soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    async def search(self, query: str) -> list[ScrapedProduct]:
        """Search the store for a product query."""
        ...

    @abstractmethod
    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        """Scrape a single product page."""
        ...

    def _parse_price(self, text: str) -> float | None:
        """Extract numeric price from text like '$1,234.56'."""
        import re
        if not text:
            return None
        cleaned = re.sub(r"[^\d.,]", "", text.strip())
        cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
