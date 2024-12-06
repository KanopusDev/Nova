from fastapi import FastAPI, HTTPException, Request, Depends
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import make_wsgi_app
import sentry_sdk
from nova.app.core.config import settings
from nova.app.core.monitoring import MetricsMiddleware
from nova.app.routes import api, admin
from nova.app.search.engine import SearchEngine
import uvicorn
import logging
import asyncio
from datetime import datetime
import os

# Configure logging
logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger(__name__)

# Initialize Sentry
sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT)
search_engine = SearchEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up application...")
    # Start background tasks
    crawler_task = asyncio.create_task(start_background_jobs())
    
    yield  # Application running
    
    # Shutdown
    logger.info("Shutting down application...")
    crawler_task.cancel()
    try:
        await crawler_task
    except asyncio.CancelledError:
        pass



app = FastAPI(
    title="Nova Search Engine",
    description="Production-grade search engine API",
    version="1.0.0",
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None
)

# Add middleware
app.add_middleware(MetricsMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # Updated from ALLOWED_ORIGINS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "nova/app/static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "nova/app/templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)


# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static_files")

# Initialize templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals.update({
    "current_year": lambda: datetime.now().year,
    "static_url": lambda path: f"/static/{path}"  # Helper for static URLs
})
# Include routers
app.include_router(api.router)
app.include_router(admin.router)

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("pages/index.html", {"request": request})


@app.get("/search")
async def search_page(request: Request, q: str = "", page: int = 1):
    try:
        if not q:
            return templates.TemplateResponse(
                "pages/search.html",
                {"request": request, "query": q, "results": [], "total_results": 0}
            )
        
        results = await search_engine.search(q, page=page)
        if not results.get("results"):
            return templates.TemplateResponse(
                "pages/search.html",
                {
                    "request": request,
                    "query": q,
                    "results": [],
                    "total_results": 0,
                    "error": "No results found or search service unavailable"
                }
            )
            
        return templates.TemplateResponse(
            "pages/search.html",
            {
                "request": request,
                "query": q,
                "results": results["results"],
                "total_results": results["total"],
                "current_page": page,
                "time_taken": results.get("time_taken", 0)
            }
        )
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return templates.TemplateResponse(
            "pages/error.html",
            {"request": request, "error": "Search service unavailable"}
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": app.version}


async def start_background_jobs():
    # Start crawler manager
    from nova.app.crawler.manager import CrawlerManager
    crawler = CrawlerManager()
    await crawler.schedule_crawls()



if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        log_level="info",
        reload=settings.ENVIRONMENT == "development"
    )