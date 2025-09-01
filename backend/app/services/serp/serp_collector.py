"""
SERP Collection Service using Scale SERP API
"""

import httpx
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import json
from loguru import logger

from app.core.config import settings as get_settings, Settings
from app.models.serp import SERPType
from app.core.database import get_db


class SERPCollector:
    """Scale SERP API client for collecting search results"""
    
    def __init__(self, settings=None, db=None, redis=None):
        if settings is None:
            settings = get_settings()
        self.settings = settings
        self.api_key = settings.scale_serp_api_key
        self.base_url = settings.scale_serp_base_url
        self.monthly_limit = settings.scale_serp_monthly_limit
        self.overusage_limit = settings.scale_serp_overusage_limit
        self.db = db
        self.redis = redis
        self.client = None  # Will be created when needed
        
    async def search(self, keyword: str, result_type: str = "organic", **kwargs) -> Dict:
        """
        Perform a search using Scale SERP API for specific result types
        
        Args:
            keyword: Search query
            result_type: Type of results to fetch ('organic', 'news', 'videos')
            **kwargs: Additional parameters (location, device, num_results, gl, hl, etc.)
            
        Returns:
            Dict containing flattened search results
        """
        # Extract parameters with defaults
        location = kwargs.get('location', 'United States')
        device = kwargs.get('device', 'desktop')
        num_results = kwargs.get('num_results', 50)
        gl = kwargs.get('gl', 'us')
        hl = kwargs.get('hl', 'en')
        
        params = {
            "api_key": self.api_key,
            "q": keyword,
            "location": location,
            "device": device,
            "num": num_results,
            "gl": gl,
            "hl": hl,
            "output": "json"
        }
        
        # Add search type specific parameters
        if result_type == "news":
            params["search_type"] = "news"
        elif result_type == "videos":
            params["search_type"] = "videos"
        # organic is the default, no special param needed
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in ['location', 'device', 'num_results', 'gl', 'hl', 'result_type']:
                params[key] = value
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # Log API usage
                await self._log_api_usage(keyword, response.headers)
                
                # Extract and flatten results based on type
                flattened_results = []
                
                if result_type == "organic":
                    results = data.get("organic_results", [])
                    for idx, result in enumerate(results):
                        flattened_results.append({
                            "position": idx + 1,
                            "title": result.get("title", ""),
                            "link": result.get("link", ""),
                            "domain": result.get("domain", ""),
                            "snippet": result.get("snippet", ""),
                            "displayed_link": result.get("displayed_link", ""),
                            "type": "organic"
                        })
                
                elif result_type == "news":
                    results = data.get("news_results", [])
                    for idx, result in enumerate(results):
                        # Extract domain from URL
                        url = result.get("link", "")
                        domain = ""
                        if url:
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            domain = parsed.netloc
                        
                        flattened_results.append({
                            "position": idx + 1,
                            "title": result.get("title", ""),
                            "link": url,
                            "domain": domain,
                            "source": result.get("source", ""),
                            "snippet": result.get("snippet", ""),
                            "date": result.get("date", ""),
                            "type": "news"
                        })
                
                elif result_type == "videos":
                    results = data.get("video_results", [])
                    for idx, result in enumerate(results):
                        # Extract domain from URL
                        url = result.get("link", "")
                        domain = ""
                        if url:
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            domain = parsed.netloc
                        
                        flattened_results.append({
                            "position": idx + 1,
                            "title": result.get("title", ""),
                            "link": url,
                            "domain": domain,
                            "displayed_link": result.get("displayed_link", ""),
                            "thumbnail": result.get("thumbnail", ""),
                            "duration": result.get("duration", ""),
                            "platform": result.get("platform", ""),
                            "date": result.get("date", ""),
                            "key_moments": result.get("key_moments", []),
                            "type": "video"
                        })
                
                return {
                    "success": True,
                    "keyword": keyword,
                    "result_type": result_type,
                    "total_results": len(flattened_results),
                    "results": flattened_results,
                    "search_metadata": {
                        "created_at": datetime.utcnow().isoformat(),
                        "device": device,
                        "location": location,
                        "query": keyword,
                        "num_results": num_results
                    }
                }
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Scale SERP API error for '{keyword}' ({result_type}): {e}")
                return {
                    "success": False,
                    "keyword": keyword,
                    "result_type": result_type,
                    "error": str(e),
                    "status_code": e.response.status_code
                }
                
            except Exception as e:
                import traceback
                logger.error(f"Unexpected error searching for '{keyword}' ({result_type}): {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return {
                    "success": False,
                    "keyword": keyword,
                    "result_type": result_type,
                    "error": str(e)
                }
    
    async def search_all_types(self, keyword: str, **kwargs) -> Dict:
        """
        Search for all types of results (organic, news, videos) in parallel
        
        Args:
            keyword: Search query
            **kwargs: Additional parameters passed to each search
            
        Returns:
            Dict containing all result types
        """
        # Run all searches in parallel
        results = await asyncio.gather(
            self.search(keyword, "organic", **kwargs),
            self.search(keyword, "news", **kwargs),
            self.search(keyword, "videos", **kwargs),
            return_exceptions=True
        )
        
        # Process results
        all_results = {
            "keyword": keyword,
            "success": True,
            "organic": {"results": [], "error": None},
            "news": {"results": [], "error": None},
            "videos": {"results": [], "error": None}
        }
        
        # Map results to their types
        result_types = ["organic", "news", "videos"]
        for result_type, result in zip(result_types, results):
            if isinstance(result, Exception):
                all_results[result_type]["error"] = str(result)
                all_results["success"] = False
            elif result.get("success"):
                all_results[result_type]["results"] = result.get("results", [])
            else:
                all_results[result_type]["error"] = result.get("error")
                all_results["success"] = False
        
        return all_results
    
    async def search_batch(
        self,
        keywords: List[str],
        location: str = "United States",
        device: str = "desktop",
        num_results: int = 50,
        delay_seconds: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Search multiple keywords with rate limiting
        
        Args:
            keywords: List of search queries
            location: Geographic location for search
            device: Device type (desktop/mobile)
            num_results: Number of results per keyword
            delay_seconds: Delay between requests
            
        Returns:
            List of search results
        """
        results = []
        
        for i, keyword in enumerate(keywords):
            # Add delay between requests (except for first)
            if i > 0:
                await asyncio.sleep(delay_seconds)
            
            result = await self.search(keyword, location, device, num_results)
            results.append(result)
            
            # Log progress
            logger.info(f"Searched {i+1}/{len(keywords)} keywords: '{keyword}'")
        
        return results
    
    async def _log_api_usage(self, keyword: str, headers: Dict) -> None:
        """
        Log API usage for tracking
        
        Args:
            keyword: Search keyword
            headers: Response headers from API
        """
        if not self.db:
            return
            
        try:
            # Extract quota info from headers if available
            quota_remaining = headers.get("X-API-Quota-Remaining")
            quota_limit = headers.get("X-API-Quota-Limit")
            
            await self.db.execute(
                """
                INSERT INTO api_usage (
                    id, api_name, service, endpoint, request_params, 
                    response_status, usage_date, created_at
                )
                VALUES (
                    gen_random_uuid(), 'scale_serp', 'scale_serp', '/search', 
                    $1, 200, CURRENT_DATE, NOW()
                )
                """,
                json.dumps({"keyword": keyword, "quota_remaining": quota_remaining})
            )
        except Exception as e:
            logger.warning(f"Failed to log API usage: {e}")
    
    async def check_quota(self) -> Dict[str, Any]:
        """
        Check API quota status from database
        
        Returns:
            Dict with quota information
        """
        if not self.db:
            return {
                "used": 0,
                "limit": self.monthly_limit,
                "remaining": self.monthly_limit,
                "percentage_used": 0,
                "in_overusage": False
            }
        
        try:
            # Get usage count from database for current month
            result = await self.db.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN response_status = 200 THEN 1 END) as successful_requests
                FROM api_usage
                WHERE service = 'scale_serp'
                AND created_at >= date_trunc('month', CURRENT_DATE)
                """
            )
            
            used = result['total_requests'] if result else 0
            remaining = max(0, self.monthly_limit - used)
            percentage_used = (used / self.monthly_limit * 100) if self.monthly_limit > 0 else 0
            
            return {
                "used": used,
                "limit": self.monthly_limit,
                "remaining": remaining,
                "percentage_used": round(percentage_used, 2),
                "overusage_limit": self.overusage_limit,
                "in_overusage": used > self.monthly_limit
            }
            
        except Exception as e:
            logger.error(f"Failed to check quota: {e}")
            return {
                "used": 0,
                "limit": self.monthly_limit,
                "remaining": self.monthly_limit,
                "percentage_used": 0,
                "in_overusage": False,
                "error": str(e)
            }
    
    async def store_results(
        self,
        keyword_id: str,
        results: List[Dict],
        search_metadata: Dict = None,
        serp_type: str = "organic"
    ) -> bool:
        """
        Store SERP results in database
        
        Args:
            keyword_id: UUID of the keyword
            results: List of flattened SERP results
            serp_type: Type of SERP results (default: organic)
            
        Returns:
            bool: Success status
        """
        if not self.db:
            logger.warning("No database connection available for storing results")
            return False
            
        try:
            # Store each result
            for result in results:
                # Get client_id from metadata
                client_id = search_metadata.get("client_id", "ncino")
                
                await self.db.execute(
                    """
                    INSERT INTO serp_results (
                        client_id, keyword_id, search_date, serp_type,
                        position, url, title, snippet, domain, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    client_id,
                    keyword_id,
                    search_metadata.get("search_date", datetime.now().date()),
                    result.get("type", serp_type),  # result_type
                    result.get("position"),
                    result.get("link", ""),
                    result.get("title", "")[:500],  # Limit title length
                    result.get("snippet", ""),
                    result.get("domain", "")
                )
            
            logger.info(f"Stored {len(results)} SERP results for keyword {keyword_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store SERP results: {e}")
            return False 