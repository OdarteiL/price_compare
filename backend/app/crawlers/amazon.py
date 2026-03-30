"""
Amazon crawler — searches amazon.com and extracts product prices.
Note: Amazon aggressively blocks scrapers; this uses realistic headers
and rate limiting. For production, consider the Amazon Product API.
"""
import logging
from urllib.parse import quote_plus

from opentelemetry import trace

from app.crawlers.base import BaseCrawler, ScrapedProduct
from app.telemetry.otel import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer("crawlers.amazon")


class AmazonCrawler(BaseCrawler):
    store_name = "Amazon"
    store_domain = "amazon.com"
    supports_search = True

    SEARCH_URL = "https://www.amazon.com/s?k={query}&ref=nb_sb_noss"

    async def search(self, query: str) -> list[ScrapedProduct]:
        with tracer.start_as_current_span("amazon.search", attributes={"query": query}):
            url = self.SEARCH_URL.format(query=quote_plus(query))
            html = await self.fetch_html(url)
            if not html:
                return []
            return self._parse_search_results(html, query)

    def _parse_search_results(self, html: str, query: str) -> list[ScrapedProduct]:
        soup = self.parse_soup(html)
        results: list[ScrapedProduct] = []

        for item in soup.select('[data-component-type="s-search-result"]')[:10]:
            try:
                # Name
                name_el = item.select_one("h2 a span")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)

                # URL
                link_el = item.select_one("h2 a")
                if not link_el or not link_el.get("href"):
                    continue
                product_url = "https://www.amazon.com" + link_el["href"].split("?")[0]

                # Price — Amazon uses several price structures
                price = self._extract_amazon_price(item)
                if price is None:
                    continue

                # Original / strikethrough price
                orig_el = item.select_one(".a-text-price span.a-offscreen")
                original_price = self._parse_price(orig_el.get_text()) if orig_el else None

                # Rating
                rating_el = item.select_one("span[aria-label*='out of 5']")
                rating = None
                if rating_el:
                    try:
                        rating = float(rating_el["aria-label"].split(" out")[0])
                    except Exception:
                        pass

                # Review count
                review_el = item.select_one("span[aria-label*='stars'] + span a span")
                review_count = None
                if review_el:
                    try:
                        review_count = int(review_el.get_text(strip=True).replace(",", ""))
                    except Exception:
                        pass

                # Image
                img_el = item.select_one("img.s-image")
                image_url = img_el.get("src") if img_el else None

                results.append(ScrapedProduct(
                    store_name=self.store_name,
                    store_domain=self.store_domain,
                    product_url=product_url,
                    name=name,
                    price=price,
                    original_price=original_price,
                    currency="USD",
                    availability="in_stock",
                    image_url=image_url,
                    rating=rating,
                    review_count=review_count,
                ))
            except Exception as exc:
                logger.debug("Failed to parse Amazon result: %s", exc)
                continue

        return results

    def _extract_amazon_price(self, item) -> float | None:
        # Try whole + fraction
        whole = item.select_one(".a-price .a-price-whole")
        fraction = item.select_one(".a-price .a-price-fraction")
        if whole:
            price_text = whole.get_text(strip=True).replace(",", "").rstrip(".")
            if fraction:
                price_text += "." + fraction.get_text(strip=True)
            return self._parse_price(price_text)

        # Fallback: .a-offscreen
        off = item.select_one(".a-price .a-offscreen")
        if off:
            return self._parse_price(off.get_text())
        return None

    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        with tracer.start_as_current_span("amazon.scrape_product", attributes={"url": url}):
            html = await self.fetch_html(url)
            if not html:
                return None

            soup = self.parse_soup(html)
            try:
                name_el = soup.select_one("#productTitle")
                if not name_el:
                    return None
                name = name_el.get_text(strip=True)

                price_el = soup.select_one(".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice")
                price = self._parse_price(price_el.get_text()) if price_el else None
                if price is None:
                    return None

                img_el = soup.select_one("#landingImage, #imgBlkFront")
                image_url = img_el.get("src") if img_el else None

                avail_el = soup.select_one("#availability span")
                availability = "in_stock"
                if avail_el:
                    avail_text = avail_el.get_text(strip=True).lower()
                    if "out of stock" in avail_text:
                        availability = "out_of_stock"
                    elif "limited" in avail_text:
                        availability = "limited"

                brand_el = soup.select_one("#bylineInfo")
                brand = brand_el.get_text(strip=True).replace("Visit the ", "").replace(" Store", "") if brand_el else None

                rating_el = soup.select_one("#acrPopover")
                rating = None
                if rating_el and rating_el.get("title"):
                    try:
                        rating = float(rating_el["title"].split(" out")[0])
                    except Exception:
                        pass

                review_el = soup.select_one("#acrCustomerReviewText")
                review_count = None
                if review_el:
                    try:
                        review_count = int(review_el.get_text(strip=True).split(" ")[0].replace(",", ""))
                    except Exception:
                        pass

                desc_el = soup.select_one("#productDescription p, #feature-bullets")
                description = desc_el.get_text(strip=True)[:1000] if desc_el else None

                return ScrapedProduct(
                    store_name=self.store_name,
                    store_domain=self.store_domain,
                    product_url=url,
                    name=name,
                    price=price,
                    currency="USD",
                    availability=availability,
                    image_url=image_url,
                    brand=brand,
                    rating=rating,
                    review_count=review_count,
                    description=description,
                )
            except Exception as exc:
                logger.error("Failed to scrape Amazon product %s: %s", url, exc)
                return None
