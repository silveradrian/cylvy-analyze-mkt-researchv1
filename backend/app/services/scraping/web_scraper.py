import httpx
from bs4 import BeautifulSoup
import trafilatura
from typing import Dict, Optional, List, Any
from urllib.parse import urljoin, urlparse
import asyncio
from datetime import datetime
import hashlib
import json
from loguru import logger
import redis.asyncio as redis
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings, Settings
from app.core.database import DatabasePool


class WebScraper:
    """Web scraping service supporting multiple engines"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        self.scrapingbee_api_key = settings.scrapingbee_api_key
        self.redis_client = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        self.js_domains = {
            'linkedin.com',
            'facebook.com',
            'instagram.com',
            'twitter.com',
            'medium.com',
            'forbes.com',
            'bloomberg.com',
            'wsj.com',
            'x.com'
        }
    
    async def scrape(
        self,
        url: str,
        use_javascript: bool = False,
        check_cache: bool = True,
        force_scrapingbee: bool = False
    ) -> Dict:
        """Scrape content from a URL"""
        
        # Check cache first
        if check_cache and self.redis_client:
            cached = await self._get_from_cache(url)
            if cached:
                logger.info(f"Cache hit for {url}")
                return cached
        
        # Check if ScrapingBee-only mode is enabled
        if self.settings.scrapingbee_only and self.settings.scrapingbee_enabled and self.scrapingbee_api_key:
            logger.info(f"Scraping {url} with ScrapingBee (scrapingbee_only mode)")
            result = await self._scrape_with_scrapingbee(url)
        elif force_scrapingbee and self.scrapingbee_api_key:
            logger.info(f"Scraping {url} with ScrapingBee (forced)")
            result = await self._scrape_with_scrapingbee(url, use_javascript=use_javascript)
        elif (use_javascript or force_scrapingbee or self._requires_javascript(url)) and self.settings.scrapingbee_enabled and self.scrapingbee_api_key:
            logger.info(f"Scraping {url} with ScrapingBee (JS rendering)")
            result = await self._scrape_with_scrapingbee(url, use_javascript=True)
        else:
            logger.info(f"Scraping {url} with direct HTTP")
            result = await self._scrape_direct(url)
        
        # Cache the result
        if result and result.get('content') and self.redis_client:
            await self._cache_result(url, result)
        
        return result
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _scrape_direct(self, url: str) -> Dict:
        """Direct HTTP scraping without JavaScript"""
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                # Extract content using trafilatura
                content_data = {}
                extracted = trafilatura.extract(
                    response.text,
                    include_comments=False,
                    include_tables=True,
                    deduplicate=True,
                    output_format='json',
                    favor_recall=True
                )
                
                if extracted:
                    content_data = json.loads(extracted)
                else:
                    # Fallback to BeautifulSoup
                    content_data = self._extract_with_beautifulsoup(response.text)
                
                # Get metadata
                soup = BeautifulSoup(response.text, 'html.parser')
                metadata = self._extract_metadata(soup)
                
                return {
                    "url": str(response.url),
                    "final_url": str(response.url),
                    "status_code": response.status_code,
                    "title": content_data.get('title') or metadata.get('title', ''),
                    "meta_description": metadata.get('description', ''),
                    "content": content_data.get('text', ''),
                    "word_count": len(content_data.get('text', '').split()),
                    "content_type": response.headers.get('content-type', 'text/html'),
                    "scraped_at": datetime.utcnow().isoformat(),
                    "engine": "direct",
                    "metadata": metadata,
                    "error": None
                }
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error scraping {url}: {e}")
                return {
                    "url": url,
                    "status_code": e.response.status_code if e.response else None,
                    "error": f"HTTP {e.response.status_code}: {str(e)}",
                    "scraped_at": datetime.utcnow().isoformat(),
                    "engine": "direct"
                }
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return {
                    "url": url,
                    "status_code": None,
                    "error": str(e),
                    "scraped_at": datetime.utcnow().isoformat(),
                    "engine": "direct"
                }
    
    async def _scrape_with_scrapingbee(self, url: str, use_javascript: bool = True) -> Dict[str, Any]:
        """Scrape using ScrapingBee API"""
        if not self.scrapingbee_api_key:
            raise Exception("ScrapingBee API key not configured")
        
        # Determine if we need special proxy based on domain
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Sites that need premium/stealth proxy
        protected_sites = [
            'openai.com', 'linkedin.com', 'facebook.com', 'instagram.com',
            'twitter.com', 'amazon.com', 'google.com', 'microsoft.com',
            'medium.com', 'reddit.com', 'quora.com'
        ]
        
        # Heavy sites that need longer timeout
        heavy_sites = ['openai.com', 'linkedin.com', 'medium.com', 'twitter.com']
        
        # Check if we need special proxy
        use_special_proxy = any(site in domain for site in protected_sites)
        is_heavy_site = any(site in domain for site in heavy_sites)
        
        # Set timeout based on site
        timeout = 60.0 if is_heavy_site else 30.0  # 60s for heavy sites, 30s for others
        
        # Try different proxy levels based on site protection needs
        proxy_attempts = []
        if use_special_proxy:
            # For protected sites, start with premium proxy
            proxy_attempts = [
                ('premium_proxy', 'premium'),
                ('stealth_proxy', 'stealth')
            ]
        else:
            # For regular sites, start with standard but always have fallbacks
            proxy_attempts = [
                ('premium_proxy', 'false'),    # Standard proxy
                ('premium_proxy', 'premium'),   # Fallback to premium
                ('stealth_proxy', 'stealth')    # Ultimate fallback to stealth
            ]
        
        last_error = None
        
        for proxy_param, proxy_value in proxy_attempts:
            params = {
                'api_key': self.scrapingbee_api_key,
                'url': url,
                'render_js': 'true' if use_javascript else 'false',
                'country_code': 'us',
                'wait': '3000' if use_javascript else '0',  # Increased wait for JS
                'block_ads': 'true',
                'timeout': str(int(timeout * 1000))  # Convert to milliseconds
            }
            
            # Add proxy parameter
            if proxy_value != 'false':
                params[proxy_param] = 'true'
                logger.info(f"Using {proxy_value} proxy for {domain}")
            else:
                params['premium_proxy'] = 'false'
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    response = await client.get(
                        'https://app.scrapingbee.com/api/v1',
                        params=params
                    )
                    
                    if response.status_code == 401:
                        logger.error("ScrapingBee: Invalid API key")
                        raise Exception("Invalid ScrapingBee API key")
                    elif response.status_code == 402:
                        logger.error("ScrapingBee: Account limit reached")
                        raise Exception("ScrapingBee account limit reached")
                    elif response.status_code == 429:
                        logger.error("ScrapingBee: Rate limit exceeded")
                        raise Exception("ScrapingBee rate limit exceeded")
                    elif response.status_code == 503:
                        logger.warning(f"ScrapingBee {proxy_value} proxy returned 503, trying next option")
                        last_error = f"{proxy_value} proxy unavailable"
                        continue
                    elif response.status_code != 200:
                        logger.warning(f"ScrapingBee error with {proxy_value}: {response.status_code}")
                        last_error = f"HTTP {response.status_code}"
                        if proxy_value != 'stealth':  # Only log fallback if not on last attempt
                            logger.info(f"Attempting fallback to next proxy level for {domain}")
                        continue
                    
                    # Process the HTML
                    content_data = {}
                    extracted = trafilatura.extract(
                        response.text,
                        include_comments=False,
                        include_tables=True,
                        output_format='json'
                    )
                    
                    if extracted:
                        import json
                        content_json = json.loads(extracted)
                        # Try different keys for content
                        content_data['content'] = (
                            content_json.get('text', '') or 
                            content_json.get('raw', '') or 
                            content_json.get('content', '')
                        )
                        content_data['title'] = content_json.get('title', '')
                        content_data['author'] = content_json.get('author', '')
                        content_data['date'] = content_json.get('date', '')
                    else:
                        # Fallback to basic extraction
                        soup = BeautifulSoup(response.text, 'html.parser')
                        content_data['title'] = soup.find('title').text if soup.find('title') else ''
                        # Extract text from body, removing scripts and styles
                        for script in soup(["script", "style"]):
                            script.decompose()
                        content_data['content'] = soup.get_text(strip=True, separator=' ')
                    
                    # Ensure we have content
                    if not content_data.get('content'):
                        # Try alternative extraction
                        extracted_simple = trafilatura.extract(response.text)
                        if extracted_simple:
                            content_data['content'] = extracted_simple
                    
                    content_data['success'] = True
                    content_data['html'] = response.text
                    content_data['engine'] = 'scrapingbee'
                    content_data['proxy_type'] = proxy_value
                    
                    proxy_desc = "standard" if proxy_value == 'false' else proxy_value
                    logger.info(f"Successfully scraped {url} with {proxy_desc} proxy")
                    return content_data
                    
                except httpx.ReadTimeout:
                    logger.error(f"ScrapingBee timeout for {url} with {proxy_value} proxy")
                    last_error = f"Request timed out after {timeout} seconds"
                    continue
                except Exception as e:
                    logger.error(f"ScrapingBee error with {proxy_value}: {str(e)}")
                    last_error = str(e)
                    continue
        
        # All attempts failed
        raise Exception(f"All proxy attempts failed. Last error: {last_error}")
    
    def _extract_with_beautifulsoup(self, html: str) -> Dict:
        """Extract content using BeautifulSoup as fallback"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        
        # Get title
        title = soup.find('title')
        title_text = title.text.strip() if title else ''
        
        # Get main content
        # Try to find main content areas
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=['content', 'main-content', 'article-body'])
        
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
        else:
            # Fallback to body
            text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return {
            'title': title_text,
            'text': text
        }
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extract metadata from HTML"""
        metadata = {}
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.text.strip()
        
        # Meta description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            metadata['description'] = desc_tag.get('content', '')
        
        # Open Graph data
        og_tags = soup.find_all('meta', attrs={'property': lambda x: x and x.startswith('og:')})
        for tag in og_tags:
            property_name = tag.get('property', '').replace('og:', '')
            if property_name:
                metadata[f'og_{property_name}'] = tag.get('content', '')
        
        # Author
        author = soup.find('meta', attrs={'name': 'author'})
        if author:
            metadata['author'] = author.get('content', '')
        
        # Published date
        pub_date = soup.find('meta', attrs={'property': 'article:published_time'})
        if pub_date:
            metadata['published_date'] = pub_date.get('content', '')
        
        # Keywords
        keywords = soup.find('meta', attrs={'name': 'keywords'})
        if keywords:
            metadata['keywords'] = keywords.get('content', '')
        
        # Canonical URL
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical:
            metadata['canonical_url'] = canonical.get('href', '')
        
        return metadata
    
    def _requires_javascript(self, url: str) -> bool:
        """Determine if URL requires JavaScript rendering"""
        domain = urlparse(url).netloc.lower()
        return any(js_domain in domain for js_domain in self.js_domains)
    
    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL"""
        return f"scrape:{hashlib.md5(url.encode()).hexdigest()}"
    
    async def _get_from_cache(self, url: str) -> Optional[Dict]:
        """Get scraped content from cache"""
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(url)
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.error(f"Cache get error: {e}")
        return None
    
    async def _cache_result(self, url: str, result: Dict):
        """Cache scraped content for 7 days"""
        if self.redis_client and result.get('content'):
            try:
                cache_key = self._get_cache_key(url)
                await self.redis_client.setex(
                    cache_key,
                    604800,  # 7 days
                    json.dumps(result)
                )
            except Exception as e:
                logger.error(f"Cache set error: {e}")
    
    async def batch_scrape(
        self,
        urls: List[str],
        max_concurrent: int = 5,
        use_javascript: bool = False
    ) -> Dict[str, Dict]:
        """Scrape multiple URLs concurrently"""
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}
        
        async def scrape_with_semaphore(url: str):
            async with semaphore:
                try:
                    result = await self.scrape(url, use_javascript)
                    results[url] = result
                except Exception as e:
                    logger.error(f"Batch scrape error for {url}: {e}")
                    results[url] = {
                        "url": url,
                        "error": str(e),
                        "scraped_at": datetime.utcnow().isoformat()
                    }
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        await asyncio.gather(*tasks)
        
        return results 