# Building a Scalable E-Commerce Price Comparison Web Scraper
## A Complete Step-by-Step Guide

---

## Table of Contents

1. [How It Works — The Big Picture](#1-how-it-works)
2. [Technology Choices and Why](#2-technology-choices)
3. [Project Structure](#3-project-structure)
4. [Phase 1 — Backend Foundation](#4-phase-1-backend-foundation)
5. [Phase 2 — The Web Scraper](#5-phase-2-the-web-scraper)
6. [Phase 3 — Background Jobs (Celery)](#6-phase-3-background-jobs)
7. [Phase 4 — The REST API](#7-phase-4-the-rest-api)
8. [Phase 5 — The Frontend](#8-phase-5-the-frontend)
9. [Phase 6 — Observability (OpenTelemetry)](#9-phase-6-observability)
10. [Phase 7 — Docker and Deployment](#10-phase-7-docker)
11. [Scalability Patterns](#11-scalability-patterns)
12. [Common Problems and How to Solve Them](#12-common-problems)
13. [How to Extend This Project](#13-how-to-extend)

---

## 1. How It Works — The Big Picture

Before writing a single line of code, understand the full data flow:

```
User types "iPhone 16"
        │
        ▼
  [Next.js Frontend]
  Sends POST /api/v1/search
        │
        ▼
  [FastAPI Backend]
  1. Checks database for cached results → returns them instantly
  2. If no results (or crawl_fresh=true) → creates a CrawlJob in DB
  3. Sends that job to a Redis queue
        │
        ▼
  [Redis Queue]
  Holds the job until a worker is free
        │
        ▼
  [Celery Worker]
  Picks up the job, runs the crawlers concurrently:
    - Amazon crawler
    - eBay crawler
    - (any future stores)
        │
        ▼
  [Playwright Browser]
  Opens a real Chromium browser (headless)
  Navigates to amazon.com/s?k=iphone+16
  Waits for the page to render
  Returns the full HTML
        │
        ▼
  [BeautifulSoup Parser]
  Reads the HTML, extracts:
    - Product name
    - Price
    - Rating
    - Availability
    - Image URL
        │
        ▼
  [PostgreSQL Database]
  Stores products and price listings
  Records price history for trend analysis
        │
        ▼
  [Frontend polls job status via SSE]
  When job completes → re-fetches search results
  Displays price comparison table
```

**Key insight:** The scraping happens *asynchronously* in the background. The user sees cached results instantly, and fresh results load automatically when the crawl finishes.

---

## 2. Technology Choices and Why

### Backend: Python + FastAPI

**Why Python?**
- Best ecosystem for web scraping (Playwright, BeautifulSoup, Scrapy)
- Excellent async support with `asyncio`
- Rich data science libraries for price analysis

**Why FastAPI over Flask/Django?**
- Native async/await support — handles thousands of concurrent requests
- Automatic OpenAPI docs at `/api/docs`
- Pydantic validation — catches bad data before it hits your database
- Much faster than Flask for I/O-bound work (scraping is I/O-bound)

### Scraping: Playwright over requests/aiohttp

**Why not just use `requests` or `aiohttp`?**

Most e-commerce sites (Amazon, eBay) are protected by:
- Bot detection (checks for `navigator.webdriver` flag in JavaScript)
- CAPTCHA challenges
- JavaScript-rendered content (the product prices are loaded by JS, not in the raw HTML)

A raw HTTP request gets a bot-detection page, not product data.

**Playwright** launches a real Chromium browser. To Amazon's servers, it looks identical to a real human visiting the site. It:
- Executes JavaScript
- Has a real viewport, fonts, and browser fingerprint
- Supports stealth patches to hide automation signals

### Database: PostgreSQL

**Why not SQLite or MongoDB?**
- PostgreSQL has excellent support for complex queries needed for price comparison
- Full-text search with `ILIKE` for product search
- Handles concurrent writes from multiple crawl workers
- JSON support for flexible product metadata

### Background Jobs: Celery + Redis

**Why run scraping in the background?**

Scraping Amazon for "iPhone 16" takes 10–60 seconds. You cannot make the user wait 60 seconds for a page to load. The solution:

1. Accept the request immediately (return in <100ms)
2. Put the scraping work in a queue
3. A separate worker process does the scraping
4. The frontend polls for completion

**Redis** is the queue (broker). It's an in-memory data store — extremely fast for passing job messages.

**Celery** is the task runner that reads from the queue and executes the scraping functions.

### Frontend: Next.js

**Why Next.js over plain React?**
- Server-side rendering — better SEO (products are indexed by Google)
- Built-in API proxy (rewrites) — avoids CORS issues
- File-based routing — simple to add new pages
- React Query for smart caching and background re-fetching

---

## 3. Project Structure

```
price_compare/
│
├── backend/                    # Python FastAPI application
│   ├── app/
│   │   ├── main.py             # FastAPI app entrypoint
│   │   ├── core/
│   │   │   ├── config.py       # All settings (reads from .env)
│   │   │   ├── database.py     # SQLAlchemy async engine
│   │   │   └── redis.py        # Redis cache helpers
│   │   │
│   │   ├── models/
│   │   │   └── product.py      # Database table definitions
│   │   │
│   │   ├── schemas/
│   │   │   └── product.py      # Pydantic request/response shapes
│   │   │
│   │   ├── crawlers/           # ← THE HEART OF THE APP
│   │   │   ├── base.py         # Rate limiting, Playwright, robots.txt
│   │   │   ├── amazon.py       # Amazon-specific parser
│   │   │   ├── ebay.py         # eBay-specific parser
│   │   │   └── generic.py      # Works on any e-commerce site (JSON-LD)
│   │   │
│   │   ├── services/
│   │   │   ├── crawler_service.py    # Runs all crawlers concurrently
│   │   │   ├── comparison_service.py # Price analysis logic
│   │   │   └── analytics_service.py  # Platform-wide stats
│   │   │
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── search.py   # POST /search
│   │   │       ├── products.py # GET /products/{id}/analysis
│   │   │       ├── crawl.py    # POST /crawl, GET /crawl/{id}/stream
│   │   │       └── analytics.py
│   │   │
│   │   ├── workers/
│   │   │   ├── celery_app.py   # Celery configuration
│   │   │   └── tasks.py        # Background task functions
│   │   │
│   │   └── telemetry/
│   │       └── otel.py         # OpenTelemetry setup
│   │
│   ├── alembic/                # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                   # Next.js application
│   └── src/
│       ├── app/                # Next.js App Router pages
│       │   ├── page.tsx        # Home page
│       │   ├── search/         # Search results page
│       │   ├── products/[id]/  # Product detail + price comparison
│       │   └── analytics/      # Platform analytics
│       │
│       ├── components/
│       │   ├── ui/             # Reusable UI components
│       │   └── charts/         # Recharts price history charts
│       │
│       └── lib/
│           ├── api.ts          # All API call functions
│           └── otel.ts         # Browser-side OpenTelemetry
│
├── otel-collector/             # OpenTelemetry collector config
├── docker-compose.yml          # Runs everything with one command
├── prometheus.yml
└── Makefile                    # Shortcuts (make up, make migrate, etc.)
```

---

## 4. Phase 1 — Backend Foundation

### Step 1: Settings Management

**File:** `backend/app/core/config.py`

Every configurable value lives in one place, read from environment variables:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/pricecompare"
    redis_url: str = "redis://redis:6379/0"
    crawler_concurrency: int = 10
    rate_limit_delay_seconds: float = 1.5

    class Config:
        env_file = ".env"

settings = Settings()
```

**Why this pattern?**
- In development, values come from `.env`
- In production (Docker), values come from environment variables
- You never hardcode secrets in your code

### Step 2: Database Models

**File:** `backend/app/models/product.py`

Your database has 4 tables:

```
products          — one row per unique product (e.g., "iPhone 16 Pro 256GB")
price_listings    — one row per store that sells that product
price_history     — time-series log of every price we've seen
crawl_jobs        — tracks background scraping jobs
```

Relationships:
```
Product (1) ──── (many) PriceListing
Product (1) ──── (many) PriceHistory
```

**Key concept — normalized name:**
```python
class Product(Base):
    normalized_name: str  # "iphone 16 pro 256gb" (lowercase, no punctuation)
```

When Amazon returns "Apple iPhone 16 Pro — 256GB" and eBay returns "Apple iPhone 16 Pro 256GB (Black)", both normalize to the same string and are matched as the same product.

### Step 3: Async Database Session

**File:** `backend/app/core/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(settings.database_url, pool_size=20)
AsyncSessionLocal = async_sessionmaker(engine)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
        await session.commit()
```

**Why async?**
When a database query is running, your Python process would normally just sit and wait. With async, it switches to handling another request while waiting. This is why FastAPI can handle thousands of concurrent users with a single process.

### Step 4: Redis Cache

**File:** `backend/app/core/redis.py`

```python
async def cache_get(key: str):
    r = await get_redis()
    value = await r.get(key)
    return json.loads(value) if value else None

async def cache_set(key: str, value, ttl: int = 300):
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value))
```

**Where caching is used:**
- Search results cached for 5 minutes — repeat searches are instant
- Price analysis cached for 30 minutes — complex statistics aren't recalculated every time
- Platform stats cached for 2 minutes

---

## 5. Phase 2 — The Web Scraper

This is the most complex part. Read it carefully.

### Step 1: Understanding the Base Crawler

**File:** `backend/app/crawlers/base.py`

Every scraper inherits from `BaseCrawler`. It handles the shared infrastructure:

#### Rate Limiting

```python
class RateLimiter:
    def __init__(self, delay: float = 1.5):
        self._delay = delay
        self._last_request: dict[str, float] = {}

    async def wait(self, domain: str):
        last = self._last_request.get(domain, 0)
        elapsed = time.monotonic() - last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last_request[domain] = time.monotonic()
```

**Why?** If you send 100 requests per second to Amazon, they ban your IP immediately. This ensures you wait at least 1.5 seconds between requests to the same domain.

#### Robots.txt Compliance

```python
async def can_fetch(self, session, url: str) -> bool:
    # Fetches /robots.txt, parses it, checks if our URL is allowed
```

**Why?** `robots.txt` is the file where websites declare what scrapers are and aren't allowed to crawl. Respecting it is both ethical and reduces the chance of being blocked.

#### Playwright Browser Management

```python
async def __aenter__(self):
    self._playwright = await async_playwright().start()
    self._browser = await self._playwright.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
    )
    return self

async def __aexit__(self, *args):
    await self._browser.close()
    await self._playwright.stop()
```

Usage pattern:
```python
async with AmazonCrawler() as crawler:
    results = await crawler.search("iphone 16")
```

The `async with` block ensures the browser is always properly closed, even if an exception occurs.

#### Stealth Script

```python
_STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.chrome = {runtime: {}};
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
"""
```

When Playwright launches a browser, it sets `navigator.webdriver = true`. Bot detection scripts check this flag. We override it to `undefined` so the site thinks it's a normal human.

#### The Fetch Method

```python
async def fetch_html(self, url: str) -> str | None:
    # 1. Check robots.txt
    # 2. Wait for rate limit
    # 3. Create a new browser context (like incognito tab)
    # 4. Inject stealth script
    # 5. Navigate to URL
    # 6. Wait 1.5s for JS to render
    # 7. Return full page HTML
    # 8. Close the browser context
```

Each page gets its own incognito context. This means cookies don't persist between requests (prevents session tracking).

### Step 2: Building a Site-Specific Crawler

Let's walk through the Amazon crawler step by step.

**File:** `backend/app/crawlers/amazon.py`

#### The Search Method

```python
SEARCH_URL = "https://www.amazon.com/s?k={query}"

async def search(self, query: str) -> list[ScrapedProduct]:
    url = SEARCH_URL.format(query=quote_plus(query))  # URL-encode the query
    html = await self.fetch_html(url)
    if not html:
        return []
    return self._parse_search_results(html, query)
```

#### How to Find the Right CSS Selectors

This is the skill you must develop. Open Amazon in Chrome, search for a product, then:

1. Right-click a product card → "Inspect"
2. Look at the HTML structure
3. Find a unique attribute that identifies all product cards

For Amazon, each result card has:
```html
<div data-component-type="s-search-result" ...>
```

So your selector is: `[data-component-type="s-search-result"]`

Inside each card:
```python
# Product name
name_el = item.select_one("h2 a span")

# Price — Amazon splits price into whole and fraction parts
whole = item.select_one(".a-price .a-price-whole")    # "999"
fraction = item.select_one(".a-price .a-price-fraction")  # "99"
# Combined: $999.99

# Product URL
link = item.select_one("h2 a")["href"]  # relative URL

# Rating
rating_el = item.select_one("span[aria-label*='out of 5']")
```

#### The ScrapedProduct Dataclass

```python
@dataclass
class ScrapedProduct:
    store_name: str      # "Amazon"
    store_domain: str    # "amazon.com"
    product_url: str     # full URL to the product page
    name: str            # "Apple iPhone 16 Pro 256GB"
    price: float         # 999.99
    currency: str        # "USD"
    original_price: float | None  # if on sale, the original price
    availability: str    # "in_stock" | "out_of_stock" | "unknown"
    rating: float | None
    review_count: int | None
    # ... etc
```

### Step 3: The Generic Crawler — JSON-LD

**File:** `backend/app/crawlers/generic.py`

Most modern e-commerce sites include structured data in their HTML for SEO. It looks like:

```html
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "iPhone 16 Pro",
  "offers": {
    "price": "999.99",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock"
  }
}
</script>
```

This is the **most reliable** scraping method because:
- It's machine-readable by design
- It's not affected by CSS class name changes
- It works on Shopify, WooCommerce, Magento, and thousands of other platforms

```python
def _extract_json_ld(self, soup, url: str) -> ScrapedProduct | None:
    for script in soup.find_all("script", type="application/ld+json"):
        data = json.loads(script.string)
        if data.get("@type") == "Product":
            name = data["name"]
            price = data["offers"]["price"]
            currency = data["offers"]["priceCurrency"]
            # ... extract everything
            return ScrapedProduct(...)
```

**Extraction priority order:**
1. JSON-LD structured data (most reliable)
2. Open Graph meta tags (`<meta property="og:title">`)
3. CSS selectors (least reliable — breaks when sites redesign)

### Step 4: Running Crawlers Concurrently

**File:** `backend/app/services/crawler_service.py`

```python
async def search_all_stores(self, query: str) -> list[ScrapedProduct]:
    # Run Amazon AND eBay at the same time
    tasks = [
        self._safe_search(AmazonCrawler(), query),
        self._safe_search(EbayCrawler(), query),
    ]
    results_nested = await asyncio.gather(*tasks)
    return [item for sublist in results_nested for item in sublist]
```

`asyncio.gather()` runs all coroutines concurrently. If Amazon takes 15 seconds and eBay takes 12 seconds, the total time is 15 seconds — not 27 seconds.

**Why `_safe_search` instead of calling directly?**

```python
async def _safe_search(self, crawler, query):
    try:
        async with crawler:
            return await crawler.search(query)
    except Exception as exc:
        logger.error("Crawler %s failed: %s", crawler.store_name, exc)
        return []  # Return empty list, don't crash everything
```

If Amazon is down or blocks us, eBay results should still show. Never let one crawler failure break the entire search.

### Step 5: Persisting Results — Product Deduplication

**File:** `backend/app/services/crawler_service.py`

```python
async def persist_results(self, db, scraped: list[ScrapedProduct]):
    # Group results by normalized product name
    groups = {}
    for item in scraped:
        key = normalize_name(item.name)  # "iphone 16 pro 256gb"
        groups.setdefault(key, []).append(item)

    for norm_name, items in groups.items():
        # Find or create the Product record
        product = await self._upsert_product(db, items[0], norm_name)

        # Add a PriceListing for each store
        for item in items:
            await self._upsert_listing(db, product, item)

            # Always append to price history (for trend charts)
            await self._append_price_history(db, product, item)
```

**Name normalization:**
```python
def normalize_name(name: str) -> str:
    # "Apple iPhone 16 Pro — 256GB, Black"
    # → "apple iphone 16 pro 256gb black"
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s]", " ", name.lower())
    return re.sub(r"\s+", " ", name).strip()
```

---

## 6. Phase 3 — Background Jobs

### Why Celery?

Scraping takes too long to do in a web request. A user will give up after 3 seconds. Scraping Amazon takes 15–60 seconds. The solution: queue the work.

```
Web Request (fast) → Redis Queue → Celery Worker (slow, runs separately)
```

### Step 1: Celery Configuration

**File:** `backend/app/workers/celery_app.py`

```python
from celery import Celery

celery_app = Celery(
    "pricecompare",
    broker="redis://redis:6379/1",    # where jobs are stored
    backend="redis://redis:6379/2",   # where results are stored
)

celery_app.conf.update(
    task_serializer="json",
    task_acks_late=True,              # only mark task done AFTER it succeeds
    worker_prefetch_multiplier=1,     # take one job at a time (fair for long tasks)
)
```

**Queues:**
- `crawl` — product scraping jobs (slow, many concurrent)
- `maintenance` — price refresh jobs (less urgent)

### Step 2: The Critical Event Loop Issue

**This is the most common mistake when combining asyncio with Celery.**

Celery workers are synchronous. When you call `asyncio.run()` inside a Celery task, it creates a brand new event loop. But if SQLAlchemy's engine was created at module import time (on a different loop), using it on the new loop causes:

```
RuntimeError: Future attached to a different loop
```

**The fix:** Create a fresh database engine *inside* the async task function:

```python
@asynccontextmanager
async def _task_db():
    # Create engine HERE, inside asyncio.run()'s event loop
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine)
    async with Session() as db:
        try:
            yield db
            await db.commit()
        finally:
            await engine.dispose()  # always clean up

# In your task:
async def _crawl_query_async(task, job_id, query):
    async with _task_db() as db:
        # safe — engine was created on this event loop
        job = await db.get(CrawlJob, job_id)
```

### Step 3: Writing a Celery Task

```python
@shared_task(
    bind=True,           # gives access to self (the task instance)
    max_retries=2,       # retry up to 2 times on failure
    time_limit=300,      # kill task if it runs more than 5 minutes
)
def crawl_query(self, job_id: str, query: str):
    return asyncio.run(_crawl_query_async(self, job_id, query))

async def _crawl_query_async(task, job_id: str, query: str):
    async with _task_db() as db:
        # Mark job as in-progress
        job = await db.get(CrawlJob, job_id)
        job.status = CrawlStatus.IN_PROGRESS

    try:
        # Do the actual scraping
        service = CrawlerService()
        scraped = await service.search_all_stores(query)

        # Save results
        async with _task_db() as db:
            products = await service.persist_results(db, scraped)

        # Mark job as completed
        async with _task_db() as db:
            job = await db.get(CrawlJob, job_id)
            job.status = CrawlStatus.COMPLETED
            job.results_count = len(products)

    except Exception as exc:
        # Mark as failed and re-raise for Celery retry
        async with _task_db() as db:
            job.status = CrawlStatus.FAILED
            job.error_message = str(exc)
        raise task.retry(exc=exc)
```

### Step 4: Dispatching a Task

From the API:
```python
# This returns immediately — the task runs in the background
crawl_query.apply_async(
    args=[str(job.id), request.query],
    queue="crawl"
)
```

### Step 5: Server-Sent Events for Real-Time Updates

Instead of the frontend polling every second, the backend streams status updates:

```python
@router.get("/{job_id}/stream")
async def stream_crawl_status(job_id: str):
    async def event_generator():
        for _ in range(60):  # max 60 seconds
            job = await db.get(CrawlJob, job_id)
            yield f"data: {json.dumps({'status': job.status})}\n\n"

            if job.status in ("completed", "failed"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

On the frontend:
```typescript
const evtSource = new EventSource(`/api/v1/crawl/${jobId}/stream`);
evtSource.onmessage = (event) => {
    const { status } = JSON.parse(event.data);
    if (status === "completed") {
        evtSource.close();
        refetchResults();  // re-fetch search results
    }
};
```

---

## 7. Phase 4 — The REST API

### Step 1: FastAPI Route Structure

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/search", tags=["search"])

@router.post("")
async def search_products(
    request: SearchRequest,          # Pydantic validates the request body
    db: AsyncSession = Depends(get_db)  # DB session injected automatically
):
    ...
```

### Step 2: The Search Endpoint Flow

```
POST /api/v1/search {"query": "laptop", "crawl_fresh": false}

1. Query the database for products matching "laptop"
2. If results exist → return them instantly (from cache)
3. If no results OR crawl_fresh=true:
   a. Create a CrawlJob record
   b. Dispatch a Celery task
   c. Return empty results + the job ID
4. Frontend uses the job ID to watch the SSE stream
5. When task completes → frontend re-fetches search
```

### Step 3: Price Analysis

**File:** `backend/app/services/comparison_service.py`

```python
async def get_analysis(self, db, product_id):
    product = await db.get(Product, product_id, options=[selectinload(Product.listings)])

    prices = [l.price for l in product.listings]

    return PriceAnalysis(
        lowest_price=min(prices),
        highest_price=max(prices),
        average_price=statistics.mean(prices),
        median_price=statistics.median(prices),
        best_deal=min(product.listings, key=lambda l: l.price),
        savings_vs_highest=max(prices) - min(prices),
        savings_percent=(1 - min(prices) / max(prices)) * 100,
    )
```

### Step 4: Dependency Injection

FastAPI's `Depends()` pattern is how you share resources (DB sessions, auth) across routes without globals:

```python
# This function is called automatically for every request
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session  # give the session to the route handler
        await session.commit()  # commit after the handler returns

# Route receives the session automatically
@router.get("/{id}")
async def get_product(id: str, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, id)
    return product
```

---

## 8. Phase 5 — The Frontend

### Step 1: Project Setup (Next.js App Router)

```
frontend/src/app/           ← pages live here
    page.tsx                ← renders at "/"
    search/
        page.tsx            ← renders at "/search"
        SearchResults.tsx   ← client component (needs "use client")
    products/
        [id]/
            page.tsx        ← renders at "/products/abc123"
    analytics/
        page.tsx
```

### Step 2: API Client

**File:** `frontend/src/lib/api.ts`

All backend calls go through one file:

```typescript
import axios from "axios";

const api = axios.create({
    baseURL: "/api/v1",   // proxied to backend via Next.js rewrites
    timeout: 30_000,
});

export const searchProducts = async (query: string) => {
    const { data } = await api.post("/search", { query });
    return data;
};
```

### Step 3: Next.js Proxy (Avoiding CORS)

**File:** `frontend/next.config.ts`

```typescript
async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    return [{
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
    }];
}
```

The browser calls `/api/v1/search` (same origin — no CORS).
Next.js server forwards it to `http://backend:8000/api/v1/search`.

**Important:** Use `BACKEND_URL` (server-side variable), NOT `NEXT_PUBLIC_API_URL` for rewrites. `NEXT_PUBLIC_*` variables are embedded in the browser JavaScript bundle at build time. Rewrites run server-side and need a runtime variable.

### Step 4: React Query for Smart Data Fetching

```typescript
import { useQuery, useQueryClient } from "@tanstack/react-query";

function SearchResults({ query }) {
    const queryClient = useQueryClient();

    const { data, isLoading } = useQuery({
        queryKey: ["search", query],  // cache key — same query = cached result
        queryFn: () => searchProducts(query),
        enabled: !!query,             // don't run if query is empty
    });

    const handleCrawlComplete = () => {
        // Invalidate cache → React Query re-fetches automatically
        queryClient.invalidateQueries({ queryKey: ["search", query] });
    };
}
```

**Why React Query?**
- Automatic caching: search "laptop" twice → second is instant
- Background refetch: stale data updates silently
- Loading/error states built-in
- `invalidateQueries` triggers re-fetch when crawl completes

### Step 5: Server-Sent Events on the Frontend

```typescript
useEffect(() => {
    if (!crawlJobId) return;

    const evtSource = new EventSource(`/api/v1/crawl/${crawlJobId}/stream`);

    evtSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setStatus(data.status);

        if (data.status === "completed") {
            evtSource.close();
            onComplete();  // re-fetch search results
        }
    };

    return () => evtSource.close();  // cleanup on unmount
}, [crawlJobId]);
```

### Step 6: Price History Chart

```typescript
import { LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";

// Transform flat history into chart-friendly format
const chartData = history.reduce((acc, point) => {
    const date = new Date(point.recorded_at).toLocaleDateString();
    if (!acc[date]) acc[date] = { date };
    acc[date][point.store_domain] = point.price;
    return acc;
}, {});

<LineChart data={Object.values(chartData)}>
    <Line dataKey="amazon.com" stroke="#3b82f6" />
    <Line dataKey="ebay.com" stroke="#22c55e" />
</LineChart>
```

---

## 9. Phase 6 — Observability

Without observability, you're flying blind. OpenTelemetry gives you three types of data:

### Traces — "What happened during this request?"

```python
tracer = trace.get_tracer("my-service")

async def search_products(query: str):
    with tracer.start_as_current_span("search.query") as span:
        span.set_attribute("search.query", query)
        results = await db.execute(...)
        span.set_attribute("search.results_count", len(results))
        return results
```

In Jaeger (at `http://localhost:16686`), you'll see a timeline showing:
- How long the DB query took
- How long each crawler took
- Where time was spent in the request

### Metrics — "How is the system performing over time?"

```python
meter = metrics.get_meter("crawlers")

requests_total = meter.create_counter("crawler.requests.total")
request_duration = meter.create_histogram("crawler.request.duration")

async def fetch_html(self, url: str):
    start = time.monotonic()
    html = await self._playwright_fetch(url)
    request_duration.record(time.monotonic() - start, {"store": self.store_name})
    requests_total.add(1, {"status": "success"})
```

Prometheus scrapes these metrics. Grafana (`http://localhost:3001`) visualizes them.

### Setup

**File:** `backend/app/telemetry/otel.py`

```python
def setup_telemetry(app):
    resource = Resource.create({SERVICE_NAME: "pricecompare-api"})

    # Traces → Jaeger
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317"))
    )
    trace.set_tracer_provider(trace_provider)

    # Metrics → Prometheus
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[PrometheusMetricReader()]
    ))

    # Auto-instrument FastAPI, SQLAlchemy, Redis
    FastAPIInstrumentor.instrument_app(app)
    RedisInstrumentor().instrument()
```

---

## 10. Phase 7 — Docker

### Why Docker?

Your app has 9 services: PostgreSQL, Redis, backend, worker, beat, frontend, OTel collector, Jaeger, Prometheus. Without Docker, you'd install and configure all 9 on your machine. With Docker:

```bash
docker compose up -d   # everything running in 30 seconds
```

### Key Docker Compose Concepts

**Service dependencies:**
```yaml
backend:
    depends_on:
        db:
            condition: service_healthy   # wait until postgres is ready
        redis:
            condition: service_healthy
```

**Health checks:**
```yaml
db:
    healthcheck:
        test: ["CMD-SHELL", "pg_isready -U postgres"]
        interval: 10s
        retries: 5
```

**Named volumes — persistent data:**
```yaml
volumes:
    postgres_data:   # data survives container restarts
    redis_data:
```

### Backend Dockerfile Explained

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies FIRST (changes rarely → cached)
RUN apt-get update && apt-get install -y gcc libpq-dev curl

# Install Python packages NEXT (changes sometimes → cached if requirements.txt unchanged)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright browser dependencies + browser
RUN playwright install chromium --with-deps

# Copy app code LAST (changes often → invalidates least cache)
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Why this order?** Docker caches each layer. If you copy code first, every code change rebuilds pip install (slow). By copying requirements.txt first, pip install is only re-run when dependencies change.

---

## 11. Scalability Patterns

### Pattern 1: Caching at Multiple Levels

```
Request → Redis cache (< 1ms) → miss → Database (5-50ms) → miss → Crawl (10-60s)
```

Cache hierarchy:
1. Redis: stores serialized query results for 5 minutes
2. Database: stores all historical data permanently
3. Crawl: only happens when data is missing or stale

### Pattern 2: Async I/O

All I/O (database, Redis, HTTP) uses `async/await`. When waiting for PostgreSQL to respond, Python handles other requests. A single worker process can handle hundreds of concurrent requests.

```python
# BAD — blocks the entire process while waiting
result = requests.get("https://amazon.com")

# GOOD — frees up the event loop while waiting
result = await client.get("https://amazon.com")
```

### Pattern 3: Horizontal Scaling

Add more workers by adding more Celery worker containers:

```yaml
worker:
    deploy:
        replicas: 4   # run 4 worker containers
```

All workers share the same Redis queue. Jobs are distributed automatically.

### Pattern 4: Database Connection Pooling

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=20,        # keep 20 connections open
    max_overflow=10,     # allow 10 extra when needed
    pool_pre_ping=True,  # test connections before using
)
```

Without pooling, each request opens and closes a database connection (expensive). Pooling reuses existing connections.

### Pattern 5: Separate Queues by Priority

```python
# Urgent: triggered by a user searching right now
crawl_query.apply_async(args=[...], queue="crawl")

# Routine: hourly background refresh
refresh_stale_prices.apply_async(args=[...], queue="maintenance")
```

Workers can be configured to prioritize the `crawl` queue over `maintenance`.

---

## 12. Common Problems and How to Solve Them

### Problem: Getting blocked by Amazon/eBay

**Symptoms:** Empty results, CAPTCHA pages, 503 errors

**Solutions:**
1. Use Playwright (we already do) — it's harder to detect than raw HTTP
2. Rotate user agents (we do this with `fake_useragent`)
3. Add random delays between requests (we do this with `RateLimiter`)
4. For production scale: consider paid proxy services (Bright Data, Oxylabs)

### Problem: "Future attached to a different loop"

**Cause:** Using a SQLAlchemy async engine that was created on one asyncio event loop from inside `asyncio.run()` which creates a new event loop.

**Fix:** Always create the async engine inside the async function being run by `asyncio.run()`. See the `_task_db()` context manager pattern in `tasks.py`.

### Problem: Selectors stop working after a site redesign

**Cause:** Amazon and eBay frequently change their HTML structure and CSS classes.

**Fix:**
1. Always try JSON-LD first (it's SEO data and changes rarely)
2. Use multiple fallback selectors
3. Write tests that run against saved HTML snapshots
4. Monitor your scrapers with metrics to detect failure spikes

### Problem: Crawl jobs stuck in "pending" state

**Cause:** Celery worker isn't running, or Redis broker is unreachable.

**Debug:**
```bash
# Check if worker is running
docker compose logs worker

# Check if it can reach Redis
docker compose exec worker celery -A app.workers.celery_app inspect ping

# Check what's in the queue
docker compose exec redis redis-cli llen crawl
```

### Problem: NEXT_PUBLIC_ variable not working in rewrites

**Cause:** `NEXT_PUBLIC_*` variables are embedded at build time. At build time in Docker, the value is unknown.

**Fix:** Use a plain `BACKEND_URL` environment variable for server-side rewrites. Only use `NEXT_PUBLIC_*` for values that need to be available in the browser JavaScript bundle.

---

## 13. How to Extend This Project

### Add a New Store

1. Create `backend/app/crawlers/walmart.py`:

```python
class WalmartCrawler(BaseCrawler):
    store_name = "Walmart"
    store_domain = "walmart.com"

    async def search(self, query: str) -> list[ScrapedProduct]:
        url = f"https://www.walmart.com/search?q={quote_plus(query)}"
        html = await self.fetch_html(url)
        # inspect walmart.com search results page, find your selectors
        return self._parse(html)

    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        html = await self.fetch_html(url)
        # inspect a walmart product page, find your selectors
        return self._parse_product(html)
```

2. Register it in `backend/app/crawlers/__init__.py`:

```python
SEARCH_CRAWLERS = [AmazonCrawler, EbayCrawler, WalmartCrawler]
```

That's it. The service layer and API pick it up automatically.

### Add Price Alerts

1. Add a `PriceAlert` model:
```python
class PriceAlert(Base):
    user_email: str
    product_id: UUID
    target_price: float
    is_triggered: bool = False
```

2. Add a Celery beat task that runs every hour:
```python
@celery_app.task
async def check_price_alerts():
    # Find alerts where current best price <= target_price
    # Send email notifications
```

### Add User Accounts

1. Add authentication with `python-jose` (JWT tokens)
2. Add a `users` table
3. Protect routes with a `current_user` dependency
4. Link saved searches and alerts to users

### Improve Search Quality

Replace `ILIKE` with PostgreSQL full-text search:

```python
from sqlalchemy import func

stmt = select(Product).where(
    func.to_tsvector("english", Product.name).op("@@")(
        func.plainto_tsquery("english", query)
    )
)
```

This handles plurals, stemming, and relevance ranking.

---

## Quick Start

```bash
# 1. Start all services
cd price_compare
make up

# 2. Run database migrations
make migrate

# 3. Open the app
open http://localhost:3000

# 4. View API docs
open http://localhost:8000/api/docs

# 5. View distributed traces (Jaeger)
open http://localhost:16686

# 6. View metrics (Grafana)
open http://localhost:3001

# 7. Trigger a manual crawl from the terminal
make crawl q="gaming laptop"
```

---

## Learning Path

Follow this order to understand the codebase:

| Step | File | What you'll learn |
|------|------|-------------------|
| 1 | `backend/app/core/config.py` | Settings and environment variables |
| 2 | `backend/app/models/product.py` | Database schema design |
| 3 | `backend/app/crawlers/base.py` | Playwright, rate limiting, robots.txt |
| 4 | `backend/app/crawlers/amazon.py` | CSS selectors and HTML parsing |
| 5 | `backend/app/crawlers/generic.py` | JSON-LD structured data extraction |
| 6 | `backend/app/services/crawler_service.py` | Concurrency with asyncio.gather |
| 7 | `backend/app/workers/tasks.py` | Celery tasks and event loop management |
| 8 | `backend/app/api/routes/search.py` | FastAPI routes and dependency injection |
| 9 | `frontend/src/lib/api.ts` | TypeScript API client |
| 10 | `frontend/src/app/search/SearchResults.tsx` | React Query + SSE |
| 11 | `backend/app/telemetry/otel.py` | OpenTelemetry traces and metrics |
| 12 | `docker-compose.yml` | Orchestrating all services |
