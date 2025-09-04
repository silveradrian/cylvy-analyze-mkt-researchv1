"""
Enhanced Google Ads service with Generate Historical Metrics API
Supports proper batch processing per geo location
"""

import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from collections import defaultdict

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    from google.protobuf.json_format import MessageToDict
    GOOGLE_ADS_AVAILABLE = True
except ImportError:
    logger.warning("Google Ads API library not installed - keyword metrics enrichment disabled")
    GoogleAdsClient = None
    GoogleAdsException = Exception
    MessageToDict = None
    GOOGLE_ADS_AVAILABLE = False
from aiolimiter import AsyncLimiter
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from app.core.config import settings
from app.core.database import db_pool
from app.models.keyword_metrics import KeywordMetric, KeywordSource


# Google Ads Geo Target Constants for your client countries
GEO_TARGET_CONSTANTS = {
    'US': '2840',    # United States
    'UK': '2826',    # United Kingdom  
    'DE': '2276',    # Germany
    'SA': '2682',    # Saudi Arabia
    'VN': '2704',    # Vietnam
    # EMEA
    'FR': '2250',    # France
    'ES': '2724',    # Spain
    'IT': '2380',    # Italy
    'NL': '2528',    # Netherlands
    'BE': '2056',    # Belgium
    'CH': '2756',    # Switzerland
    'AT': '2040',    # Austria
    'SE': '2752',    # Sweden
    'NO': '2578',    # Norway
    'DK': '2208',    # Denmark
    'FI': '2246',    # Finland
    'PL': '2616',    # Poland
    'CZ': '2203',    # Czech Republic
    'HU': '2348',    # Hungary
    'AE': '2784',    # UAE
    'ZA': '2710',    # South Africa
    # Americas
    'CA': '2124',    # Canada
    'MX': '2484',    # Mexico
    'BR': '2076',    # Brazil
    'AR': '2032',    # Argentina
    'CL': '2152',    # Chile
    'CO': '2170',    # Colombia
    'PE': '2604',    # Peru
    # Asia-Pacific
    'AU': '2036',    # Australia
    'NZ': '2554',    # New Zealand
    'SG': '2702',    # Singapore
    'HK': '2344',    # Hong Kong
    'JP': '2392',    # Japan
    'KR': '2410',    # South Korea
    'IN': '2356',    # India
    'TH': '2764',    # Thailand
    'MY': '2458',    # Malaysia
    'PH': '2608',    # Philippines
    'ID': '2360'     # Indonesia
}


