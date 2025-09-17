"""
Simplified Google Ads Service - Based on Working Direct Test
This is the exact implementation that successfully returned 1,630 keyword ideas
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import json

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    GOOGLE_ADS_AVAILABLE = True
except ImportError:
    GOOGLE_ADS_AVAILABLE = False
    GoogleAdsClient = None
    GoogleAdsException = Exception

from loguru import logger
from app.core.config import settings
from app.core.database import db_pool
from app.models.keyword_metrics import KeywordMetric, KeywordSource


class SimplifiedGoogleAdsService:
    """Simplified Google Ads service using exact working pattern"""
    
    def __init__(self):
        self.client = None
        self.customer_id = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize using exact same pattern as working direct test"""
        if not GOOGLE_ADS_AVAILABLE:
            logger.warning("Google Ads API not available")
            return
            
        try:
            # Use exact same credentials config as working direct test
            credentials = {
                'developer_token': settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                'client_id': settings.GOOGLE_ADS_CLIENT_ID,
                'client_secret': settings.GOOGLE_ADS_CLIENT_SECRET,
                'refresh_token': settings.GOOGLE_ADS_REFRESH_TOKEN,
                'login_customer_id': settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
                'use_proto_plus': True
            }
            
            # Check credentials
            missing = [k for k, v in credentials.items() if k != 'use_proto_plus' and not v]
            if missing:
                logger.error(f"Missing Google Ads credentials: {missing}")
                return
                
            # Create client exactly like working test
            self.client = GoogleAdsClient.load_from_dict(credentials)
            self.customer_id = settings.GOOGLE_ADS_CUSTOMER_ID or settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
            
            self._initialized = True
            logger.info(f"✅ Simplified Google Ads client initialized: {self.customer_id}")
            
        except Exception as e:
            logger.error(f"❌ Simplified Google Ads init failed: {e}")
            self._initialized = False
    
    async def get_historical_metrics_batch(
        self,
        keywords: List[str],
        countries: List[str], 
        months_back: int = 12,
        pipeline_execution_id: Optional[str] = None
    ) -> Dict[str, List[KeywordMetric]]:
        """Get keyword metrics using exact working API pattern"""
        
        if not self._initialized:
            await self.initialize()
            
        if not self._initialized:
            logger.error("❌ Google Ads not initialized")
            return {country: [] for country in countries}
        
        results = {}

        # Configurable batching and concurrency
        try:
            batch_size = int(getattr(settings, 'GOOGLE_ADS_BATCH_SIZE', 1000))
        except Exception:
            batch_size = 1000
        try:
            max_in_flight = int(getattr(settings, 'GOOGLE_ADS_CONCURRENCY', 4))
        except Exception:
            max_in_flight = 4

        async def process_country(country: str) -> None:
            try:
                # Chunk keywords to recommended batch size to avoid rate limiting
                keyword_batches = [keywords[i:i+batch_size] for i in range(0, len(keywords), batch_size)]
                logger.info(f"🚀 {country}: {len(keywords)} keywords in {len(keyword_batches)} batches (size={batch_size})")

                semaphore = asyncio.Semaphore(max(1, max_in_flight))

                async def process_batch(batch_keywords: List[str], idx: int) -> List[KeywordMetric]:
                    async with semaphore:
                        logger.info(f"🔗 {country}: calling Google Ads for batch {idx+1}/{len(keyword_batches)} with {len(batch_keywords)} keywords")
                        batch_metrics = await self._get_keyword_ideas(batch_keywords, country)
                        # Store per batch to persist progressively
                        if batch_metrics:
                            await self._store_metrics(batch_metrics, country, pipeline_execution_id)
                        return batch_metrics

                tasks = [process_batch(bk, i) for i, bk in enumerate(keyword_batches)]
                batches = await asyncio.gather(*tasks, return_exceptions=True)

                country_metrics: List[KeywordMetric] = []
                for i, bm in enumerate(batches):
                    if isinstance(bm, Exception):
                        logger.error(f"❌ {country}: batch {i+1} failed: {bm}")
                        continue
                    country_metrics.extend(bm)

                results[country] = country_metrics
                logger.info(f"✅ {country}: total {len(country_metrics)} metrics across {len(keyword_batches)} batches")
            except Exception as e:
                logger.error(f"❌ Failed for {country}: {e}")
                results[country] = []

        # Process countries sequentially to respect per-account limits; adjust if needed
        for country in countries:
            await process_country(country)
        
        return results
    
    async def _get_keyword_ideas(self, keywords: List[str], country: str) -> List[KeywordMetric]:
        """Get keyword ideas using exact working direct test pattern"""
        
        try:
            # Use exact same service call as working test
            keyword_service = self.client.get_service("KeywordPlanIdeaService")
            
            # Create request exactly like working test
            request = self.client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = self.customer_id
            
            # Set network exactly like working test
            request.keyword_plan_network = self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
            
            # Set language exactly like working test
            request.language = self.client.get_service("GoogleAdsService").language_constant_path("1000")
            
            # Set geo target exactly like working test
            geo_map = {'US': '2840', 'UK': '2826', 'CA': '2124'}
            geo_id = geo_map.get(country, '2840')
            request.geo_target_constants.append(
                self.client.get_service("GoogleAdsService").geo_target_constant_path(geo_id)
            )
            
            # Set keywords exactly like working test
            request.keyword_seed.keywords.extend(keywords)
            
            logger.info(f"🔗 Making API call for {len(keywords)} keywords in {country}")
            
            # Execute exactly like working test
            response = keyword_service.generate_keyword_ideas(request=request)
            
            # Process results exactly like working test
            metrics = []
            results = list(response.results)
            
            logger.info(f"📊 Got {len(results)} keyword ideas from API")
            
            # Create metrics for our requested keywords
            for keyword in keywords:
                # Find matching result
                matching_result = None
                for result in results:
                    if result.text.lower() == keyword.lower():
                        matching_result = result
                        break
                
                if matching_result:
                    idea_metrics = matching_result.keyword_idea_metrics
                    
                    metric = KeywordMetric(
                        keyword=keyword,
                        avg_monthly_searches=idea_metrics.avg_monthly_searches or 0,
                        competition_level=idea_metrics.competition.name if idea_metrics.competition else "UNKNOWN",
                        low_top_of_page_bid_micros=idea_metrics.low_top_of_page_bid_micros or 0,
                        high_top_of_page_bid_micros=idea_metrics.high_top_of_page_bid_micros or 0,
                        source=KeywordSource.GOOGLE_ADS,
                        country_code=country
                    )
                    metrics.append(metric)
                    logger.info(f"✅ {keyword}: {metric.avg_monthly_searches} searches, {metric.competition_level}")
                else:
                    # No data found
                    metric = KeywordMetric(
                        keyword=keyword,
                        avg_monthly_searches=0,
                        competition_level="UNKNOWN", 
                        low_top_of_page_bid_micros=0,
                        high_top_of_page_bid_micros=0,
                        source=KeywordSource.GOOGLE_ADS,
                        country_code=country
                    )
                    metrics.append(metric)
                    logger.warning(f"⚠️ No data found for: {keyword}")
            
            return metrics
            
        except GoogleAdsException as ex:
            logger.error(f"❌ Google Ads API Exception for {country}: {ex}")
            if hasattr(ex, 'failure') and ex.failure and hasattr(ex.failure, 'errors'):
                for error in ex.failure.errors:
                    logger.error(f"  📍 Error code: {error.error_code}")
                    logger.error(f"  📍 Error message: {error.message}")
            raise
            
        except Exception as e:
            logger.error(f"❌ Unexpected error for {country}: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"📍 Traceback: {traceback.format_exc()}")
            raise
    
    async def _store_metrics(self, metrics: List[KeywordMetric], country: str, pipeline_id: Optional[str]):
        """Store metrics in database"""
        if not metrics:
            return
            
        try:
            snapshot_date = date.today()
            
            async with db_pool.acquire() as conn:
                stored_count = 0
                
                for metric in metrics:
                    try:
                        await conn.execute("""
                            INSERT INTO historical_keyword_metrics (
                                snapshot_date, keyword_text, country_code, source,
                                pipeline_execution_id, avg_monthly_searches, 
                                competition_level, low_top_of_page_bid_micros,
                                high_top_of_page_bid_micros
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            ON CONFLICT (snapshot_date, keyword_id, country_code, source) 
                            DO UPDATE SET 
                                avg_monthly_searches = EXCLUDED.avg_monthly_searches,
                                competition_level = EXCLUDED.competition_level,
                                low_top_of_page_bid_micros = EXCLUDED.low_top_of_page_bid_micros,
                                high_top_of_page_bid_micros = EXCLUDED.high_top_of_page_bid_micros,
                                updated_at = NOW()
                        """,
                            snapshot_date,
                            metric.keyword,
                            country,
                            'GOOGLE_ADS',
                            pipeline_id,
                            metric.avg_monthly_searches,
                            metric.competition_level,
                            metric.low_top_of_page_bid_micros,
                            metric.high_top_of_page_bid_micros
                        )
                        stored_count += 1
                        
                    except Exception as store_error:
                        logger.error(f"❌ Failed to store {metric.keyword}: {store_error}")
                        
                logger.info(f"💾 Stored {stored_count} Google Ads metrics for {country}")
                
        except Exception as e:
            logger.error(f"❌ Database storage error: {e}")
