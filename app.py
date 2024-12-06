from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_wsgi_app
import sentry_sdk
from app.core.config import settings
from app.core.monitoring import MetricsMiddleware
from app.routes import api, admin
import uvicorn
import logging
import asyncio

# Configure logging
logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger(__name__)

# Initialize Sentry
sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT)

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
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(v1.router)
app.include_router(admin.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": app.version}

@app.on_event("startup")
async def startup_event():
    # Start background tasks
    asyncio.create_task(start_background_jobs())

@app.on_event("shutdown")
async def shutdown_event():
    # Cleanup resources
    logger.info("Shutting down application...")

async def start_background_jobs():
    # Start crawler manager
    from app.crawler.manager import CrawlerManager
    crawler = CrawlerManager()
    asyncio.create_task(crawler.schedule_crawls())

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        log_level="info",
        reload=settings.ENVIRONMENT == "development"
    )