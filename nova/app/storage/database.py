from motor.motor_asyncio import AsyncIOMotorClient
import redis
from typing import Dict, List
import logging
import json
from datetime import datetime
from nova.app.core.config import settings

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGODB_URL)  # Use settings
        self.db = self.client.nova_search
        self.redis = redis.from_url(settings.REDIS_URL)  # Use settings
        self.cache_timeout = 3600  # 1 hour

    async def index_page(self, page_data: Dict):
        try:
            # Add vector embedding
            page_data['embedding'] = self._generate_embedding(
                f"{page_data['title']} {page_data['content']}"
            )

            # Add timestamps
            page_data['created_at'] = datetime.utcnow()
            page_data['updated_at'] = datetime.utcnow()

            # Create compound indexes
            await self.db.pages.create_indexes([
                [('url', 1)],
                [('embedding', '2dsphere')],
                [('created_at', -1)],
                [('title', 'text'), ('content', 'text')]
            ])

            result = await self.db.pages.update_one(
                {'url': page_data['url']},
                {'$set': page_data},
                upsert=True
            )

            # Invalidate cache
            self._invalidate_cache(page_data['url'])
            
            return result

        except Exception as e:
            logging.error(f"Database indexing error: {str(e)}", exc_info=True)
            raise

    async def get_by_url(self, url: str) -> Dict:
        # Try cache first
        cached = self._get_from_cache(url)
        if cached:
            return cached

        result = await self.db.pages.find_one({'url': url})
        if result:
            self._set_in_cache(url, result)
        return result

    def _get_from_cache(self, key: str) -> Dict:
        try:
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logging.warning(f"Cache get error: {str(e)}")
            return None

    def _set_in_cache(self, key: str, value: Dict):
        try:
            self.redis.setex(
                key,
                self.cache_timeout,
                json.dumps(value)
            )
        except Exception as e:
            logging.warning(f"Cache set error: {str(e)}")

    def _invalidate_cache(self, key: str):
        try:
            self.redis.delete(key)
        except Exception as e:
            logging.warning(f"Cache invalidation error: {str(e)}")

    async def search(self, query: str, page: int = 1, per_page: int = 10) -> List[Dict]:
        try:
            cursor = self.db.pages.find(
                {'$text': {'$search': query}},
                {'score': {'$meta': 'textScore'}}
            ).sort([
                ('score', {'$meta': 'textScore'}),
                ('indexed_at', -1)
            ]).skip((page - 1) * per_page).limit(per_page)
            
            return await cursor.to_list(length=per_page)
            
        except Exception as e:
            logging.error(f"Search error: {str(e)}")
            return []