from pydantic import AnyHttpUrl, EmailStr, field_validator
from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any, Union
from functools import lru_cache
import secrets
import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nova Search"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    ELASTICSEARCH_HOSTS: List[str] = ["http://localhost:9200"]
    REDIS_URL: str = "redis://localhost:6379"
    
    # Search Engine
    MAX_SEARCH_RESULTS: int = 100
    CACHE_EXPIRY: int = 3600
    
    # Crawler Settings
    CRAWLER_WORKERS: int = 4
    CRAWL_DELAY: int = 1
    MAX_PAGES_PER_DOMAIN: int = 1000
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_PORT: int = 9090
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Logging
    LOGGING: Dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json"
            }
        },
        "root": {
            "handlers": ["console"],
            "level": "INFO"
        }
    }

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = 'utf-8'

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            if field_name == "SECRET_KEY":
                return str(raw_val) if raw_val else secrets.token_urlsafe(32)
            return raw_val

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()