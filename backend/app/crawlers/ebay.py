"""
eBay crawler — uses eBay's public search pages.
"""
import logging
from urllib.parse import quote_plus

from app.crawlers.base import BaseCrawler, ScrapedProduct
from app.telemetry.otel import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer("crawlers.ebay")


class EbayCrawler(BaseCrawler):
    store_name = "eBay"
    store_domain = "ebay.com"
    supports_search = True

    SEARCH_URL = "https://www.ebay.com/sch/i.html?_nkw={query}&_sop=12&LH_BIN=1"

    async def search(self, query: str) -> list[ScrapedProduct]:
        with tracer.start_as_current_span("ebay.search", attributes={"query": query}):
            url = self.SEARCH_URL.format(query=quote_plus(query))
            html = await self.fetch_html(url)
            if not html:
                return []
            return self._parse_search_results(html)

    def _parse_search_results(self, html: str) -> list[ScrapedProduct]:
        soup = self.parse_soup(html)
        results: list[ScrapedProduct] = []

        for item in soup.select(".s-item")[:10]:
            try:
                name_el = item.select_one(".s-item__title")
                if not name_el or name_el.get_text(strip=True).lower() == "shop on ebay":
                    continue
                name = name_el.get_text(strip=True)

                link_el = item.select_one(".s-item__link")
                if not link_el:
                    continue
                product_url = link_el["href"].split("?")[0]

                price_el = item.select_one(".s-item__price .POSITIVE, .s-item__price")
                if not price_el:
                    continue
                # Handle price ranges — take the lower bound
                price_text = price_el.get_text(strip=True).split(" to ")[0]
                price = self._parse_price(price_text)
                if price is None:
                    continue

                img_el = item.select_one(".s-item__image-img")
                image_url = img_el.get("src") if img_el else None

                shipping_el = item.select_one(".s-item__shipping, .s-item__freeXDays")
                shipping_cost = None
                if shipping_el:
                    sh_text = shipping_el.get_text(strip=True).lower()
                    if "free" in sh_text:
                        shipping_cost = 0.0
                    else:
                        shipping_cost = self._parse_price(sh_text)

                seller_el = item.select_one(".s-item__seller-info-text")
                seller_name = seller_el.get_text(strip=True) if seller_el else None

                results.append(ScrapedProduct(
                    store_name=self.store_name,
                    store_domain=self.store_domain,
                    product_url=product_url,
                    name=name,
                    price=price,
                    currency="USD",
                    availability="in_stock",
                    image_url=image_url,
                    shipping_cost=shipping_cost,
                    seller_name=seller_name,
                ))
            except Exception as exc:
                logger.debug("Failed to parse eBay result: %s", exc)
                continue

        return results

    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        with tracer.start_as_current_span("ebay.scrape_product", attributes={"url": url}):
            html = await self.fetch_html(url)
            if not html:
                return None
            soup = self.parse_soup(html)
            try:
                name_el = soup.select_one("h1.x-item-title__mainTitle span")
                if not name_el:
                    return None
                name = name_el.get_text(strip=True)

                price_el = soup.select_one(".x-price-primary span.ux-textspans")
                if not price_el:
                    return None
                price = self._parse_price(price_el.get_text())
                if price is None:
                    return None

                avail_el = soup.select_one(".d-quantity__availability")
                availability = "in_stock"
                if avail_el and "sold" in avail_el.get_text(strip=True).lower():
                    availability = "out_of_stock"

                img_el = soup.select_one(".ux-image-magnify__image--original, img.img-responsive")
                image_url = img_el.get("src") if img_el else None

                seller_el = soup.select_one(".x-sellercard-atf__data span.ux-textspans--BOLD")
                seller_name = seller_el.get_text(strip=True) if seller_el else None

                shipping_el = soup.select_one(".ux-labels-values__values .ux-textspans")
                shipping_cost = None
                if shipping_el:
                    sh_text = shipping_el.get_text(strip=True).lower()
                    shipping_cost = 0.0 if "free" in sh_text else self._parse_price(sh_text)

                return ScrapedProduct(
                    store_name=self.store_name,
                    store_domain=self.store_domain,
                    product_url=url,
                    name=name,
                    price=price,
                    currency="USD",
                    availability=availability,
                    image_url=image_url,
                    seller_name=seller_name,
                    shipping_cost=shipping_cost,
                )
            except Exception as exc:
                logger.error("Failed to scrape eBay product %s: %s", url, exc)
                return None
