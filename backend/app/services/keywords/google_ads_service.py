"""
Google Ads integration service for keyword metrics
Simplified and integrated version of the keyword metrics microservice
"""

import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf.json_format import MessageToDict
from aiolimiter import AsyncLimiter
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from app.core.config import settings
from app.core.database import db_pool
from app.models.keyword_metrics import KeywordMetric, KeywordSource


class GoogleAdsService:
    """Google Ads API integration for keyword metrics"""
    
    def __init__(self):
        self.rate_limiter = AsyncLimiter(5, 1.0)  # 5 requests per second
        self.client = None
        self.customer_id = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Google Ads client"""
        if self._initialized:
            return
        
        try:
            # Get API credentials from database (encrypted) or environment
            api_credentials = await self._get_google_ads_credentials()
            
            if not all(api_credentials.values()):
                logger.warning("Google Ads API not configured - keyword metrics will be unavailable")
                return
            
            # Create client configuration
            credentials = {
                "developer_token": api_credentials["developer_token"],
                "refresh_token": api_credentials["refresh_token"],
                "client_id": api_credentials["client_id"],
                "client_secret": api_credentials["client_secret"],
                "login_customer_id": api_credentials["login_customer_id"],
                "use_proto_plus": False
            }
            
            self.client = GoogleAdsClient.load_from_dict(credentials)
            self.customer_id = api_credentials.get("customer_id")
            self._initialized = True
            
            logger.info("Google Ads client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Ads client: {e}")
            self._initialized = False
    
    async def get_keyword_metrics(self, keywords: List[str], location_id: str = "2840") -> List[KeywordMetric]:
        """
        Get keyword metrics from Google Ads Keyword Planner
        
        Args:
            keywords: List of keyword strings
            location_id: Geographic location ID (default: US)
            
        Returns:
            List of keyword metrics
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.client:
            logger.warning("Google Ads client not available")
            return []
        
        async with self.rate_limiter:
            try:
                return await self._fetch_keyword_metrics(keywords, location_id)
            except Exception as e:
                logger.error(f"Error fetching keyword metrics: {e}")
                return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _fetch_keyword_metrics(self, keywords: List[str], location_id: str) -> List[KeywordMetric]:
        """Fetch keyword metrics with retry logic"""
        try:
            keyword_plan_idea_service = self.client.get_service("KeywordPlanIdeaService")
            
            # Create request
            request = self.client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = self.customer_id
            request.language = self.client.get_service("LanguageConstantService").get_language_constant("1000").resource_name  # English
            
            # Set geo target
            geo_target = self.client.get_type("LocationInfo")
            geo_target.location_constant = f"geoTargetConstants/{location_id}"
            request.geo_target_constants.append(geo_target)
            
            # Add seed keywords
            for keyword_text in keywords:
                keyword_seed = self.client.get_type("KeywordSeed")
                keyword_seed.keyword.append(keyword_text)
                request.keyword_seed = keyword_seed
                break  # For now, process one at a time
            
            # Execute request
            response = keyword_plan_idea_service.generate_keyword_ideas(request=request)
            
            # Process results
            metrics = []
            for idea in response:
                keyword_dict = MessageToDict(idea._pb)
                
                # Extract metrics
                keyword_metric = KeywordMetric(
                    keyword=keyword_dict.get("text", ""),
                    avg_monthly_searches=self._extract_avg_searches(keyword_dict),
                    competition_level=keyword_dict.get("competitionIndex", "UNKNOWN"),
                    low_top_of_page_bid_micros=keyword_dict.get("lowTopOfPageBidMicros", 0),
                    high_top_of_page_bid_micros=keyword_dict.get("highTopOfPageBidMicros", 0),
                    source=KeywordSource.GOOGLE_ADS
                )
                
                metrics.append(keyword_metric)
            
            logger.info(f"Fetched metrics for {len(metrics)} keywords")
            return metrics
            
        except GoogleAdsException as ex:
            logger.error(f"Google Ads API error: {ex}")
            for error in ex.errors:
                logger.error(f"  Error code: {error.error_code}")
                logger.error(f"  Error message: {error.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in keyword metrics: {e}")
            raise
    
    def _extract_avg_searches(self, keyword_dict: Dict[str, Any]) -> int:
        """Extract average monthly searches from keyword data"""
        try:
            if "monthlySearchVolumes" in keyword_dict:
                volumes = keyword_dict["monthlySearchVolumes"]
                if volumes:
                    total = sum(vol.get("monthlySearches", 0) for vol in volumes)
                    return total // len(volumes) if volumes else 0
            
            # Fallback to aggregate data
            if "searchVolume" in keyword_dict:
                return keyword_dict["searchVolume"]
            
            return 0
            
        except Exception as e:
            logger.warning(f"Could not extract search volume: {e}")
            return 0
    
    async def get_keyword_ideas(
        self, 
        seed_keywords: List[str], 
        location_id: str = "2840",
        max_ideas: int = 100
    ) -> List[KeywordMetric]:
        """
        Generate keyword ideas based on seed keywords
        
        Args:
            seed_keywords: Base keywords to generate ideas from
            location_id: Geographic location
            max_ideas: Maximum number of ideas to return
            
        Returns:
            List of keyword ideas with metrics
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.client:
            return []
        
        # Implementation would be similar to _fetch_keyword_metrics
        # but using keyword ideas generation instead of metrics for existing keywords
        logger.info(f"Generating keyword ideas for: {seed_keywords}")
        return []  # Placeholder implementation
    
    async def _get_google_ads_credentials(self) -> Dict[str, str]:
        """Get Google Ads credentials from database or environment"""
        # Try database first (encrypted storage)
        async with db_pool.acquire() as conn:
            google_ads_keys = await conn.fetch(
                """
                SELECT service_name, api_key_encrypted 
                FROM api_keys 
                WHERE service_name LIKE 'google_ads_%' AND is_active = true
                """
            )
        
        credentials = {}
        for row in google_ads_keys:
            key_name = row['service_name'].replace('google_ads_', '')
            # TODO: Decrypt the key properly
            credentials[key_name] = row['api_key_encrypted']
        
        # Fallback to environment variables
        env_mapping = {
            'developer_token': 'GOOGLE_ADS_DEVELOPER_TOKEN',
            'client_id': 'GOOGLE_ADS_CLIENT_ID', 
            'client_secret': 'GOOGLE_ADS_CLIENT_SECRET',
            'refresh_token': 'GOOGLE_ADS_REFRESH_TOKEN',
            'login_customer_id': 'GOOGLE_ADS_LOGIN_CUSTOMER_ID',
            'customer_id': 'GOOGLE_ADS_CUSTOMER_ID'
        }
        
        for key, env_var in env_mapping.items():
            if key not in credentials:
                credentials[key] = os.getenv(env_var, "")
        
        return credentials
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Google Ads API connection"""
        if not self._initialized:
            await self.initialize()
        
        if not self.client:
            return {"status": "error", "message": "Client not initialized"}
        
        try:
            # Simple test request
            customer_service = self.client.get_service("CustomerService")
            customer = customer_service.get_customer(
                resource_name=f"customers/{self.customer_id}"
            )
            
            return {
                "status": "success",
                "customer_id": self.customer_id,
                "currency": customer.currency_code,
                "timezone": customer.time_zone,
                "message": "Google Ads API connection successful"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Connection test failed: {str(e)}"
            }
