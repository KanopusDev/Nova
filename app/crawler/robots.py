import urllib.robotparser
import aiohttp
import asyncio
from urllib.parse import urlparse
import logging
from typing import Dict
import time
import redis
from app.core.config import REDIS_URL

class RobotsParser:
    def __init__(self):
        self.parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self.cache_time = 3600  # Cache robots.txt for 1 hour
        self.last_checked = {}
        self.redis_client = redis.from_url(REDIS_URL)
        self.session = None

    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def can_fetch(self, url: str) -> bool:
        try:
            cached = await self._get_cached_result(url)
            if cached is not None:
                return cached

            result = await self._fetch_and_check(url)
            await self._cache_result(url, result)
            return result

        except Exception as e:
            logging.error(f"Robots check error: {str(e)}")
            return False

    async def _fetch_and_check(self, url: str) -> bool:
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Check if we need to update the cached parser
        if self._should_update_parser(base_url):
            await self._update_parser(base_url)

        parser = self.parsers.get(base_url)
        if parser:
            return parser.can_fetch("NovaSearchBot/1.0", url)
        
        return True  # If no robots.txt, assume allowed

    async def _get_cached_result(self, url: str) -> bool:
        result = await self.redis_client.get(f"robots:{url}")
        return bool(int(result)) if result else None

    def _should_update_parser(self, base_url: str) -> bool:
        last_check = self.last_checked.get(base_url, 0)
        return time.time() - last_check > self.cache_time

    async def _update_parser(self, base_url: str):
        try:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(f"{base_url}/robots.txt")
            await parser.read()
            self.parsers[base_url] = parser
            self.last_checked[base_url] = time.time()
        except Exception as e:
            logging.error(f"Error updating robots parser for {base_url}: {str(e)}")