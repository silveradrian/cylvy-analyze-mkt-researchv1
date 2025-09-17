import httpx
from bs4 import BeautifulSoup
import trafilatura
from typing import Dict, Optional, List, Any
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
import asyncio
from datetime import datetime
import hashlib
import json
from loguru import logger
import redis.asyncio as redis
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings, Settings
from app.core.database import DatabasePool
from app.services.scraping.document_parser import DocumentParser


class WebScraper:
    """Web scraping service supporting multiple engines"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        self.scrapingbee_api_key = settings.SCRAPINGBEE_API_KEY
        # Initialize Redis cache client if available
        try:
            redis_url = getattr(self.settings, 'REDIS_URL', None) or 'redis://redis:6379/0'
            self.redis_client = redis.from_url(redis_url)
            logger.info(f"Initialized Redis cache client: {redis_url}")
        except Exception as e:
            self.redis_client = None
            logger.warning(f"Redis initialization failed: {e}")
        self.document_parser = DocumentParser()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        # Simple per-domain circuit breaker memory (process-local)
        self._domain_failures: Dict[str, int] = {}
        self._circuit_open_until: Dict[str, float] = {}
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
        # Document file extensions
        self.document_extensions = {'.pdf', '.docx', '.doc'}
        # Concurrency limiter for ScrapingBee - use DEFAULT_SCRAPER_CONCURRENT_LIMIT or 50
        try:
            max_sb_conc = int(getattr(self.settings, 'DEFAULT_SCRAPER_CONCURRENT_LIMIT', 50) or 50)
            logger.info(f"ScrapingBee concurrency limit set to: {max_sb_conc}")
        except Exception:
            max_sb_conc = 50
            logger.warning(f"Using default ScrapingBee concurrency: {max_sb_conc}")
        self._scrapingbee_semaphore = asyncio.Semaphore(max_sb_conc)
    
    async def scrape(
        self,
        url: str,
        use_javascript: bool = False,
        check_cache: bool = True,
        force_scrapingbee: bool = False
    ) -> Dict:
        """Scrape content from a URL or document"""
        # Normalize URL to improve cache hit rate and avoid duplicate scrapes
        url = self._normalize_url(url)
        
        # Check if URL points to a document
        if self._is_document_url(url):
            logger.info(f"Detected document URL: {url}")
            # Always route documents to the document parser. Do NOT send to ScrapingBee.
            return await self._scrape_document(url)
        
        # Check cache first
        if check_cache and self.redis_client:
            cached = await self._get_from_cache(url)
            if cached:
                logger.info(f"Cache hit for {url}")
                return cached
        
        # Always use ScrapingBee for non-document URLs
        scrapingbee_enabled = getattr(self.settings, 'scrapingbee_enabled', True)
        if not self.scrapingbee_api_key or not scrapingbee_enabled:
            raise Exception("ScrapingBee is required but not configured or disabled")
        # Prefer JS rendering by default for higher success; ScrapingBee handles non-JS quickly too
        logger.info(f"Scraping {url} with ScrapingBee (JS by default)")
        async with self._scrapingbee_semaphore:
            result = await self._scrape_with_scrapingbee(url, use_javascript=True)
        
        # Cache or purge based on result quality
        if self.redis_client:
            content_text = (result or {}).get('content') if result else None
            has_quality_content = isinstance(content_text, str) and len(content_text.strip()) >= 100
            if has_quality_content:
                await self._cache_result(url, result)
            else:
                # Ensure failed/empty results are not left in cache
                try:
                    await self._delete_cache(url)
                except Exception:
                    pass
        
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
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _scrape_with_scrapingbee(self, url: str, use_javascript: bool = True) -> Dict[str, Any]:
        """Scrape using ScrapingBee API"""
        if not self.scrapingbee_api_key:
            raise Exception("ScrapingBee API key not configured")
        
        # Determine if we need special proxy based on domain
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        # Circuit breaker: if domain is open (too many recent failures), short-circuit fast
        import time
        now = time.time()
        open_until = self._circuit_open_until.get(domain)
        if open_until and now < open_until:
            wait_seconds = int(open_until - now)
            logger.warning(f"Circuit open for {domain}; skipping scrape for {wait_seconds}s")
            return {
                "url": url,
                "status_code": 503,
                "error": f"circuit_open:{wait_seconds}s",
                "scraped_at": datetime.utcnow().isoformat(),
                "engine": "scrapingbee",
                "proxy_type": "n/a"
            }
        
        # Sites that need premium/stealth proxy
        protected_sites = [
            'openai.com', 'linkedin.com', 'facebook.com', 'instagram.com',
            'twitter.com', 'amazon.com', 'google.com', 'microsoft.com',
            'medium.com', 'reddit.com', 'quora.com'
        ]
        
        # Heavy sites that need longer timeout
        heavy_sites = ['openai.com', 'linkedin.com', 'medium.com', 'twitter.com', 'kpmg.com', 'capgemini.com']
        
        # Check if we need special proxy
        use_special_proxy = any(site in domain for site in protected_sites)
        is_heavy_site = any(site in domain for site in heavy_sites)
        
        # Set timeout based on site
        timeout = 90.0 if is_heavy_site else 45.0  # increase timeouts to improve yield
        
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
                    elif response.status_code in (404, 410):
                        # Permanent/not found – do not retry other proxies
                        logger.warning(f"ScrapingBee non-retryable {response.status_code} for {url} with {proxy_value} proxy")
                        return {
                            "url": url,
                            "status_code": response.status_code,
                            "error": f"HTTP {response.status_code}",
                            "scraped_at": datetime.utcnow().isoformat(),
                            "engine": "scrapingbee",
                            "proxy_type": proxy_value
                        }
                    elif response.status_code != 200:
                        logger.warning(f"ScrapingBee error with {proxy_value}: {response.status_code}")
                        last_error = f"HTTP {response.status_code}"
                        if proxy_value != 'stealth':  # Only log fallback if not on last attempt
                            logger.info(f"Attempting fallback to next proxy level for {domain}")
                        # brief backoff on 5xx to reduce hammering
                        if 500 <= response.status_code < 600:
                            try:
                                await asyncio.sleep(0.5)
                            except Exception:
                                pass
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
                    
                    # Always extract basic metadata for description
                    try:
                        soup_md = BeautifulSoup(response.text, 'html.parser')
                        md = self._extract_metadata(soup_md)
                    except Exception:
                        md = {}

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
                    content_data['status_code'] = 200
                    content_data['url'] = url
                    content_data['final_url'] = url
                    content_data['meta_description'] = md.get('description', '')
                    try:
                        content_data['word_count'] = len((content_data.get('content') or '').split())
                    except Exception:
                        content_data['word_count'] = 0
                    
                    proxy_desc = "standard" if proxy_value == 'false' else proxy_value
                    logger.info(f"Successfully scraped {url} with {proxy_desc} proxy")
                    # Reset circuit breaker on success
                    self._domain_failures.pop(domain, None)
                    self._circuit_open_until.pop(domain, None)
                    return content_data
                    
                except httpx.ReadTimeout:
                    logger.error(f"ScrapingBee timeout for {url} with {proxy_value} proxy")
                    last_error = f"Request timed out after {timeout} seconds"
                    continue
                except Exception as e:
                    logger.error(f"ScrapingBee error with {proxy_value}: {str(e)}")
                    last_error = str(e)
                    continue
        
        # All attempts failed: increment domain failures and possibly open circuit
        failures = self._domain_failures.get(domain, 0) + 1
        self._domain_failures[domain] = failures
        # Exponential open window: 3, 6, 12, 24 seconds (cap 60s)
        backoff_seconds = min(3 * (2 ** max(failures - 1, 0)), 60)
        if failures >= 3:
            self._circuit_open_until[domain] = time.time() + backoff_seconds
            logger.warning(f"Opening circuit for {domain} for {backoff_seconds}s after {failures} failures")
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
    
    def _is_document_url(self, url: str) -> bool:
        """Check if URL points to a document file"""
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        query = (parsed_url.query or '').lower()
        
        # Check file extension
        for ext in self.document_extensions:
            if path.endswith(ext):
                return True
        # Heuristic: many PDFs carry params like ?pdf=download or append extra segments
        if '.pdf' in path or '.pdf' in query:
            return True
        
        # Check content-type if we can do a HEAD request
        # (This is done in _scrape_document to avoid extra requests)
        return False
    
    async def _scrape_document(self, url: str) -> Dict:
        """Scrape content from a document (PDF, Word, etc.)"""
        try:
            # Prefer extension heuristic; only use HEAD to refine, never to fall back to HTML
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    head_response = await client.head(url, headers=self.headers, follow_redirects=True)
                    content_type = head_response.headers.get('content-type', '').lower()
                    if any(doc_type in content_type for doc_type in ['pdf', 'document', 'msword', 'wordprocessingml']):
                        pass  # Confirmed as document
            except Exception:
                # Ignore HEAD failures and continue to document parsing
                content_type = ''

            # Parse the document (download and extract text)
            result = await self.document_parser.parse_document_from_url(url)
            
            # Transform result to match expected scraping format
            if result.get('error'):
                return {
                    "url": url,
                    "final_url": url,
                    "status_code": 500,
                    "title": f"Document: {url.split('/')[-1]}",
                    "meta_description": "",
                    "content": "",
                    "word_count": 0,
                    "content_type": result.get('document_type', 'document'),
                    "scraped_at": datetime.utcnow().isoformat(),
                    "engine": "document_parser",
                    "metadata": {},
                    "error": result.get('error')
                }
            
            # Success case
            content = result.get('content', '')
            filename = url.split('/')[-1]
            
            return {
                "url": url,
                "final_url": url,
                "status_code": 200,
                "title": f"Document: {filename}",
                "meta_description": f"{result.get('document_type', 'document').upper()} document with {result.get('word_count', 0)} words",
                "content": content,
                "word_count": result.get('word_count', 0),
                "content_type": result.get('document_type', 'document'),
                "scraped_at": datetime.utcnow().isoformat(),
                "engine": "document_parser",
                "metadata": {
                    "page_count": result.get('page_count', 0),
                    "paragraph_count": result.get('paragraph_count', 0),
                    "table_count": result.get('table_count', 0),
                    "document_type": result.get('document_type', 'unknown')
                },
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error scraping document {url}: {e}")
            return {
                "url": url,
                "final_url": url,
                "status_code": 500,
                "title": f"Document: {url.split('/')[-1]}",
                "meta_description": "",
                "content": "",
                "word_count": 0,
                "content_type": "document",
                "scraped_at": datetime.utcnow().isoformat(),
                "engine": "document_parser",
                "metadata": {},
                "error": str(e)
            }
    
    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL"""
        normalized = self._normalize_url(url)
        return f"scrape:{hashlib.md5(normalized.encode()).hexdigest()}"

    def _normalize_url(self, url: str) -> str:
        """Normalize URLs by stripping tracking params, fragments, and standardizing host.

        Keeps functional query params but removes common trackers (utm_*, gclid, fbclid, etc.).
        """
        try:
            parsed = urlparse(url)
            # Lowercase scheme and netloc
            scheme = (parsed.scheme or 'http').lower()
            netloc = parsed.netloc.lower()
            # Remove default ports
            if netloc.endswith(':80') and scheme == 'http':
                netloc = netloc[:-3]
            if netloc.endswith(':443') and scheme == 'https':
                netloc = netloc[:-4]

            # Strip common tracking parameters
            tracking_prefixes = ('utm_',)
            tracking_exact = {
                'gclid', 'fbclid', 'msclkid', 'yclid', 'mc_cid', 'mc_eid', 'mkt_tok',
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'ref', 'ref_src', 'spm', 'igshid'
            }
            query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
            filtered = []
            for k, v in query_pairs:
                lk = k.lower()
                if lk in tracking_exact or any(lk.startswith(p) for p in tracking_prefixes):
                    continue
                filtered.append((k, v))
            # Sort for stability
            filtered.sort()
            query = urlencode(filtered, doseq=True)

            # Remove fragment
            fragment = ''

            # Normalize path: remove trailing slash except root
            path = parsed.path or '/'
            if path != '/' and path.endswith('/'):
                path = path[:-1]

            normalized = urlunparse((scheme, netloc, path, '', query, fragment))
            return normalized
        except Exception:
            return url
    
    async def _get_from_cache(self, url: str) -> Optional[Dict]:
        """Get scraped content from cache"""
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(url)
                cached = await self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Validate cached payload has usable content; otherwise purge and ignore
                    content_text = data.get('content') if isinstance(data, dict) else None
                    if not isinstance(content_text, str) or len(content_text.strip()) < 100 or data.get('error'):
                        try:
                            await self.redis_client.delete(cache_key)
                        except Exception:
                            pass
                        return None
                    return data
            except Exception as e:
                logger.error(f"Cache get error: {e}")
        return None
    
    async def _cache_result(self, url: str, result: Dict):
        """Cache scraped content for 7 days"""
        if self.redis_client and isinstance(result.get('content'), str) and len(result.get('content').strip()) >= 100:
            try:
                cache_key = self._get_cache_key(url)
                await self.redis_client.setex(
                    cache_key,
                    604800,  # 7 days
                    json.dumps(result)
                )
            except Exception as e:
                logger.error(f"Cache set error: {e}")

    async def _delete_cache(self, url: str) -> None:
        """Delete a cached entry for a URL if present"""
        if not self.redis_client:
            return
        try:
            cache_key = self._get_cache_key(url)
            await self.redis_client.delete(cache_key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
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