import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.product import ProductOut, PriceAnalysis
from app.services.comparison_service import ComparisonService
from app.telemetry.otel import get_tracer

router = APIRouter(prefix="/products", tags=["products"])
tracer = get_tracer("api.products")
comparison_svc = ComparisonService()


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    with tracer.start_as_current_span("api.get_product", attributes={"product_id": str(product_id)}):
        product = await comparison_svc.get_product_with_listings(db, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product


@router.get("/{product_id}/analysis", response_model=PriceAnalysis)
async def get_price_analysis(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    with tracer.start_as_current_span("api.price_analysis", attributes={"product_id": str(product_id)}):
        analysis = await comparison_svc.get_analysis(db, product_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Product not found or has no active listings")
        return analysis
