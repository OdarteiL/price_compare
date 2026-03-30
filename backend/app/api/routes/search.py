import uuid
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import CrawlJob, CrawlStatus
from app.schemas.product import SearchRequest, ProductSummary, CrawlJobOut
from app.services.comparison_service import ComparisonService
from app.workers.tasks import crawl_query
from app.telemetry.otel import get_tracer

router = APIRouter(prefix="/search", tags=["search"])
tracer = get_tracer("api.search")
comparison_svc = ComparisonService()


@router.post("", response_model=dict)
async def search_products(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Search for products by keyword.
    If crawl_fresh=True, triggers a background crawl and returns a job ID
    alongside any cached results. Subsequent polling of /crawl/{job_id} shows status.
    """
    with tracer.start_as_current_span("api.search", attributes={"query": request.query}):
        # Return cached/existing results immediately
        results = await comparison_svc.search_products(db, request.query, request.max_results)

        job_id = None
        if request.crawl_fresh or not results:
            job = CrawlJob(
                id=uuid.uuid4(),
                query=request.query,
                status=CrawlStatus.PENDING,
            )
            db.add(job)
            await db.flush()
            crawl_query.apply_async(args=[str(job.id), request.query], queue="crawl")
            job_id = str(job.id)

        return {
            "query": request.query,
            "results": results,
            "total": len(results),
            "crawl_job_id": job_id,
        }
