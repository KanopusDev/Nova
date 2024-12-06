from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_wsgi_app, Counter, Histogram
from wsgiref.simple_server import make_server
import sentry_sdk
from config import CONFIG
from flask_limiter.util import get_remote_address
from flask_caching import Cache
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
import logging
from datetime import datetime
import redis
from database import Database
from crawler_manager import CrawlerManager
from typing import Optional
import asyncio

# Configure logging
logging.basicConfig(
    filename='search_engine.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize monitoring
sentry_sdk.init(dsn=CONFIG.SENTRY_DSN)
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests')
LATENCY = Histogram('http_request_duration_seconds', 'Request latency')

app = FastAPI(title="Nova Search Engine", version="1.0.0")

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Add API versioning
@app.get("/api/v1/search")
@LATENCY.time()
async def search_v1(
    query: str,
    page: int = 1,
    filters: dict = None,
    search_engine = Depends(get_search_engine)
):
    REQUEST_COUNT.inc()
    try:
        results = await search_engine.search(query, page, filters)
        return results
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=500, detail=str(e))

class EnhancedSearchEngine:
    def __init__(self):
        self.db = Database()
        self.crawler_manager = CrawlerManager()
        
    async def search(self, query: str, 
                    page: int = 1, 
                    filters: Optional[Dict] = None) -> Dict:
        try:
            # Get base search results
            results = await self.db.search(query, page)
            
            # Apply filters if any
            if filters:
                results = self.apply_filters(results, filters)
            
            # Get search suggestions
            suggestions = await self.get_search_suggestions(query)
            
            return {
                'results': results,
                'suggestions': suggestions,
                'page': page,
                'total_pages': await self.db.count_results(query)
            }
            
        except Exception as e:
            logging.error(f"Enhanced search error: {str(e)}")
            return {'error': str(e)}

# Initialize enhanced search engine
search_engine = EnhancedSearchEngine()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search')
@limiter.limit("10 per minute")
@cache.memoize(timeout=300)  # Cache results for 5 minutes
def search():
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'error': 'Empty query', 'results': []})

        # Log search query
        logging.info(f"Search query: {query} from IP: {get_remote_address()}")
        
        # Perform search
        results = search_engine.search(query)
        
        # Log analytics
        log_analytics(query, len(results))
        
        return jsonify({
            'status': 'success',
            'query': query,
            'count': len(results),
            'results': results
        })

    except Exception as e:
        logging.error(f"Error in search endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred during search',
            'results': []
        }), 500

@app.route('/api/search')
@limiter.limit("10 per minute")
@cache.memoize(timeout=300)
async def api_search():
    try:
        query = request.args.get('q', '').strip()
        page = int(request.args.get('page', 1))
        filters = request.args.get('filters', {})
        
        if not query:
            return jsonify({'error': 'Empty query'})
            
        results = await search_engine.search(query, page, filters)
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Start crawler in background
@app.before_first_request
def start_background_tasks():
    asyncio.create_task(search_engine.crawler_manager.schedule_crawls())

def log_analytics(query, result_count):
    try:
        analytics_data = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'result_count': result_count,
            'ip': get_remote_address()
        }
        # In production, you'd want to store this in a proper database
        logging.info(f"Analytics: {json.dumps(analytics_data)}")
    except Exception as e:
        logging.error(f"Analytics logging error: {str(e)}")

if __name__ == '__main__':
    app.run(debug=False)  # Set to False in production