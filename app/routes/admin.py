
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from app.core.auth import verify_admin_token
from app.search.engine import SearchEngine
from app.crawler.manager import CrawlerManager

router = APIRouter(prefix="/api/admin", dependencies=[Depends(verify_admin_token)])

class IndexStats(BaseModel):
    total_documents: int
    last_update: str
    storage_size: str

@router.get("/stats", response_model=IndexStats)
async def get_stats(
    search_engine: SearchEngine = Depends(lambda: SearchEngine())
):
    try:
        return await search_engine.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reindex")
async def reindex(
    search_engine: SearchEngine = Depends(lambda: SearchEngine())
):
    try:
        task_id = await search_engine.start_reindex()
        return {"status": "started", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear-cache")
async def clear_cache(
    search_engine: SearchEngine = Depends(lambda: SearchEngine())
):
    try:
        await search_engine.clear_cache()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))