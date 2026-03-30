import uuid
from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field
from app.models.product import Availability, CrawlStatus


class PriceListingOut(BaseModel):
    id: uuid.UUID
    store_name: str
    store_domain: str
    product_url: str
    price: float
    original_price: float | None
    currency: str
    availability: Availability
    rating: float | None
    review_count: int | None
    shipping_cost: float | None
    seller_name: str | None
    scraped_at: datetime
    discount_percent: float | None = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context):
        if self.original_price and self.original_price > self.price:
            object.__setattr__(
                self,
                "discount_percent",
                round((1 - self.price / self.original_price) * 100, 1),
            )


class PriceHistoryPoint(BaseModel):
    store_domain: str
    price: float
    currency: str
    recorded_at: datetime

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    brand: str | None
    image_url: str | None
    created_at: datetime
    listings: list[PriceListingOut] = []

    model_config = {"from_attributes": True}


class ProductSummary(BaseModel):
    id: uuid.UUID
    name: str
    brand: str | None
    image_url: str | None
    best_price: float | None
    best_price_store: str | None
    currency: str
    listing_count: int

    model_config = {"from_attributes": True}


class PriceAnalysis(BaseModel):
    product_id: uuid.UUID
    product_name: str
    lowest_price: float
    highest_price: float
    average_price: float
    median_price: float
    best_deal: PriceListingOut
    savings_vs_highest: float
    savings_percent: float
    listings: list[PriceListingOut]
    price_history: list[PriceHistoryPoint]
    in_stock_count: int
    total_listing_count: int


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    max_results: int = Field(default=20, ge=1, le=100)
    crawl_fresh: bool = Field(default=False, description="Trigger a fresh crawl for this query")


class CrawlRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    urls: list[str] | None = Field(default=None, description="Specific product URLs to crawl")


class CrawlJobOut(BaseModel):
    id: uuid.UUID
    query: str
    status: CrawlStatus
    results_count: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
