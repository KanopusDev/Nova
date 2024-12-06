from typing import List
import asyncio
import structlog
from prometheus_client import Counter, Gauge
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import aiohttp
import logging
from nova.app.core.config import settings


logger = structlog.get_logger()
PAGES_CRAWLED = Counter('pages_crawled_total', 'Total pages crawled')
CRAWL_QUEUE_SIZE = Gauge('crawl_queue_size', 'Size of crawl queue')

class CrawlerManager:
    def __init__(self):
        from nova.app.crawler.crawler import WebCrawler
        from nova.app.crawler.url_prioritizer import URLPrioritizer
        from nova.app.crawler.sitemap import SitemapParser
        from nova.app.storage.database import Database
        
        self.crawler = WebCrawler()
        self.prioritizer = URLPrioritizer()
        self.sitemap_parser = SitemapParser()
        self.db = Database()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.queue = asyncio.Queue()

    async def start_crawling(self, seed_urls: List[str]):
        try:
            logger.info("starting_crawl", urls=seed_urls)
            
            # Initialize monitoring
            CRAWL_QUEUE_SIZE.set(len(seed_urls))
            
            # Use thread pool for CPU-intensive tasks
            with ThreadPoolExecutor() as pool:
                sitemap_urls = await self.sitemap_parser.parse_multiple(seed_urls)
                prioritized_urls = await asyncio.get_event_loop().run_in_executor(
                    pool, self.prioritizer.prioritize_urls, sitemap_urls
                )
            
            await self._process_urls(prioritized_urls)
            
        except Exception as e:
            logger.error("crawl_error", error=str(e))
            raise

    async def _process_urls(self, urls: List[dict]):
        for url_data in urls:
            await self.queue.put(url_data)
            CRAWL_QUEUE_SIZE.inc()

        workers = [
            asyncio.create_task(self._crawler_worker())
            for _ in range(settings.CRAWLER_WORKERS)  # Use settings instead of CONFIG
        ]
        
        await asyncio.gather(*workers)



    async def schedule_crawls(self):
        """Schedule periodic crawls based on site update frequency"""
        while True:
            try:
                # Get sites due for recrawl
                sites = await self.db.get_sites_for_recrawl()
                
                for site in sites:
                    await self.start_crawling([site['url']])
                    
                # Update crawl schedule
                await self.db.update_crawl_schedule(site['url'])
                
            except Exception as e:
                logging.error(f"Scheduling error: {str(e)}")
            
            await asyncio.sleep(3600)  # Check every hour

    async def index_crawled_data(self):
        """Index newly crawled data into search database"""
        try:
            # Get recently crawled pages
            new_pages = await self.db.get_unindexed_pages()
            
            # Process and index pages
            for page in new_pages:
                await self.db.index_page(page)
                
        except Exception as e:
            logging.error(f"Indexing error: {str(e)}")