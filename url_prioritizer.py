from typing import List, Dict
from urllib.parse import urlparse
import re
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import redis
from config import REDIS_URL

class URLPrioritizer:
    def __init__(self):
        self.priority_patterns = [
            (r'/article/', 0.8),
            (r'/blog/', 0.7),
            (r'/news/', 0.9),
            (r'/product/', 0.6)
        ]
        self.redis_client = redis.from_url(REDIS_URL)
        self.model = self._load_or_create_model()
        
    def prioritize_urls(self, urls: List[str]) -> List[Dict]:
        cached_results = self._get_cached_priorities(urls)
        uncached_urls = [url for url in urls if url not in cached_results]
        
        if uncached_urls:
            new_priorities = self._calculate_priorities(uncached_urls)
            self._cache_priorities(new_priorities)
            cached_results.update(new_priorities)
            
        return [{'url': url, 'priority': cached_results[url]} for url in urls]

    def _get_cached_priorities(self, urls: List[str]) -> Dict:
        return {url: float(score) for url, score in 
                zip(urls, self.redis_client.mget(urls)) if score}

    def _cache_priorities(self, priorities: Dict):
        pipeline = self.redis_client.pipeline()
        for url, priority in priorities.items():
            pipeline.setex(url, 3600, str(priority))  # Cache for 1 hour
        pipeline.execute()

    def _load_or_create_model(self):
        try:
            return joblib.load('models/url_priority_model.joblib')
        except:
            return RandomForestClassifier(n_estimators=100)
        
    def calculate_priority(self, url: str) -> float:
        base_priority = 0.5
        
        # Check against priority patterns
        for pattern, score in self.priority_patterns:
            if re.search(pattern, url):
                base_priority = max(base_priority, score)
                
        # Adjust priority based on URL depth
        depth = url.count('/')
        depth_penalty = max(0, (depth - 3) * 0.1)
        
        return max(0.1, base_priority - depth_penalty)