class EnhancedGoogleAdsService:
    """Enhanced Google Ads service with proper batch processing for historical metrics"""
    
    def __init__(self):
        self.rate_limiter = AsyncLimiter(10, 1.0)  # Higher rate for batch requests
        self.client = None
        self.customer_id = None
        self._initialized = False
        self.batch_size = 1000  # Keywords per batch (Google Ads supports up to 10,000)
    
    async def initialize(self):
        """Initialize Google Ads client"""
        if not GOOGLE_ADS_AVAILABLE:
            logger.warning("Google Ads API not available - skipping initialization")
            self._initialized = False
            return
            
        try:
            # Initialize Google Ads client
            self.client = GoogleAdsClient.load_from_storage()
            
            if hasattr(settings, 'GOOGLE_ADS_CUSTOMER_ID') and settings.GOOGLE_ADS_CUSTOMER_ID:
                self.customer_id = settings.GOOGLE_ADS_CUSTOMER_ID
            else:
                # Try to get customer ID from client
                customer_service = self.client.get_service("CustomerService")
                customers = customer_service.list_accessible_customers()
                if customers.resource_names:
                    self.customer_id = customers.resource_names[0].split('/')[-1]
            
            if self.customer_id:
                self._initialized = True
                logger.info(f"Google Ads client initialized with customer ID: {self.customer_id}")
            else:
                logger.warning("Google Ads customer ID not found")
        
        except Exception as e:
            logger.error(f"Failed to initialize Google Ads client: {e}")
            self._initialized = False
    
    async def get_historical_metrics_batch(
        self, 
        keywords: List[str], 
        countries: List[str],
        months_back: int = 12,
        pipeline_execution_id: Optional[str] = None
    ) -> Dict[str, List[KeywordMetric]]:
        """
        Get historical metrics for keywords across multiple countries using batch processing
        
        Args:
            keywords: List of keyword strings (up to 10,000 per batch)
            countries: List of country codes (e.g., ['US', 'UK', 'DE'])
            months_back: Number of months of historical data
            
        Returns:
            Dict mapping country code to list of keyword metrics
        """
        if not self._initialized:
            await self.initialize()
        
        if not GOOGLE_ADS_AVAILABLE or not self.client or not self.customer_id:
            logger.warning("Google Ads client not available - returning mock data for testing")
            # Return mock structure for testing when Google Ads is not configured
            return {country: [] for country in countries}
        
        results = {}
        
        # Process each country separately (required by Google Ads API)
        for country in countries:
            geo_target_id = GEO_TARGET_CONSTANTS.get(country)
            if not geo_target_id:
                logger.warning(f"No geo target constant found for country: {country}")
                continue
                
            logger.info(f"Fetching historical metrics for {len(keywords)} keywords in {country}")
            
            try:
                country_metrics = await self._fetch_historical_metrics_for_country(
                    keywords, geo_target_id, country, months_back
                )
                results[country] = country_metrics
                
                # Store metrics in database with pipeline tracking
                await self._store_keyword_metrics(country_metrics, country, pipeline_execution_id)
                
            except Exception as e:
                logger.error(f"Failed to fetch metrics for {country}: {e}")
                results[country] = []
        
        return results
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _fetch_historical_metrics_for_country(
        self, 
        keywords: List[str], 
        geo_target_id: str, 
        country: str,
        months_back: int
    ) -> List[KeywordMetric]:
        """Fetch historical metrics for a specific country using batch processing"""
        
        async with self.rate_limiter:
            try:
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                metrics = await loop.run_in_executor(
                    None,
                    self._generate_historical_metrics_sync,
                    keywords,
                    geo_target_id,
                    country,
                    months_back
                )
                
                logger.info(f"Retrieved {len(metrics)} historical metrics for {country}")
                return metrics
                
            except GoogleAdsException as e:
                logger.error(f"Google Ads API error for {country}: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error for {country}: {e}")
                raise
    
    def _generate_historical_metrics_sync(
        self, 
        keywords: List[str], 
        geo_target_id: str, 
        country: str,
        months_back: int
    ) -> List[KeywordMetric]:
        """Synchronous method to generate historical metrics using Google Ads API"""
        
        try:
            # Use Keyword Plan Service for historical data
            keyword_plan_service = self.client.get_service("KeywordPlanService")
            
            # Create request for historical metrics
            request = self.client.get_type("GenerateHistoricalMetricsRequest")
            request.customer_id = self.customer_id
            
            # Set geo target
            geo_target = self.client.get_type("LocationInfo")
            geo_target.location_constant = f"geoTargetConstants/{geo_target_id}"
            request.geo_target_constants.append(geo_target)
            
            # Set language (English for now, could be parameterized)
            request.language = self.client.get_service("LanguageConstantService").get_language_constant("1000").resource_name
            
            # Add all keywords to the request (supports batch processing!)
            for keyword_text in keywords:
                request.keywords.append(keyword_text)
            
            # Set date range for historical data
            end_date = date.today()
            start_date = end_date - timedelta(days=months_back * 30)
            
            request.historical_metrics_options.year_month_range.start.year = start_date.year
            request.historical_metrics_options.year_month_range.start.month = start_date.month
            request.historical_metrics_options.year_month_range.end.year = end_date.year
            request.historical_metrics_options.year_month_range.end.month = end_date.month
            
            # Execute request
            logger.info(f"Requesting historical metrics for {len(keywords)} keywords in {country}")
            response = keyword_plan_service.generate_historical_metrics(request=request)
            
            # Process results
            metrics = []
            for metric_data in response.metrics:
                metric_dict = MessageToDict(metric_data._pb)
                
                keyword_metric = KeywordMetric(
                    keyword=metric_dict.get("keyword", ""),
                    avg_monthly_searches=self._extract_avg_searches(metric_dict),
                    competition_level=metric_dict.get("competition", "UNKNOWN"),
                    low_top_of_page_bid_micros=metric_dict.get("lowTopOfPageBidMicros", 0),
                    high_top_of_page_bid_micros=metric_dict.get("highTopOfPageBidMicros", 0),
                    source=KeywordSource.GOOGLE_ADS,
                    location_id=geo_target_id,
                    country_code=country
                )
                
                metrics.append(keyword_metric)
            
            logger.info(f"Successfully processed {len(metrics)} keyword metrics for {country}")
            return metrics
            
        except GoogleAdsException as ex:
            logger.error(f"Google Ads API error for {country}: {ex}")
            for error in ex.errors:
                logger.error(f"  Error code: {error.error_code}")
                logger.error(f"  Error message: {error.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting historical metrics for {country}: {e}")
            raise
    
    def _extract_avg_searches(self, metric_dict: Dict[str, Any]) -> int:
        """Extract average monthly searches from historical metric data"""
        try:
            # Historical metrics have different structure than keyword ideas
            if "monthlySearchVolumes" in metric_dict:
                volumes = metric_dict["monthlySearchVolumes"]
                if volumes:
                    total = sum(vol.get("monthlySearches", 0) for vol in volumes)
                    return total // len(volumes) if volumes else 0
            
            # Fallback to aggregate data
            if "averageMonthlySearches" in metric_dict:
                return metric_dict["averageMonthlySearches"]
            
            if "searchVolume" in metric_dict:
                return metric_dict["searchVolume"]
            
            return 0
            
        except Exception as e:
            logger.warning(f"Could not extract search volume from historical data: {e}")
            return 0
    
    async def _store_keyword_metrics(
        self, 
        metrics: List[KeywordMetric], 
        country: str, 
        pipeline_execution_id: Optional[str] = None
    ):
        """Store keyword metrics in database with enhanced historical tracking"""
        if not metrics:
            return
        
        snapshot_date = date.today()
        geo_target_id = GEO_TARGET_CONSTANTS.get(country)
        
        async with db_pool.acquire() as conn:
            stored_count = 0
            for metric in metrics:
                try:
                    # Update keyword with latest search volume data
                    await conn.execute("""
                        UPDATE keywords 
                        SET avg_monthly_searches = $1,
                            competition_level = $2,
                            updated_at = NOW()
                        WHERE keyword = $3
                    """, 
                        metric.avg_monthly_searches,
                        metric.competition_level,
                        metric.keyword
                    )
                    
                    # Store comprehensive historical metrics
                    await conn.execute("""
                        INSERT INTO historical_keyword_metrics (
                            snapshot_date, keyword_id, keyword_text, country_code, geo_target_id,
                            source, pipeline_execution_id, calculation_frequency,
                            avg_monthly_searches, competition_level, 
                            low_top_of_page_bid_micros, high_top_of_page_bid_micros
                        ) 
                        SELECT $1, k.id, k.keyword, $2, $3, $4, $5, $6, $7, $8, $9, $10
                        FROM keywords k WHERE k.keyword = $11
                        ON CONFLICT (snapshot_date, keyword_id, country_code, source) 
                        DO UPDATE SET 
                            avg_monthly_searches = EXCLUDED.avg_monthly_searches,
                            competition_level = EXCLUDED.competition_level,
                            low_top_of_page_bid_micros = EXCLUDED.low_top_of_page_bid_micros,
                            high_top_of_page_bid_micros = EXCLUDED.high_top_of_page_bid_micros,
                            updated_at = NOW()
                    """,
                        snapshot_date,               # $1
                        country,                     # $2  
                        geo_target_id,              # $3
                        'GOOGLE_ADS',               # $4 source
                        pipeline_execution_id,       # $5
                        'monthly',                   # $6 frequency  
                        metric.avg_monthly_searches, # $7
                        metric.competition_level,    # $8
                        getattr(metric, 'low_top_of_page_bid_micros', 0),  # $9
                        getattr(metric, 'high_top_of_page_bid_micros', 0), # $10
                        metric.keyword               # $11
                    )
                    stored_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to store metric for {metric.keyword} in {country}: {e}")
                    continue
        
        logger.info(f"Stored {stored_count}/{len(metrics)} keyword metrics for {country} (Pipeline: {pipeline_execution_id})")
    
    async def get_supported_countries(self) -> List[Dict[str, str]]:
        """Get list of supported countries with geo target IDs"""
        return [
            {'code': code, 'name': self._get_country_name(code), 'geo_target_id': geo_id}
            for code, geo_id in GEO_TARGET_CONSTANTS.items()
        ]
    
    def _get_country_name(self, country_code: str) -> str:
        """Get human-readable country name"""
        country_names = {
            'US': 'United States', 'UK': 'United Kingdom', 'DE': 'Germany',
            'SA': 'Saudi Arabia', 'VN': 'Vietnam', 'FR': 'France', 'ES': 'Spain',
            'IT': 'Italy', 'NL': 'Netherlands', 'BE': 'Belgium', 'CH': 'Switzerland',
            'AT': 'Austria', 'SE': 'Sweden', 'NO': 'Norway', 'DK': 'Denmark',
            'FI': 'Finland', 'PL': 'Poland', 'CZ': 'Czech Republic', 'HU': 'Hungary',
            'AE': 'UAE', 'ZA': 'South Africa', 'CA': 'Canada', 'MX': 'Mexico',
            'BR': 'Brazil', 'AR': 'Argentina', 'CL': 'Chile', 'CO': 'Colombia',
            'PE': 'Peru', 'AU': 'Australia', 'NZ': 'New Zealand', 'SG': 'Singapore',
            'HK': 'Hong Kong', 'JP': 'Japan', 'KR': 'South Korea', 'IN': 'India',
            'TH': 'Thailand', 'MY': 'Malaysia', 'PH': 'Philippines', 'ID': 'Indonesia'
        }
        return country_names.get(country_code, country_code)
