"""
Generic e-commerce crawler using heuristic selectors and JSON-LD schema.org
data (most modern e-commerce sites include this for SEO).
"""
import json
import logging
import re
from urllib.parse import quote_plus, urlparse

from app.crawlers.base import BaseCrawler, ScrapedProduct
from app.telemetry.otel import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer("crawlers.generic")

# Common CSS selectors used across e-commerce platforms (Shopify, WooCommerce, Magento, etc.)
PRICE_SELECTORS = [
    "[itemprop='price']",
    ".price",
    ".product-price",
    ".product__price",
    ".price__regular",
    ".price-box .price",
    "[data-price]",
    "#priceBlock .price",
    ".entry-price",
    ".woocommerce-Price-amount",
    ".offer-price",
    ".sale-price",
    "span.amount",
]

NAME_SELECTORS = [
    "h1[itemprop='name']",
    "h1.product-title",
    "h1.product__title",
    "h1.entry-title",
    "h1.product_title",
    "#productTitle",
    "h1",
]

IMAGE_SELECTORS = [
    "[itemprop='image']",
    ".product__image img",
    ".product-image img",
    ".woocommerce-product-gallery__image img",
    "#main-image img",
    ".gallery-image",
]

AVAILABILITY_SELECTORS = [
    "[itemprop='availability']",
    ".availability",
    ".stock",
    ".product-availability",
    "#availability",
]


class GenericCrawler(BaseCrawler):
    """
    Crawls arbitrary e-commerce URLs.
    Prioritises JSON-LD schema.org Product markup, falls back to CSS selectors.
    """

    store_name = "Generic"
    store_domain = ""
    supports_search = False  # No unified search; called with specific URLs

    def __init__(self, store_name: str = "", store_domain: str = ""):
        super().__init__()
        if store_name:
            self.store_name = store_name
        if store_domain:
            self.store_domain = store_domain

    async def search(self, query: str) -> list[ScrapedProduct]:
        # Generic crawler does not support keyword search
        return []

    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        parsed = urlparse(url)
        domain = parsed.netloc.lstrip("www.")
        self.store_domain = domain
        self.store_name = domain.split(".")[0].capitalize()

        with tracer.start_as_current_span(
            "generic.scrape_product",
            attributes={"url": url, "domain": domain},
        ):
            html = await self.fetch_html(url)
            if not html:
                return None

            soup = self.parse_soup(html)

            # 1. Try JSON-LD first (most reliable)
            product = self._extract_json_ld(soup, url)
            if product:
                return product

            # 2. Try Open Graph / meta tags
            product = self._extract_meta_tags(soup, url)
            if product:
                return product

            # 3. Heuristic CSS selectors
            return self._extract_via_selectors(soup, url)

    def _extract_json_ld(self, soup, url: str) -> ScrapedProduct | None:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                # Handle arrays or single object
                if isinstance(data, list):
                    data = next((d for d in data if d.get("@type") in ("Product", "IndividualProduct")), None)
                if not data or data.get("@type") not in ("Product", "IndividualProduct"):
                    continue

                name = data.get("name", "")
                if not name:
                    continue

                # Extract offer price
                offers = data.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}

                price_str = offers.get("price", offers.get("lowPrice", ""))
                price = self._parse_price(str(price_str))
                if price is None:
                    continue

                currency = offers.get("priceCurrency", "USD")
                availability_url = offers.get("availability", "")
                availability = "in_stock" if "InStock" in availability_url else \
                               "out_of_stock" if "OutOfStock" in availability_url else "unknown"

                image = data.get("image", "")
                if isinstance(image, list):
                    image = image[0] if image else ""
                if isinstance(image, dict):
                    image = image.get("url", "")

                brand = data.get("brand", {})
                if isinstance(brand, dict):
                    brand = brand.get("name", "")

                rating_data = data.get("aggregateRating", {})
                rating = float(rating_data.get("ratingValue", 0)) or None
                review_count = int(rating_data.get("reviewCount", 0)) or None

                description = data.get("description", "")[:1000] or None

                return ScrapedProduct(
                    store_name=self.store_name,
                    store_domain=self.store_domain,
                    product_url=url,
                    name=name,
                    price=price,
                    currency=currency,
                    availability=availability,
                    image_url=image or None,
                    brand=brand or None,
                    rating=rating,
                    review_count=review_count,
                    description=description,
                )
            except Exception as exc:
                logger.debug("JSON-LD parse error at %s: %s", url, exc)
                continue
        return None

    def _extract_meta_tags(self, soup, url: str) -> ScrapedProduct | None:
        og_title = soup.find("meta", property="og:title")
        og_price = soup.find("meta", property="product:price:amount") or \
                   soup.find("meta", {"name": "twitter:data1"})
        og_image = soup.find("meta", property="og:image")

        name = og_title.get("content", "") if og_title else ""
        price_str = og_price.get("content", "") if og_price else ""
        price = self._parse_price(price_str)

        if not name or price is None:
            return None

        currency_el = soup.find("meta", property="product:price:currency")
        currency = currency_el.get("content", "USD") if currency_el else "USD"

        return ScrapedProduct(
            store_name=self.store_name,
            store_domain=self.store_domain,
            product_url=url,
            name=name,
            price=price,
            currency=currency,
            image_url=og_image.get("content") if og_image else None,
        )

    def _extract_via_selectors(self, soup, url: str) -> ScrapedProduct | None:
        # Name
        name = None
        for sel in NAME_SELECTORS:
            el = soup.select_one(sel)
            if el:
                name = el.get_text(strip=True)
                break
        if not name:
            return None

        # Price
        price = None
        for sel in PRICE_SELECTORS:
            el = soup.select_one(sel)
            if el:
                text = el.get("content") or el.get("data-price") or el.get_text()
                price = self._parse_price(text)
                if price:
                    break
        if price is None:
            return None

        # Image
        image_url = None
        for sel in IMAGE_SELECTORS:
            el = soup.select_one(sel)
            if el:
                image_url = el.get("src") or el.get("data-src")
                break

        # Availability
        availability = "unknown"
        for sel in AVAILABILITY_SELECTORS:
            el = soup.select_one(sel)
            if el:
                text = (el.get("content") or el.get_text(strip=True)).lower()
                if "in stock" in text or "instock" in text:
                    availability = "in_stock"
                elif "out of stock" in text or "outofstock" in text:
                    availability = "out_of_stock"
                break

        return ScrapedProduct(
            store_name=self.store_name,
            store_domain=self.store_domain,
            product_url=url,
            name=name,
            price=price,
            availability=availability,
            image_url=image_url,
        )
