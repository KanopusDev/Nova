from pydantic import BaseSettings
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Database
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Search Engine
    MAX_SEARCH_RESULTS: int = 100
    CACHE_TIMEOUT: int = 300
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN")
    LOG_LEVEL: str = "INFO"
    
    # Crawler Settings
    USER_AGENT: str = "NovaSearchBot/1.0"
    CRAWL_DELAY: int = 1
    MAX_PAGES: int = 10000
    
    class Config:
        env_file = ".env"

CONFIG = Settings()