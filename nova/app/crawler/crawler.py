import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from nova.app.crawler.robots import RobotsParser
from datetime import datetime
import logging
import json
import hashlib
from typing import Set, Dict, List
import re
from concurrent.futures import ThreadPoolExecutor
import nltk
from nltk.tokenize import sent_tokenize
from nova.app.storage.metadata import MetadataExtractor

class WebCrawler:
    def __init__(self, max_pages: int = 1000, max_depth: int = 3):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.visited_urls: Set[str] = set()
        self.url_queue: asyncio.Queue = asyncio.Queue()
        self.robots_parser = RobotsParser()
        self.metadata_extractor = MetadataExtractor()
        self.session = None
        self.download_delay = 1  # Respect websites by waiting between requests
        
        # Initialize NLTK
        nltk.download('punkt')
        nltk.download('averaged_perceptron_tagger')
        
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={'User-Agent': 'NovaSearchBot/1.0 (+http://novasearch.com/bot)'}
            )

    async def crawl(self, start_urls: List[str]):
        await self.init_session()
        
        # Initialize queue with start URLs
        for url in start_urls:
            await self.url_queue.put((url, 0))  # (url, depth)

        # Create worker tasks
        workers = [
            asyncio.create_task(self.worker())
            for _ in range(5)  # Number of parallel workers
        ]

        # Wait for all workers to complete
        await asyncio.gather(*workers)

    async def worker(self):
        while True:
            try:
                url, depth = await self.url_queue.get()
                
                if depth > self.max_depth or len(self.visited_urls) >= self.max_pages:
                    self.url_queue.task_done()
                    continue

                if url in self.visited_urls or not self.robots_parser.can_fetch(url):
                    self.url_queue.task_done()
                    continue

                # Crawl the page
                await self.process_url(url, depth)
                
                # Respect robots.txt delay
                await asyncio.sleep(self.download_delay)
                
                self.url_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error processing {url}: {str(e)}")
                self.url_queue.task_done()

    async def process_url(self, url: str, depth: int):
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return

                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')

                # Extract and store content
                content = self.extract_content(soup)
                metadata = self.metadata_extractor.extract(soup, url)
                
                # Store the processed data
                self.store_page_data(url, content, metadata)
                
                # Add to visited urls
                self.visited_urls.add(url)

                # Extract and queue new URLs
                await self.extract_and_queue_links(soup, url, depth)

        except Exception as e:
            logging.error(f"Error fetching {url}: {str(e)}")

    def extract_content(self, soup) -> Dict:
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'iframe']):
            element.decompose()

        # Extract main content
        main_content = ''
        content_areas = soup.find_all(['article', 'main', 'div'], class_=re.compile(r'content|article|post'))
        
        if content_areas:
            main_content = ' '.join(area.get_text(strip=True) for area in content_areas)
        else:
            main_content = soup.get_text(strip=True)

        # Extract important sentences
        sentences = sent_tokenize(main_content)
        important_sentences = self.extract_important_sentences(sentences)

        return {
            'title': self.extract_title(soup),
            'description': self.extract_description(soup),
            'main_content': main_content,
            'summary': ' '.join(important_sentences[:3]),
            'keywords': self.extract_keywords(main_content)
        }

    def store_page_data(self, url: str, content: Dict, metadata: Dict):
        page_data = {
            'url': url,
            'crawled_at': datetime.utcnow().isoformat(),
            'content': content,
            'metadata': metadata
        }

        # Generate unique ID for the page
        page_id = hashlib.sha256(url.encode()).hexdigest()

        # Save to JSON file (in production, use a proper database)
        with open(f'data/pages/{page_id}.json', 'w') as f:
            json.dump(page_data, f)

    async def extract_and_queue_links(self, soup, base_url: str, depth: int):
        links = soup.find_all('a', href=True)
        
        for link in links:
            url = urljoin(base_url, link['href'])
            
            # Filter URLs
            if self.should_crawl_url(url):
                await self.url_queue.put((url, depth + 1))

    def should_crawl_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.scheme in ('http', 'https') and
            not any(ext in url.lower() for ext in ['.pdf', '.jpg', '.png', '.gif']) and
            '#' not in url
        )

    def extract_important_sentences(self, sentences: List[str]) -> List[str]:
        # Simple importance scoring based on sentence length and keywords
        scored_sentences = []
        important_keywords = {'key', 'important', 'significant', 'primary', 'essential'}
        
        for sentence in sentences:
            score = len(sentence.split())  # Basic length score
            words = set(sentence.lower().split())
            score += sum(2 for word in words if word in important_keywords)
            scored_sentences.append((score, sentence))
        
        return [s[1] for s in sorted(scored_sentences, reverse=True)]
