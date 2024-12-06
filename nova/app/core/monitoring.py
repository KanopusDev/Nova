import structlog
from prometheus_client import Counter, Histogram, Gauge
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Metrics
SEARCH_REQUESTS = Counter('search_requests_total', 'Total search requests')
SEARCH_LATENCY = Histogram('search_latency_seconds', 'Search request latency')
CACHE_HITS = Counter('cache_hits_total', 'Total cache hits')
CRAWL_ERRORS = Counter('crawl_errors_total', 'Total crawling errors')
DB_CONNECTIONS = Gauge('db_connections', 'Number of database connections')

# Structured logging
logger = structlog.get_logger()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        # Record metrics
        request_duration = time.time() - start_time
        SEARCH_LATENCY.observe(request_duration)
        
        if request.url.path.startswith("/api/v1/search"):
            SEARCH_REQUESTS.inc()
        
        return response

def log_error(error: Exception, context: dict = None):
    logger.error("error_occurred",
                error_type=type(error).__name__,
                error_message=str(error),
                **context or {})
    CRAWL_ERRORS.inc()