
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from pydantic import BaseModel, HttpUrl
from app.search.engine import SearchEngine
from app.crawler.manager import CrawlerManager
from app.core.monitoring import SEARCH_REQUESTS, SEARCH_LATENCY
import time

router = APIRouter(prefix="/api/v1")

class SearchFilters(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    categories: Optional[List[str]] = None

class SearchResponse(BaseModel):
    results: List[dict]
    total: int
    page: int
    total_pages: int
    suggestions: Optional[List[str]] = None

class CrawlRequest(BaseModel):
    urls: List[HttpUrl]
    max_depth: Optional[int] = 3

@router.get("/search", response_model=SearchResponse)
async def search(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    filters: Optional[SearchFilters] = None,
    search_engine: SearchEngine = Depends(lambda: SearchEngine())
):
    start_time = time.time()
    try:
        SEARCH_REQUESTS.inc()
        results = await search_engine.search(query, page, filters.dict() if filters else None)
        SEARCH_LATENCY.observe(time.time() - start_time)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/crawl")
async def start_crawl(
    request: CrawlRequest,
    crawler: CrawlerManager = Depends(lambda: CrawlerManager())
):
    try:
        task_id = await crawler.start_crawling(request.urls)
        return {"status": "started", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crawl/{task_id}")
async def get_crawl_status(
    task_id: str,
    crawler: CrawlerManager = Depends(lambda: CrawlerManager())
):
    status = await crawler.get_crawl_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status