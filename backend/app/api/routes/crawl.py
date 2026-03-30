import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.models.product import CrawlJob, CrawlStatus
from app.schemas.product import CrawlRequest, CrawlJobOut
from app.workers.tasks import crawl_query, crawl_urls
from app.telemetry.otel import get_tracer

router = APIRouter(prefix="/crawl", tags=["crawl"])
tracer = get_tracer("api.crawl")


@router.post("", response_model=CrawlJobOut, status_code=202)
async def trigger_crawl(request: CrawlRequest, db: AsyncSession = Depends(get_db)):
    """Trigger a crawl job. Returns immediately with the job object."""
    with tracer.start_as_current_span("api.trigger_crawl", attributes={"query": request.query}):
        job = CrawlJob(
            id=uuid.uuid4(),
            query=request.query,
            urls=json.dumps(request.urls) if request.urls else None,
            status=CrawlStatus.PENDING,
        )
        db.add(job)
        await db.flush()

        if request.urls:
            crawl_urls.apply_async(args=[str(job.id), request.query, request.urls], queue="crawl")
        else:
            crawl_query.apply_async(args=[str(job.id), request.query], queue="crawl")

        return job


@router.get("/{job_id}", response_model=CrawlJobOut)
async def get_crawl_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job


@router.get("/{job_id}/stream")
async def stream_crawl_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Server-Sent Events endpoint — streams job status updates to the frontend.
    The frontend subscribes and receives updates until the job completes.
    """
    async def event_generator():
        import asyncio
        for _ in range(60):  # Max 60 polls (60s)
            result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                yield f"data: {json.dumps({'error': 'not found'})}\n\n"
                break

            payload = {
                "status": job.status.value,
                "results_count": job.results_count,
                "completed_at": str(job.completed_at) if job.completed_at else None,
                "error": job.error_message,
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if job.status in (CrawlStatus.COMPLETED, CrawlStatus.FAILED):
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
