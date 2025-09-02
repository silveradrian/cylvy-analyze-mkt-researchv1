"""
Application configuration using Pydantic Settings
"""
from typing import List, Optional, Union
from functools import lru_cache
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Cylvy Digital Landscape Analyzer"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(False, env="DEBUG")
    
    # Security
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field("HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DB_POOL_SIZE: int = Field(20, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(40, env="DB_MAX_OVERFLOW")
    
    # Redis
    REDIS_URL: str = Field("redis://localhost:6379", env="REDIS_URL")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(
        ["http://localhost:3000", "http://localhost:8000"],
        env="BACKEND_CORS_ORIGINS"
    )
    ALLOWED_HOSTS: List[str] = Field(["*"], env="ALLOWED_HOSTS")
    
    # Rate Limits (Default values, can be overridden per tenant)
    DEFAULT_SERP_DAILY_LIMIT: int = Field(2000, env="DEFAULT_SERP_DAILY_LIMIT")
    DEFAULT_SCRAPER_CONCURRENT_LIMIT: int = Field(50, env="DEFAULT_SCRAPER_CONCURRENT_LIMIT")
    DEFAULT_ANALYZER_CONCURRENT_LIMIT: int = Field(30, env="DEFAULT_ANALYZER_CONCURRENT_LIMIT")
    
# External API Keys (Fallback values for development)
    # In production, these are stored encrypted per deployment
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    SCALE_SERP_API_KEY: Optional[str] = Field(None, env="SCALE_SERP_API_KEY")
    SCRAPINGBEE_API_KEY: Optional[str] = Field(None, env="SCRAPINGBEE_API_KEY")
    COGNISM_API_KEY: Optional[str] = Field(None, env="COGNISM_API_KEY")
    YOUTUBE_API_KEY: Optional[str] = Field(None, env="YOUTUBE_API_KEY")
    
    # Google Ads API Configuration
    GOOGLE_ADS_DEVELOPER_TOKEN: Optional[str] = Field(None, env="GOOGLE_ADS_DEVELOPER_TOKEN")
    GOOGLE_ADS_CLIENT_ID: Optional[str] = Field(None, env="GOOGLE_ADS_CLIENT_ID")
    GOOGLE_ADS_CLIENT_SECRET: Optional[str] = Field(None, env="GOOGLE_ADS_CLIENT_SECRET")
    GOOGLE_ADS_REFRESH_TOKEN: Optional[str] = Field(None, env="GOOGLE_ADS_REFRESH_TOKEN")
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: Optional[str] = Field(None, env="GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    GOOGLE_ADS_CUSTOMER_ID: Optional[str] = Field(None, env="GOOGLE_ADS_CUSTOMER_ID")
    
    # Storage
    STORAGE_PATH: str = Field("/app/storage", env="STORAGE_PATH")
    
    # Feature Flags
    ENABLE_HISTORICAL_TRACKING: bool = Field(True, env="ENABLE_HISTORICAL_TRACKING")
    ENABLE_SCHEDULING: bool = Field(False, env="ENABLE_SCHEDULING")
    ENABLE_ADVANCED_ANALYTICS: bool = Field(True, env="ENABLE_ADVANCED_ANALYTICS")
    
    # Logging
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field("json", env="LOG_FORMAT")
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @validator("ALLOWED_HOSTS", pre=True)
    def assemble_allowed_hosts(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()

