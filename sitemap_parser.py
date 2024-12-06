import asyncio
import aiohttp
from typing import List, Set
import logging
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
import gzip
from io import BytesIO
from aiohttp import ClientTimeout
from ratelimit import limits, sleep_and_retry

class SitemapParser:
    def __init__(self):
        self.session = None
        self.parsed_urls: Set[str] = set()
        self.timeout = ClientTimeout(total=30)
        self.rate_limit = 10  # requests per second

    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={'User-Agent': 'NovaSearchBot/1.0 (+http://novasearch.com/bot)'}
            )

    async def parse_multiple(self, seed_urls: List[str]) -> List[str]:
        """Parse multiple sitemaps from seed URLs"""
        await self.init_session()
        all_urls = set()

        try:
            tasks = [self.parse_sitemap(url) for url in seed_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for urls in results:
                if isinstance(urls, set):  # Filter out exceptions
                    all_urls.update(urls)

        except Exception as e:
            logging.error(f"Error parsing multiple sitemaps: {str(e)}")
        finally:
            await self.session.close()

        return list(all_urls)

    @sleep_and_retry
    @limits(calls=10, period=1)  # Rate limit: 10 calls per second
    async def parse_sitemap(self, url: str) -> Set[str]:
        """Parse a single sitemap URL"""
        urls = set()
        try:
            if url in self.parsed_urls:
                return urls

            self.parsed_urls.add(url)
            
            # Fetch sitemap content
            async with self.session.get(url, timeout=self.timeout) as response:
                if response.status != 200:
                    return urls

                # Add compression handling
                if response.headers.get('Content-Encoding') == 'br':
                    import brotli
                    content = await response.read()
                    return brotli.decompress(content).decode('utf-8')

                content = await self._get_content(response)
                if not content:
                    return urls

                # Parse XML content
                root = ET.fromstring(content)
                
                # Handle sitemap index files
                if 'sitemapindex' in root.tag:
                    tasks = []
                    for sitemap in root.findall('.//{*}loc'):
                        sitemap_url = sitemap.text.strip()
                        tasks.append(self.parse_sitemap(sitemap_url))
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, set):
                            urls.update(result)
                
                # Handle regular sitemaps
                else:
                    for url_elem in root.findall('.//{*}loc'):
                        page_url = url_elem.text.strip()
                        urls.add(page_url)

        except asyncio.TimeoutError:
            logging.error(f"Timeout while fetching {url}")
            return set()
        except Exception as e:
            logging.error(f"Error parsing sitemap {url}: {str(e)}")
            return set()

        return urls

    async def _get_content(self, response) -> str:
        """Handle different content encodings"""
        try:
            if response.headers.get('Content-Type', '').endswith('gzip'):
                content = await response.read()
                with gzip.GzipFile(fileobj=BytesIO(content)) as gz:
                    return gz.read().decode('utf-8')
            return await response.text()
        except Exception as e:
            logging.error(f"Error reading content: {str(e)}")
            return ''

    def _is_valid_url(self, url: str) -> bool:
        """Basic URL validation"""
        return url.startswith(('http://', 'https://'))