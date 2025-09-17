"""
DataForSEO Service for Keyword Metrics with 24-hour caching
"""
import asyncio
import base64
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger
import httpx
from app.core.config import get_settings
from app.core.database import db_pool
import redis.asyncio as redis


class DataForSEOService:
    """DataForSEO API client for keyword metrics with Redis caching"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Handle Base64 encoded credentials in format "username:password"
        if self.settings.DATAFORSEO_LOGIN:
            try:
                # Try to decode the login as it might be Base64 encoded
                decoded = base64.b64decode(self.settings.DATAFORSEO_LOGIN).decode()
                if ':' in decoded:
                    # It's encoded credentials
                    self.login, self.password = decoded.split(':', 1)
                else:
                    # Not encoded or not in expected format
                    self.login = self.settings.DATAFORSEO_LOGIN
                    self.password = self.settings.DATAFORSEO_PASSWORD or ""
            except Exception:
                # Not Base64 encoded, use as is
                self.login = self.settings.DATAFORSEO_LOGIN
                self.password = self.settings.DATAFORSEO_PASSWORD or ""
        else:
            self.login = None
            self.password = ""
            
        self.base_url = "https://api.dataforseo.com/v3"
        self.client = None
        self.redis_client = None
        self.cache_ttl = 86400  # 24 hours in seconds
        
        # Create auth header
        if self.login:
            credentials = f"{self.login}:{self.password}"
            self.auth_header = f"Basic {base64.b64encode(credentials.encode()).decode()}"
        else:
            self.auth_header = None
            
    async def initialize(self):
        """Initialize HTTP client and Redis connection"""
        if not self.client:
            self.client = httpx.AsyncClient(timeout=30.0)
            
        if not self.redis_client:
            try:
                self.redis_client = await redis.from_url(
                    self.settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("✅ DataForSEO Redis cache initialized")
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed, proceeding without cache: {e}")
                self.redis_client = None
    
    def _get_cache_key(self, keyword: str, location_code: int) -> str:
        """Generate cache key for keyword-location combination"""
        key_data = f"{keyword.lower()}:{location_code}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"dataforseo:keywords:v1:{key_hash}"
    
    async def _get_from_cache(self, keyword: str, location_code: int) -> Optional[Dict]:
        """Get keyword metrics from cache"""
        if not self.redis_client:
            return None
            
        try:
            cache_key = self._get_cache_key(keyword, location_code)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                logger.debug(f"📦 Cache hit for '{keyword}' in location {location_code}")
                return data
                
        except Exception as e:
            logger.warning(f"⚠️ Cache read error: {e}")
            
        return None
    
    async def _set_cache(self, keyword: str, location_code: int, data: Dict):
        """Store keyword metrics in cache"""
        if not self.redis_client:
            return
            
        try:
            cache_key = self._get_cache_key(keyword, location_code)
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data)
            )
            logger.debug(f"💾 Cached metrics for '{keyword}' in location {location_code}")
            
        except Exception as e:
            logger.warning(f"⚠️ Cache write error: {e}")
    
    def _get_location_code(self, country_code: str) -> int:
        """Map country codes to DataForSEO location codes"""
        # DataForSEO location codes for countries
        location_map = {
            "US": 2840,  # United States
            "UK": 2826,  # United Kingdom
            "GB": 2826,  # United Kingdom (alternate)
            "DE": 2276,  # Germany
            "SA": 2682,  # Saudi Arabia
            "VN": 2704,  # Vietnam
            "CA": 2124,  # Canada
            "AU": 2036,  # Australia
            "FR": 2250,  # France
            "ES": 2724,  # Spain
            "IT": 2380,  # Italy
            "NL": 2528,  # Netherlands
            "BR": 2076,  # Brazil
            "IN": 2356,  # India
            "JP": 2392,  # Japan
            "CN": 2156,  # China
        }
        return location_map.get(country_code.upper(), 2840)  # Default to US
    
    async def get_keyword_metrics(self, keywords: List[str], location_code: int) -> List[Dict]:
        """Get keyword metrics from DataForSEO API or cache"""
        if not self.auth_header:
            logger.error("❌ DataForSEO credentials not configured")
            return []
            
        await self.initialize()
        
        results = []
        uncached_keywords = []
        
        # Check cache first
        for keyword in keywords:
            cached_data = await self._get_from_cache(keyword, location_code)
            if cached_data:
                results.append(cached_data)
            else:
                uncached_keywords.append(keyword)
        
        # Fetch uncached keywords from API
        if uncached_keywords:
            logger.info(f"🔍 Fetching {len(uncached_keywords)} keywords from DataForSEO API")
            
            # DataForSEO allows up to 1000 keywords per request
            batch_size = 700  # Conservative limit
            
            for i in range(0, len(uncached_keywords), batch_size):
                batch = uncached_keywords[i:i + batch_size]
                batch_results = await self._fetch_batch_from_api(batch, location_code)
                
                # Cache results
                for result in batch_results:
                    await self._set_cache(result['keyword'], location_code, result)
                    
                results.extend(batch_results)
        
        return results
    
    async def _fetch_batch_from_api(self, keywords: List[str], location_code: int) -> List[Dict]:
        """Fetch a batch of keywords from DataForSEO API"""
        try:
            # Prepare request data
            post_data = [{
                "location_code": location_code,
                "language_code": "en",
                "keywords": keywords
            }]
            
            # Make API request
            response = await self.client.post(
                f"{self.base_url}/keywords_data/google_ads/search_volume/live",
                headers={
                    "Authorization": self.auth_header,
                    "Content-Type": "application/json"
                },
                json=post_data
            )
            
            if response.status_code != 200:
                logger.error(f"❌ DataForSEO API error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            
            if data.get("status_code") != 20000:
                logger.error(f"❌ DataForSEO API error: {data.get('status_message', 'Unknown error')}")
                return []
            
            # Parse results
            results = []
            tasks = data.get("tasks", [])
            
            for task in tasks:
                if task.get("status_code") == 20000:
                    task_results = task.get("result", [])
                    for result in task_results:
                        keyword_data = result.get("keyword", "")
                        metrics = result.get("search_volume", {})
                        competition = result.get("competition", 0)
                        
                        # Convert competition to HIGH/MEDIUM/LOW
                        try:
                            competition_float = float(competition) if competition is not None else 0
                        except (ValueError, TypeError):
                            competition_float = 0
                            
                        if competition_float >= 0.7:
                            competition_level = "HIGH"
                        elif competition_float >= 0.3:
                            competition_level = "MEDIUM"
                        else:
                            competition_level = "LOW"
                        
                        # Extract monthly searches - could be nested or direct
                        monthly_searches = 0
                        if isinstance(metrics, dict):
                            monthly_searches = metrics.get("monthly_searches", 0) or 0
                        elif isinstance(result.get("monthly_searches"), (int, float)):
                            monthly_searches = result.get("monthly_searches", 0)
                        
                        results.append({
                            "keyword": keyword_data,
                            "avg_monthly_searches": int(monthly_searches) if monthly_searches else 0,
                            "competition_level": competition_level,
                            "competition_score": competition_float,
                            "cpc": float(result.get("cpc", 0) or 0),
                            "source": "dataforseo",
                            "cached_at": datetime.utcnow().isoformat()
                        })
            
            logger.info(f"✅ Retrieved {len(results)} keyword metrics from DataForSEO")
            return results
            
        except Exception as e:
            logger.error(f"❌ DataForSEO API request failed: {str(e)}")
            return []
    
    async def get_keyword_metrics_by_country(
        self, 
        keywords: List[str], 
        country_code: str,
        pipeline_execution_id: Optional[str] = None
    ) -> List[Dict]:
        """Get keyword metrics for a specific country"""
        location_code = self._get_location_code(country_code)
        metrics = await self.get_keyword_metrics(keywords, location_code)
        
        # Store in database if pipeline execution ID provided
        if pipeline_execution_id and metrics:
            await self._store_metrics_in_db(metrics, country_code, pipeline_execution_id)
            
        return metrics
    
    async def _store_metrics_in_db(
        self, 
        metrics: List[Dict], 
        country_code: str,
        pipeline_execution_id: str
    ):
        """Store keyword metrics in the database"""
        try:
            async with db_pool.acquire() as conn:
                # Get keyword IDs
                keyword_texts = [m['keyword'] for m in metrics]
                keyword_records = await conn.fetch(
                    """
                    SELECT id, keyword FROM keywords 
                    WHERE keyword = ANY($1::text[])
                    """,
                    keyword_texts
                )
                
                keyword_id_map = {rec['keyword']: rec['id'] for rec in keyword_records}
                
                # Insert metrics
                snapshot_date = datetime.utcnow().date()
                
                for metric in metrics:
                    keyword_id = keyword_id_map.get(metric['keyword'])
                    if not keyword_id:
                        continue
                        
                    await conn.execute(
                        """
                        INSERT INTO historical_keyword_metrics (
                            snapshot_date, keyword_id, keyword_text, country_code, source,
                            pipeline_execution_id, avg_monthly_searches, competition_level
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT DO NOTHING
                        """,
                        snapshot_date,
                        keyword_id,
                        metric['keyword'],
                        country_code,
                        'DATAFORSEO',
                        pipeline_execution_id,
                        metric['avg_monthly_searches'],
                        metric['competition_level']
                    )
                
                logger.info(f"💾 Stored {len(metrics)} DataForSEO metrics for {country_code}")
                
        except Exception as e:
            logger.error(f"❌ Failed to store DataForSEO metrics: {e}")
    
    async def close(self):
        """Close connections"""
        if self.client:
            await self.client.aclose()
            
        if self.redis_client:
            await self.redis_client.close()
    
    async def purge_keyword_metrics_cache(self):
        """Purge all keyword metrics from Redis cache"""
        if not self.redis_client:
            await self.initialize()
        
        try:
            # Find all keys matching our pattern
            keys = []
            async for key in self.redis_client.scan_iter(match="dataforseo:keywords:*"):
                keys.append(key)
            
            if keys:
                # Delete all matching keys
                await self.redis_client.delete(*keys)
                logger.info(f"🧹 Purged {len(keys)} keyword metrics from cache")
            else:
                logger.info("🧹 No keyword metrics found in cache to purge")
            
            return len(keys)
        except Exception as e:
            logger.error(f"❌ Failed to purge cache: {e}")
            return 0
