from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Optional
from nova.app.search.engine import SearchEngine
from nova.app.core.config import settings
from nova.app.crawler.manager import CrawlerManager
from pydantic import BaseModel, HttpUrl
from nova.app.crawler.crawler import WebCrawler
from nova.app.search.engine import SearchEngine

router = APIRouter(prefix="/api/v1")
search_engine = SearchEngine()
crawler = WebCrawler()


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

@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100)
) -> Dict:
    """Search endpoint"""
    try:
        results = await search_engine.search(q, page=page, per_page=per_page)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
async def get_crawler_manager():
    from nova.app.crawler.manager import CrawlerManager
    return CrawlerManager()

@router.post("/crawl")
async def start_crawl(
    urls: List[str],
    crawler: CrawlerManager = Depends(get_crawler_manager)
) -> Dict:
    try:
        await crawler.start_crawling(urls)
        return {"status": "success", "message": "Crawl started"}
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