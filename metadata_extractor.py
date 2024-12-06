from bs4 import BeautifulSoup
from typing import Dict
import re
from transformers import pipeline
import numpy as np
from concurrent.futures import ThreadPoolExecutor

class MetadataExtractor:
    def __init__(self):
        self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        self.classifier = pipeline("zero-shot-classification")
        self.executor = ThreadPoolExecutor(max_workers=4)

    def extract(self, soup: BeautifulSoup, url: str) -> Dict:
        basic_metadata = {
            'title': self._extract_title(soup),
            'meta_description': self._extract_meta_description(soup),
            'meta_keywords': self._extract_meta_keywords(soup),
            'og_data': self._extract_og_data(soup),
            'schema_data': self._extract_schema_data(soup),
            'author': self._extract_author(soup),
            'published_date': self._extract_published_date(soup),
            'language': self._extract_language(soup)
        }
        
        # Add AI-powered metadata
        content = self._extract_main_content(soup)
        ai_metadata = self._extract_ai_metadata(content)
        
        return {**basic_metadata, **ai_metadata}

    def _extract_title(self, soup: BeautifulSoup) -> str:
        title = soup.find('title')
        return title.get_text() if title else ''

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        return meta_desc['content'] if meta_desc else ''

    def _extract_meta_keywords(self, soup: BeautifulSoup) -> str:
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        return meta_keywords['content'] if meta_keywords else ''

    def _extract_og_data(self, soup: BeautifulSoup) -> Dict:
        og_data = {}
        for tag in soup.find_all('meta', attrs={'property': re.compile(r'^og:')}):
            og_data[tag['property']] = tag['content']
        return og_data

    def _extract_schema_data(self, soup: BeautifulSoup) -> Dict:
        schema_data = {}
        for tag in soup.find_all('script', attrs={'type': 'application/ld+json'}):
            schema_data.update(json.loads(tag.string))
        return schema_data

    def _extract_author(self, soup: BeautifulSoup) -> str:
        author = soup.find('meta', attrs={'name': 'author'})
        return author['content'] if author else ''

    def _extract_published_date(self, soup: BeautifulSoup) -> str:
        pub_date = soup.find('meta', attrs={'property': 'article:published_time'})
        return pub_date['content'] if pub_date else ''

    def _extract_language(self, soup: BeautifulSoup) -> str:
        html_tag = soup.find('html')
        return html_tag['lang'] if html_tag and 'lang' in html_tag.attrs else ''

    def _extract_ai_metadata(self, content: str) -> Dict:
        summary = self.executor.submit(
            self.summarizer, content[:1024], max_length=130, min_length=30
        ).result()

        categories = self.executor.submit(
            self.classifier,
            content,
            candidate_labels=["technology", "business", "science", "entertainment"]
        ).result()

        return {
            'ai_summary': summary[0]['summary_text'],
            'categories': categories['labels'],
            'category_scores': categories['scores']
        }