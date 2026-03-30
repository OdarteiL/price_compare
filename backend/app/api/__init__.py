from fastapi import APIRouter
from app.api.routes import search, products, crawl, analytics

api_router = APIRouter()
api_router.include_router(search.router)
api_router.include_router(products.router)
api_router.include_router(crawl.router)
api_router.include_router(analytics.router)
