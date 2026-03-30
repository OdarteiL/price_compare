from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics_service import AnalyticsService
from app.telemetry.otel import get_tracer

router = APIRouter(prefix="/analytics", tags=["analytics"])
tracer = get_tracer("api.analytics")
analytics_svc = AnalyticsService()


@router.get("/stats")
async def platform_stats(db: AsyncSession = Depends(get_db)):
    with tracer.start_as_current_span("api.platform_stats"):
        return await analytics_svc.get_platform_stats(db)


@router.get("/cheapest-stores")
async def cheapest_stores(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    with tracer.start_as_current_span("api.cheapest_stores"):
        return await analytics_svc.get_cheapest_stores(db, limit)


@router.get("/price-trend/{product_id}")
async def price_trend(
    product_id: str,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    with tracer.start_as_current_span("api.price_trend", attributes={"product_id": product_id}):
        return await analytics_svc.get_price_trend(db, product_id, days)
