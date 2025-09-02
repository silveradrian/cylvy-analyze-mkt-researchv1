"""Google Ads API client for keyword metrics"""

import asyncio
import os
import sys
from typing import List, Dict, Any, Optional
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf.json_format import MessageToDict
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from aiolimiter import AsyncLimiter

from app.config import settings
from app.models import KeywordMetric, KeywordSource

# Let the library use its default API version (v20 for google-ads==25.1.0)

logger = structlog.get_logger()


class GoogleAdsApiClient:
    """Async wrapper for Google Ads API"""
    
    def __init__(self):
        """Initialize Google Ads client"""
        # Rate limiter
        self.rate_limiter = AsyncLimiter(settings.google_ads_qps, 1.0)
        
        # Defer actual client creation until first use
        self.client = None
        self.customer_id = None
        self._client_initialized = False
    
    def _ensure_client_initialized(self):
        """Initialize the client if not already done"""
        if not self._client_initialized:
            try:
                # Load credentials directly from environment variables
                credentials = {
                    "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip(),
                    "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "").strip(),
                    "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip(),
                    "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip(),
                    "login_customer_id": os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").strip(),
                    "use_proto_plus": False,
                    "api_version": "v19"
                }
                
                # Log credential status (without exposing secrets)
                logger.info(
                    "Initializing Google Ads client",
                    dev_token_len=len(credentials["developer_token"]),
                    refresh_token_len=len(credentials["refresh_token"]),
                    client_id_len=len(credentials["client_id"]),
                    client_secret_len=len(credentials["client_secret"]),
                    login_customer_id=credentials["login_customer_id"]
                )
                
                # Create client
                self.client = GoogleAdsClient.load_from_dict(credentials)
                self.customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").strip()
                self._client_initialized = True
                
                logger.info("Google Ads client initialized successfully", customer_id=self.customer_id)
                
            except Exception as e:
                print(f"FATAL: Failed to initialize Google Ads client: {e}", file=sys.stderr)
                print(f"Exception type: {type(e).__name__}", file=sys.stderr)
                
                # Debug environment variables
                print("Environment variables check:", file=sys.stderr)
                for key in ["GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID", 
                           "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
                           "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "GOOGLE_ADS_CUSTOMER_ID"]:
                    value = os.getenv(key, "")
                    if value:
                        # Show first and last few chars for debugging
                        if len(value) > 20:
                            masked = f"{value[:8]}...{value[-8:]}"
                        else:
                            masked = "*" * len(value)
                        print(f"  {key}: {masked} (len={len(value)})", file=sys.stderr)
                    else:
                        print(f"  {key}: NOT SET", file=sys.stderr)
                        
                raise RuntimeError(f"Failed to initialize Google Ads client: {e}")
    
    @property
    def is_initialized(self) -> bool:
        """Check if client is properly initialized"""
        return self._client_initialized and self.client is not None
    
    @retry(
        retry=retry_if_exception_type(GoogleAdsException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get_keyword_metrics(
        self,
        keywords: List[str],
        language: str = "en",
        location: str = "2840",  # US geo code
        include_ideas: bool = False
    ) -> List[KeywordMetric]:
        """
        Fetch keyword metrics from Google Ads
        
        Args:
            keywords: List of keywords (max 10 per batch)
            language: Language code
            location: Geo target code
            include_ideas: Include related keyword ideas
            
        Returns:
            List of keyword metrics
        """
        # Ensure client is initialized before use
        self._ensure_client_initialized()
        
        if not self.is_initialized:
            raise RuntimeError("Google Ads client not initialized")

        async with self.rate_limiter:
            try:
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                metrics = await loop.run_in_executor(
                    None,
                    self._get_keyword_metrics_sync,
                    keywords,
                    language,
                    location,
                    include_ideas
                )
                
                logger.info(
                    "Retrieved keyword metrics",
                    count=len(metrics),
                    keywords_requested=len(keywords)
                )
                
                return metrics
                
            except GoogleAdsException as e:
                logger.error(
                    "Google Ads API error",
                    error=str(e),
                    failure=e.failure
                )
                raise
            except Exception as e:
                logger.error(
                    "Unexpected error getting keyword metrics",
                    error=str(e)
                )
                raise
    
    def _get_keyword_metrics_sync(
        self,
        keywords: List[str],
        language: str,
        location: str,
        include_ideas: bool
    ) -> List[KeywordMetric]:
        """
        Synchronous method to get keyword metrics
        """
        # This should already be initialized by the async wrapper
        if not self.is_initialized:
            raise RuntimeError("Google Ads client not initialized")

        keyword_plan_idea_service = self.client.get_service("KeywordPlanIdeaService")
        
        # Build request
        request = self.client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = self.customer_id
        
        # Set language
        # Convert language code to ID if needed
        language_id = "1000" if language == "en" else language
        language_rn = self.client.get_service("GoogleAdsService").language_constant_path(language_id)
        request.language = language_rn
        
        # Set location  
        location_rn = self.client.get_service("GoogleAdsService").geo_target_constant_path(location)
        request.geo_target_constants.append(location_rn)
        
        # Set network
        # For protobuf messages, we need to use the numeric value
        request.keyword_plan_network = 2  # GOOGLE_SEARCH = 2
        
        # Add seed keywords
        for keyword in keywords:
            request.keyword_seed.keywords.append(keyword)
        
        # Execute request
        response = keyword_plan_idea_service.generate_keyword_ideas(request=request)
        
        # Process results
        metrics = []
        
        # Process seed keywords
        for result in response.results:
            # Handle both proto-plus and regular protobuf responses
            keyword_text = result.text
            if hasattr(keyword_text, 'value'):
                keyword_text = keyword_text.value
            
            if not keyword_text:
                continue
                
            # Check if this is one of our seed keywords
            is_seed = keyword_text.lower() in [k.lower() for k in keywords]
            
            if is_seed or include_ideas:
                metric = self._parse_keyword_metrics(result, is_seed)
                metrics.append(metric)
        
        return metrics
    
    def _parse_keyword_metrics(self, result: Any, is_seed: bool) -> KeywordMetric:
        """
        Parse keyword metrics from API response
        """
        # Handle both proto-plus and regular protobuf responses
        keyword_text = result.text
        if hasattr(keyword_text, 'value'):
            keyword_text = keyword_text.value
        elif not keyword_text:
            keyword_text = ""
        
        # Extract metrics
        metrics = result.keyword_idea_metrics
        
        # Handle search volume
        search_volume = metrics.avg_monthly_searches
        if hasattr(search_volume, 'value'):
            search_volume = search_volume.value
        elif not search_volume:
            search_volume = None
            
        # Handle CPC
        cpc_micro = metrics.average_cpc_micros
        if hasattr(cpc_micro, 'value'):
            cpc_micro = cpc_micro.value
        elif not cpc_micro:
            cpc_micro = None
            
        # Handle competition
        competition = metrics.competition
        if hasattr(competition, 'value'):
            competition = competition.value
        elif not competition:
            competition = None
        
        return KeywordMetric(
            keyword=keyword_text.lower() if keyword_text else "",
            search_volume=search_volume,
            cpc_micro=cpc_micro,
            competition=competition,
            source=KeywordSource.SEED if is_seed else KeywordSource.IDEA
        )
    
    async def get_keyword_ideas(
        self,
        seed_keywords: List[str],
        language: str = "en",
        location: str = "2840",
        limit: int = 100,
        min_search_volume: int = 0
    ) -> List[KeywordMetric]:
        """
        Get keyword ideas based on seed keywords
        
        Args:
            seed_keywords: Seed keywords
            language: Language code
            location: Geo target code  
            limit: Max number of ideas
            min_search_volume: Minimum search volume filter
            
        Returns:
            List of keyword ideas
        """
        # Ensure client is initialized before use
        self._ensure_client_initialized()
        
        if not self.is_initialized:
            raise RuntimeError("Google Ads client not initialized")

        async with self.rate_limiter:
            try:
                loop = asyncio.get_event_loop()
                ideas = await loop.run_in_executor(
                    None,
                    self._get_keyword_ideas_sync,
                    seed_keywords,
                    language,
                    location,
                    limit,
                    min_search_volume
                )
                
                logger.info(
                    "Retrieved keyword ideas",
                    count=len(ideas),
                    seeds=len(seed_keywords)
                )
                
                return ideas
                
            except GoogleAdsException as e:
                logger.error(
                    "Google Ads API error getting ideas",
                    error=str(e),
                    failure=e.failure
                )
                raise
            except Exception as e:
                logger.error(
                    "Unexpected error getting keyword ideas",
                    error=str(e)
                )
                raise
    
    def _get_keyword_ideas_sync(
        self,
        seed_keywords: List[str],
        language: str,
        location: str,
        limit: int,
        min_search_volume: int
    ) -> List[KeywordMetric]:
        """
        Synchronous method to get keyword ideas
        """
        # This should already be initialized by the async wrapper
        if not self.is_initialized:
            raise RuntimeError("Google Ads client not initialized")

        keyword_plan_idea_service = self.client.get_service("KeywordPlanIdeaService")
        
        # Build request
        request = self.client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = self.customer_id
        
        # Set language
        # Convert language code to ID if needed  
        language_id = "1000" if language == "en" else language
        language_rn = self.client.get_service("GoogleAdsService").language_constant_path(language_id)
        request.language = language_rn
        
        # Set location
        location_rn = self.client.get_service("GoogleAdsService").geo_target_constant_path(location)
        request.geo_target_constants.append(location_rn)
        
        # Set network
        # For protobuf messages, we need to use the numeric value
        request.keyword_plan_network = 2  # GOOGLE_SEARCH = 2
        
        # Add seed keywords
        for keyword in seed_keywords:
            request.keyword_seed.keywords.append(keyword)
        
        # Execute request
        response = keyword_plan_idea_service.generate_keyword_ideas(request=request)
        
        # Process results
        ideas = []
        
        for result in response.results:
            # Handle both proto-plus and regular protobuf responses
            keyword_text = result.text
            if hasattr(keyword_text, 'value'):
                keyword_text = keyword_text.value
            
            if not keyword_text:
                continue
                
            # Skip if it's a seed keyword
            if keyword_text.lower() in [k.lower() for k in seed_keywords]:
                continue
                
            # Check search volume filter
            metrics = result.keyword_idea_metrics
            search_volume = metrics.avg_monthly_searches
            if hasattr(search_volume, 'value'):
                search_volume = search_volume.value
            elif not search_volume:
                search_volume = 0
            
            if search_volume >= min_search_volume:
                idea = self._parse_keyword_metrics(result, False)
                ideas.append(idea)
                
                if len(ideas) >= limit:
                    break
        
        return ideas


# Create singleton instance - will be initialized lazily
google_ads_client = None

def get_google_ads_client():
    """Get or create the Google Ads client singleton"""
    global google_ads_client
    if google_ads_client is None:
        google_ads_client = GoogleAdsApiClient()
    return google_ads_client 