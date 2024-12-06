from elasticsearch import Elasticsearch
from datetime import datetime
import logging
from transformers import AutoTokenizer, AutoModel
import torch
from typing import List, Dict
import numpy as np

class SearchEngine:
    def __init__(self):
        self.es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
        
        # Initialize BERT model for semantic search
        self.tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/bert-base-nli-mean-tokens')
        self.model = AutoModel.from_pretrained('sentence-transformers/bert-base-nli-mean-tokens')
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

    def search(self, query: str, page: int = 1, per_page: int = 10) -> Dict:
        try:
            # Get semantic embedding for query
            query_embedding = self._get_embedding(query)

            body = {
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "should": [
                                    {"match": {"title": {"query": query, "boost": 3}}},
                                    {"match": {"content": {"query": query, "boost": 1}}},
                                    {"match": {"meta_description": {"query": query, "boost": 2}}},
                                    {"match": {"h1": {"query": query, "boost": 2}}},
                                    {"match": {"h2": {"query": query, "boost": 1.5}}}
                                ],
                                "must": [
                                    {"exists": {"field": "embedding"}}
                                ]
                            }
                        },
                        "script": {
                            # Combine semantic similarity with text matching
                            "source": "cosineSimilarity(params.query_vector, 'embedding') + _score * 0.5",
                            "params": {"query_vector": query_embedding.tolist()}
                        }
                    }
                },
                "highlight": {
                    "fields": {
                        "title": {},
                        "content": {}
                    }
                },
                "_source": ["url", "title", "meta_description", "content"],
                "from": (page - 1) * per_page,
                "size": per_page
            }

            response = self.es.search(index="web_pages", body=body)
            return self._process_results(response, query)

        except Exception as e:
            logging.error(f"Search error: {str(e)}", exc_info=True)
            raise

    def _get_embedding(self, text: str) -> np.ndarray:
        with torch.no_grad():
            inputs = self.tokenizer(text, return_tensors="pt", 
                                  truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            return outputs.last_hidden_state.mean(dim=1).cpu().numpy()[0]

    def _process_results(self, response: Dict, query: str) -> Dict:
        results = []
        for hit in response['hits']['hits']:
            result = self._format_result(hit)
            result['relevance'] = self._calculate_relevance(hit, query)
            results.append(result)
        
        return {
            'results': sorted(results, key=lambda x: x['relevance'], reverse=True),
            'total': response['hits']['total']['value']
        }

    def _format_result(self, hit: Dict) -> Dict:
        result = {
            'url': hit['_source']['url'],
            'title': hit['_source']['title'],
            'content': hit['_source'].get('meta_description') or hit['_source']['content'][:200] + '...',
            'relevance_score': hit['_score']
        }
        
        # Add highlighted snippets if available
        if 'highlight' in hit:
            if 'content' in hit['highlight']:
                result['content'] = '...'.join(hit['highlight']['content'])
            if 'title' in hit['highlight']:
                result['title'] = ''.join(hit['highlight']['title'])
        
        return result

    def _calculate_relevance(self, hit: Dict, query: str) -> float:
        # Placeholder for a more complex relevance calculation
        return hit['_score']