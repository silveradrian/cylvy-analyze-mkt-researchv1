"""Configuration settings for Keyword Metrics Service"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration"""
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )
    
    # Service configuration
    port: int = int(os.getenv("PORT", "8080"))
    environment: str = "development"
    
    # GCP Configuration
    gcp_project: str
    
    # Google Ads Configuration
    google_ads_developer_token: str
    google_ads_client_id: str
    google_ads_client_secret: str
    google_ads_refresh_token: str
    google_ads_login_customer_id: str
    google_ads_customer_id: str
    
    # Database Configuration
    database_url: str
    
    # BigQuery Configuration
    bigquery_dataset: str = "cylvy_analytics"
    bigquery_table: str = "keyword_metrics"
    
    # Pub/Sub Configuration  
    pubsub_topic: str = "keyword-metrics-events"
    pubsub_topic_metrics_requested: str = "keyword.metrics.requested"
    pubsub_topic_metrics_completed: str = "keyword.metrics.completed.v1"
    pubsub_subscription: str = "keyword-metrics-service"
    enable_pubsub: bool = True
    
    # Cache Configuration
    cache_ttl: int = 3600  # 1 hour
    max_cache_size: int = 1000  # Maximum number of cached items
    
    # Rate Limiting
    google_ads_qps: int = 5  # Queries per second
    max_concurrent_requests: int = 10  # Maximum concurrent requests
    
    # Batch Processing
    batch_size: int = 100  # Number of keywords to process per batch
    
    # Client Context Service
    client_context_url: str = "http://client-context-service:8080"
    enable_bigquery: bool = True


# Create settings instance
settings = Settings() 