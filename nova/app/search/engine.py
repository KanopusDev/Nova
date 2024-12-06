from elasticsearch import Elasticsearch, ConnectionError
from datetime import datetime
import logging
from transformers import AutoTokenizer, AutoModel
import torch
from typing import List, Dict, Optional
import numpy as np
from nova.app.core.config import settings
import time
import pymongo

logger = logging.getLogger(__name__)

class SearchEngine:
    def __init__(self):
        self.es = None
        self.ml_enabled = False
        self.connect()
        self._init_ml()

    def connect(self):
        try:
            self.es = Elasticsearch(
                settings.ELASTICSEARCH_HOSTS,
                verify_certs=False,
                timeout=30,
                retry_on_timeout=True,
                max_retries=3
            )
            if not self.es.ping():
                raise ConnectionError("Failed to ping Elasticsearch")
            logger.info("Successfully connected to Elasticsearch")
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {str(e)}")
            self.es = None

    def _init_ml(self):
        """Initialize ML models if available"""
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            self.tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')
            self.model = AutoModel.from_pretrained('distilbert-base-uncased')
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
            self.ml_enabled = True
            logger.info("ML features enabled")
        except Exception as e:
            logger.warning(f"ML features disabled: {str(e)}")
            self.ml_enabled = False

    async def search(self, query: str, page: int = 1, per_page: int = 10) -> Dict:
        if not self.es:
            try:
                self.connect()
            except Exception as e:
                logger.error(f"Failed to reconnect to Elasticsearch: {str(e)}")
                return {"results": [], "total": 0, "time_taken": 0}

        try:
            start_time = time.time()
            body = self._build_query(query)
            body.update({
                "from": (page - 1) * per_page,
                "size": per_page
            })

            response = await self.es.search(index="web_pages", body=body)
            results = self._process_results(response)
            results["time_taken"] = time.time() - start_time
            
            return results

        except ConnectionError as e:
            logger.error(f"Elasticsearch connection error: {str(e)}")
            return {"results": [], "total": 0, "time_taken": 0}
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            raise

    def _build_query(self, query: str) -> Dict:
        """Build search query with or without ML features"""
        base_query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"title": {"query": query, "boost": 3}}},
                        {"match": {"content": {"query": query, "boost": 1}}}
                    ]
                }
            },
            "highlight": {
                "fields": {
                    "title": {},
                    "content": {"fragment_size": 150, "number_of_fragments": 3}
                }
            }
        }

        if self.ml_enabled:
            # Add ML-enhanced query components
            base_query = self._enhance_query_with_ml(base_query, query)

        return base_query

    async def _mongodb_fallback_search(self, query: str, page: int, per_page: int) -> Dict:
        """Fallback search using MongoDB text search"""
        try:
            if not self.mongo_client:
                return {"results": [], "total": 0, "time_taken": 0}

            db = self.mongo_client.nova_search
            start_time = time.time()
            
            cursor = db.pages.find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}}
            ).sort([
                ("score", {"$meta": "textScore"}),
                ("created_at", -1)
            ]).skip((page - 1) * per_page).limit(per_page)

            results = []
            async for doc in cursor:
                results.append({
                    "url": doc["url"],
                    "title": doc["title"],
                    "content": doc.get("content", "")[:200],
                    "score": doc["score"]
                })

            total = await db.pages.count_documents({"$text": {"$search": query}})
            time_taken = time.time() - start_time

            return {
                "results": results,
                "total": total,
                "time_taken": time_taken
            }
        except Exception as e:
            logger.error(f"MongoDB fallback search error: {str(e)}")
            return {"results": [], "total": 0, "time_taken": 0}

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generate BERT embedding for text"""
        with torch.no_grad():
            inputs = self.tokenizer(text, return_tensors="pt", 
                                  truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            return outputs.last_hidden_state.mean(dim=1).cpu().numpy()[0]

    def _process_results(self, response: Dict) -> Dict:
        """Process Elasticsearch response into searchable results"""
        results = []
        for hit in response['hits']['hits']:
            result = {
                'url': hit['_source']['url'],
                'title': hit['highlight'].get('title', [hit['_source']['title']])[0],
                'content': '...'.join(hit['highlight'].get('content', 
                    [hit['_source'].get('meta_description', hit['_source']['content'][:200])])),
                'score': hit['_score']
            }
            results.append(result)

        return {
            'results': results,
            'total': response['hits']['total']['value'],
        }

    async def get_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """Get search suggestions based on query"""
        try:
            body = {
                "suggest": {
                    "text": query,
                    "completion": {
                        "field": "suggest",
                        "size": limit,
                        "skip_duplicates": True,
                        "fuzzy": {
                            "fuzziness": "AUTO"
                        }
                    }
                }
            }
            response = await self.es.search(index="web_pages", body=body)
            return [
                suggestion['text'] 
                for suggestion in response['suggest']['completion'][0]['options']
            ]
        except Exception as e:
            logger.error(f"Suggestion error: {str(e)}")
            return []

    async def get_total_pages(self) -> int:
        """Get total number of indexed pages"""
        try:
            stats = await self.es.count(index="web_pages")
            return stats['count']
        except Exception as e:
            logger.error(f"Stats error: {str(e)}")
            return 0

    async def get_last_crawl_time(self) -> Optional[str]:
        """Get timestamp of last indexed page"""
        try:
            body = {
                "size": 1,
                "sort": [{"indexed_at": "desc"}],
                "_source": ["indexed_at"]
            }
            response = await self.es.search(index="web_pages", body=body)
            if response['hits']['hits']:
                return response['hits']['hits'][0]['_source']['indexed_at']
            return None
        except Exception as e:
            logger.error(f"Last crawl time error: {str(e)}")
            return None