"""
Enhanced Company Enrichment Service with Robustness Features
Includes circuit breaker, retry logic, and detailed logging
"""

import httpx
import time
from collections import deque
import inspect
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import json
import re
import asyncio
from loguru import logger
import redis.asyncio as redis
import openai
from uuid import uuid4

from app.core.config import Settings
from app.core.database import DatabasePool
from app.models.company import (
    CompanyProfile, CompanySearchResult, CompanyEnrichmentResult,
    BatchEnrichmentResult
)
from app.core.robustness_logging import get_logger, log_performance


class _AsyncRateLimiter:
    """Simple async sliding-window rate limiter.
    Ensures no more than max_requests occur within window_seconds.
    """
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        while True:
            async with self._lock:
                now = time.monotonic()
                # Drop timestamps outside the window
                while self._timestamps and now - self._timestamps[0] >= self.window_seconds:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return

                # Need to wait until the oldest timestamp expires
                sleep_time = self.window_seconds - (now - self._timestamps[0])
            await asyncio.sleep(max(0.0, sleep_time))


class EnhancedCompanyEnricher:
    """Company enrichment service with robustness features"""
    
    def __init__(
        self, 
        settings: Settings, 
        db: DatabasePool,
        circuit_breaker=None,
        retry_manager=None,
        redis_client=None
    ):
        self.settings = settings
        self.db = db
        self.api_key = settings.COGNISM_API_KEY
        
        # Workaround for API key parsing issue
        if self.api_key and self.api_key.startswith("PI-P-"):
            self.api_key = "A" + self.api_key
            logger.warning("Applied workaround for API key parsing issue")
        
        self.base_url = "https://app.cognism.com/api"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Robustness services
        self.circuit_breaker = circuit_breaker
        self.retry_manager = retry_manager
        self.redis_client = redis_client
        self.logger = get_logger("company_enricher")
        self.rate_limiter = _AsyncRateLimiter(max_requests=1000, window_seconds=60.0)
        
        # Initialize Redis client if not provided
        if self.redis_client is None:
            try:
                redis_url = getattr(self.settings, 'REDIS_URL', None) or 'redis://redis:6379/0'
                # If running in Docker, prefer the docker network host name
                if 'localhost' in redis_url:
                    redis_url = 'redis://redis:6379/0'
                self.redis_client = redis.from_url(redis_url)
                logger.info(f"Initialized Redis cache client for company enricher: {redis_url}")
            except Exception as e:
                self.redis_client = None
                logger.warning(f"Company enricher Redis initialization failed: {e}")
    
    async def _fallback_none(self, *args, **kwargs):
        """Async fallback used by circuit breaker to ensure awaitable return."""
        return None

    @log_performance("company_enricher", "enrich_domain")
    async def enrich_domain(
        self, 
        domain: str, 
        country: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[CompanyProfile]:
        """Enrich company data from domain with robustness"""
        
        # Store original domain and get cleaned domain for Cognism lookup
        original_domain = domain
        cleaned_domain = self._clean_domain(domain)
        
        self.logger.debug(
            f"Starting domain enrichment",
            original_domain=original_domain,
            cleaned_domain=cleaned_domain,
            country=country,
            force_refresh=force_refresh
        )
        
        # Check cache first if not forcing refresh (use original domain for cache)
        if not force_refresh:
            cached = await self._get_from_cache(original_domain)
            if cached:
                self.logger.info(f"Cache hit for domain", domain=original_domain)
                return cached
        
        # Use circuit breaker if available (search with cleaned domain)
        if self.circuit_breaker:
            try:
                cb_result = self.circuit_breaker.call(
                    self._search_company_with_retry,
                    cleaned_domain,
                    country,
                    fallback=self._fallback_none
                )
                company_data = await cb_result if inspect.isawaitable(cb_result) else cb_result
            except Exception as e:
                self.logger.error(
                    "Company search failed with circuit breaker",
                    original_domain=original_domain,
                    cleaned_domain=cleaned_domain,
                    error=e
                )
                return None
        else:
            company_data = await self._search_company_with_retry(cleaned_domain, country)
        
        if company_data:
            # Update company data to use original domain for storage
            company_data.domain = original_domain
            
            # Enrich with additional data
            enriched = await self._enrich_company_data(company_data)
            
            # Classify source type
            source_type = await self._classify_source_type(enriched, original_domain)
            enriched.source_type = source_type
            
            # Store in database (with original domain)
            await self._store_company_profile(enriched)
            
            # Cache result (with original domain)
            await self._cache_result(original_domain, enriched)
            
            self.logger.info(
                f"Successfully enriched domain",
                original_domain=original_domain,
                cleaned_domain=cleaned_domain,
                company_name=enriched.company_name,
                employees=enriched.headcount
            )
            
            return enriched
        
        self.logger.warning(f"No company found for domain, creating fallback", 
                          original_domain=original_domain, 
                          cleaned_domain=cleaned_domain)
        
        # Create fallback company profile
        fallback_profile = await self._create_fallback_profile(original_domain)
        
        # Store in database
        await self._store_company_profile(fallback_profile)
        
        # Cache result
        await self._cache_result(original_domain, fallback_profile)
        
        return fallback_profile
    
    def _clean_domain(self, domain: str) -> str:
        """Clean and normalize domain to primary domain for Cognism lookup"""
        # Remove protocol and www
        domain = domain.replace('http://', '').replace('https://', '')
        domain = domain.replace('www.', '')
        domain = domain.split('/')[0].lower()
        
        # Extract primary domain from subdomains
        # For subdomains like business.hsbc.uk, we want hsbc.uk
        # For domains like example.co.uk, we want example.co.uk
        parts = domain.split('.')
        
        if len(parts) >= 3:
            # Check for multi-part TLDs like .co.uk, .com.au, .org.uk
            if len(parts) >= 3 and parts[-2] in ['co', 'com', 'net', 'org', 'gov', 'edu', 'ac']:
                # Keep last 3 parts for multi-part TLD (e.g., hsbc.co.uk)
                primary_domain = '.'.join(parts[-3:])
            else:
                # Keep last 2 parts for regular TLD (e.g., hsbc.com)
                primary_domain = '.'.join(parts[-2:])
        else:
            # Already a primary domain
            primary_domain = domain
        
        self.logger.debug(f"Domain cleaning: {domain} → {primary_domain}")
        return primary_domain
    
    async def _create_fallback_profile(self, original_domain: str) -> CompanyProfile:
        """Create a fallback company profile from domain"""
        # Use the cleaned primary domain for better company name extraction
        primary_domain = self._clean_domain(original_domain)
        
        # Extract company name from primary domain (not subdomain)
        # For hsbc.uk → "HSBC", not "Business" from business.hsbc.uk
        company_name = primary_domain.split('.')[0].replace('-', ' ').title()
        
        # Create minimal profile using original domain but better company name
        fallback_profile = CompanyProfile(
            domain=original_domain,  # Store original domain
            company_name=company_name,  # Use primary domain for name
            source="fallback",
            source_type="OTHER",  # Use standard classification
            website=f"https://{original_domain}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.logger.info(f"Created fallback profile for {original_domain} → {primary_domain}: {company_name}")
        
        return fallback_profile
    
    async def _select_best_company_match(self, companies: List[Dict], domain: str) -> Dict:
        """AI-powered company profile selection based on brand alignment to domain
        
        Uses OpenAI to select the company profile that is most aligned with the domain's brand,
        ignoring holding companies and focusing on operating brands.
        """
        if len(companies) == 1:
            return companies[0]
        
        if not self.settings.OPENAI_API_KEY:
            # Fallback to simple domain matching if no OpenAI
            domain_root = domain.replace('www.', '').split('.')[0].lower()
            for company in companies:
                if domain_root in company.get("name", "").lower():
                    return company
            return companies[0]
        
        try:
            # Prepare company context for AI analysis
            company_context = []
            for i, company in enumerate(companies, 1):
                name = company.get("name", "Unknown")
                industry = company.get("industry", "Unknown")
                employees = company.get("sizeFrom", 0) or 0
                description = company.get("description", "No description")[:200]
                
                company_context.append(f"""
Company {i}:
- Name: {name}
- Industry: {industry}
- Employees: {employees:,}
- Description: {description}
""")
            
            companies_text = "\n".join(company_context)
            
            prompt = f"""This domain "{domain}" has returned {len(companies)} associated company profiles from Cognism API. Please select the company profile and brand name that is MOST ALIGNED with the domain brand.

SELECTION GUIDELINES:
1. Prioritize the OPERATING COMPANY/BRAND over holding companies, investors, or parent corporations
2. Choose the company whose brand name is most directly associated with the domain
3. Ignore financial holding companies, private equity firms, and investment companies
4. For well-known brands, choose the brand itself over its corporate parent

EXAMPLES:
- finastra.com → Choose "Finastra" (operating brand) NOT "Vista Equity Partners" (holding company)
- redhat.com → Choose "Red Hat" (brand) NOT "IBM" (parent owner)
- securityintelligence.com → Choose "IBM" (since this is IBM's content platform, not a separate brand)

COMPANY PROFILES AVAILABLE:
{companies_text}

Return JSON with:
{{
    "selected_company_number": 1-{len(companies)},
    "company_name": "Selected company name",
    "reasoning": "Brief explanation of why this profile best represents the domain brand"
}}

Focus on brand alignment, not corporate ownership."""
            
            # Use OpenAI for intelligent selection
            from openai import OpenAI
            client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: client.chat.completions.create(
                        model="gpt-4o-mini",  # Fast, cheap model
                        messages=[
                            {"role": "system", "content": "You are an expert at identifying which company profile best represents a domain's brand identity. Focus on operating brands over financial ownership. Always return valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=300,
                        temperature=0.1
                    )
                ),
                timeout=30
            )
            
            # Parse AI response
            content = response.choices[0].message.content.strip()
            
            try:
                # Handle markdown code fences
                if content.startswith('```json'):
                    start_idx = content.find('{')
                    end_idx = content.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        content = content[start_idx:end_idx+1]
                
                result = json.loads(content)
                
                selected_index = result.get('selected_company_number', 1) - 1  # Convert to 0-based
                selected_company = companies[selected_index] if 0 <= selected_index < len(companies) else companies[0]
                
                self.logger.debug(
                    f"AI selected best company match",
                    domain=domain,
                    selected_company=selected_company.get("name"),
                    reasoning=result.get('reasoning', 'No reasoning provided'),
                    total_candidates=len(companies)
                )
                
                return selected_company
                
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                self.logger.warning(f"AI company selection parsing error: {e}, falling back to first result")
                return companies[0]
                
        except Exception as e:
            self.logger.warning(f"AI company selection failed: {e}, falling back to rule-based")
            # Fallback to simple domain matching
            domain_root = domain.replace('www.', '').split('.')[0].lower()
            for company in companies:
                if domain_root in company.get("name", "").lower():
                    return company
            return companies[0]
    
    async def _search_company_with_retry(
        self, 
        domain: str, 
        country: Optional[str] = None
    ) -> Optional[CompanySearchResult]:
        """Search for company with retry logic"""
        if self.retry_manager:
            return await self.retry_manager.retry_with_backoff(
                self._search_company,
                domain,
                country,
                entity_type='company_search',
                entity_id=domain,
                max_attempts=3
            )
        else:
            return await self._search_company(domain, country)
    
    async def _search_company(
        self, 
        domain: str, 
        country: Optional[str] = None
    ) -> Optional[CompanySearchResult]:
        """Search for company by domain using Cognism API"""
        
        # Normalize domain once for consistent use
        norm = self._clean_domain(domain)

        if not self.api_key:
            self.logger.error("Cognism API key not configured")
            return None
        
        start_time = datetime.utcnow()
        
        params = {"indexSize": 100}
        payload = {
            # TRY WEBSITES INSTEAD OF DOMAINS for better company matching
            "websites": [f"https://{norm}", f"https://www.{norm}", f"http://{norm}", f"http://www.{norm}"],
            "accountSearchOptions": {
                "match_exact_domain": 1,  # Exact domain match
                "match_exact_account_name": 1,  # Also match exact account name as requested
                "filter_domain": "exists",
                "exclude_dataTypes": [
                    "companyHiring", 
                    "locations", 
                    "officePhoneNumbers", 
                    "hqPhoneNumbers", 
                    "technologies"
                ]
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                await self.rate_limiter.acquire()
                self.logger.api_call(
                    service="cognism",
                    method="POST",
                    url=f"{self.base_url}/search/account/search",
                    domain=domain
                )
                
                response = await client.post(
                    f"{self.base_url}/search/account/search",
                    headers=self.headers,
                    params=params,
                    json=payload
                )
                
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                self.logger.api_call(
                    service="cognism",
                    method="POST",
                    url=f"{self.base_url}/search/account/search",
                    status=response.status_code,
                    duration_ms=duration_ms,
                    domain=domain
                )
                
                if response.status_code == 401:
                    self.logger.error("Cognism: Invalid API key")
                    raise Exception("Invalid API key")
                elif response.status_code == 429:
                    self.logger.warning("Cognism: Rate limit exceeded")
                    raise Exception("Rate limit exceeded")
                elif response.status_code != 200:
                    self.logger.error(
                        f"Cognism API error",
                        status_code=response.status_code,
                        response=response.text[:200]
                    )
                    raise Exception(f"API error: {response.status_code}")
                
                data = response.json()
                
                # Extract search results
                results = data.get("results", [])
                if not results:
                    self.logger.warning(f"No results found", domain=domain)
                    return None
                
                # AI-POWERED COMPANY SELECTION: Pick brand-aligned company over holding companies
                company = await self._select_best_company_match(results, domain)
                company_id = company.get("id")
                company_name = company.get("name", "")
                
                if not company_id:
                    self.logger.error(f"No company ID found in search results", domain=domain)
                    return None
                
                self.logger.info(f"Found company in search: {company_name} (ID: {company_id})")
                
                # Now redeem the full company details
                redeemed_data = await self._redeem_company_details(client, [company_id])
                
                if not redeemed_data:
                    self.logger.error(f"Failed to redeem company details for ID: {company_id}")
                    return None
                
                # Use the redeemed data which has full details
                full_company = redeemed_data[0]
                
                # Extract employee count from size fields
                emp_count = None
                if full_company.get("sizeFrom") and full_company.get("sizeTo"):
                    # Use average of range
                    emp_count = (full_company.get("sizeFrom") + full_company.get("sizeTo")) // 2
                elif full_company.get("sizeFrom"):
                    emp_count = full_company.get("sizeFrom")
                
                # Extract headquarters from location array
                hq_data = {"country": "", "city": ""}
                locations = full_company.get("location", [])
                if locations and isinstance(locations, list):
                    for loc in locations:
                        if loc.get("addressType") == "hq" or len(locations) == 1:
                            hq_data = {
                                "country": loc.get("country", ""),
                                "city": loc.get("city", ""),
                                "state": loc.get("state", ""),
                                "street": loc.get("street", ""),
                                "zip": loc.get("zip", "")
                            }
                            break
                
                # Extract industries (it's an array in the response)
                industries = full_company.get("industry", [])
                primary_industry = industries[0] if industries else ""
                
                search_result = CompanySearchResult(
                    id=company_id,
                    name=full_company.get("name", company_name),
                    domain=full_company.get("domain", norm),
                    website=full_company.get("website", f"https://{norm}"),
                    industry=primary_industry,
                    employee_count=str(emp_count) if emp_count else None,
                    revenue=str(full_company.get("revenue", "")) if full_company.get("revenue") else None,
                    headquarters=hq_data,
                    raw_data=full_company
                )
                
                self.logger.debug(
                    f"Successfully redeemed company details",
                    domain=domain,
                    company_name=search_result.name,
                    company_id=search_result.id
                )
                
                return search_result
                
            except httpx.TimeoutException:
                self.logger.error(f"Cognism API timeout", domain=domain)
                raise
            except Exception as e:
                self.logger.error(
                    f"Error searching company",
                    domain=domain,
                    error=e
                )
                raise
    
    async def _redeem_company_details(self, client: httpx.AsyncClient, company_ids: List[str]) -> Optional[List[Dict]]:
        """Redeem full company details using company IDs"""
        try:
            await self.rate_limiter.acquire()
            
            self.logger.info(f"Redeeming company details for IDs: {company_ids}")
            
            redeem_payload = {
                "redeemIds": company_ids
            }
            
            response = await client.post(
                f"{self.base_url}/search/account/redeem",
                headers=self.headers,
                json=redeem_payload
            )
            
            if response.status_code != 200:
                self.logger.error(
                    f"Cognism redeem API error",
                    status_code=response.status_code,
                    response=response.text[:200]
                )
                return None
            
            data = response.json()
            results = data.get("results", [])  # Note: it's "results" not "result"
            
            if not results:
                self.logger.warning(f"No results from redeem API for IDs: {company_ids}")
                return None
            
            self.logger.info(f"Successfully redeemed {len(results)} company details")
            return results
            
        except Exception as e:
            self.logger.error(f"Error redeeming company details: {e}")
            return None
    
    async def _enrich_company_data(
        self, 
        search_result: CompanySearchResult
    ) -> CompanyProfile:
        """Enrich company data with additional information and map to CompanyProfile schema"""

        # Parse headcount (int) from string if possible
        headcount_val = None
        if hasattr(search_result, 'employee_count') and search_result.employee_count:
            try:
                # Handle both string and int values
                emp_str = str(search_result.employee_count).replace(",", "").strip()
                headcount_val = int(emp_str) if emp_str.isdigit() else None
            except (ValueError, AttributeError):
                headcount_val = None

        # Get revenue from raw data (already have full details from redeem)
        revenue_amount = search_result.raw_data.get("revenue")
        revenue_range_val = str(revenue_amount) if revenue_amount else None

        # Build headquarters location from raw data
        hq = search_result.headquarters if search_result.headquarters else None

        # Extract technologies list
        technologies = search_result.raw_data.get("technologies", search_result.raw_data.get("tech", []))
        if not technologies:
            technologies = []

        # Get LinkedIn URL
        linkedin_url = search_result.raw_data.get("linkedinUrl", None)
        social_profiles = {"linkedin": linkedin_url} if linkedin_url else None

        profile = CompanyProfile(
            id=search_result.id,  # Add company ID for parent/subsidiary relationships
            domain=search_result.domain,
            company_name=search_result.name,
            website=search_result.website,
            industry=search_result.industry,
            sub_industry=None,  # Not provided by Cognism
            headcount=headcount_val,
            employee_range=self._get_employee_range(headcount_val) if headcount_val is not None else None,
            revenue_amount=revenue_amount,
            revenue_range=revenue_range_val,
            revenue_currency="USD" if revenue_amount else None,
            founded_year=search_result.raw_data.get("founded"),
            description=search_result.raw_data.get("description", search_result.raw_data.get("shortDescription")),
            company_type=search_result.raw_data.get("type"),
            headquarters_location=hq,
            technologies=technologies,
            social_profiles=social_profiles,
            linkedin_url=linkedin_url,
            source="cognism",
            confidence_score=self._calculate_confidence_score(search_result)
        )

        return profile
    
    def _get_employee_range(self, count: Optional[int]) -> str:
        """Convert employee count to range string"""
        if not count or not isinstance(count, (int, float)):
            return "Unknown"
        
        # Ensure we're working with an integer
        try:
            count = int(count)
        except (ValueError, TypeError):
            return "Unknown"
            
        if count < 10:
            return "1-10"
        elif count < 50:
            return "11-50"
        elif count < 200:
            return "51-200"
        elif count < 500:
            return "201-500"
        elif count < 1000:
            return "501-1000"
        elif count < 5000:
            return "1001-5000"
        elif count < 10000:
            return "5001-10000"
        else:
            return "10000+"
    
    def _get_revenue_range(self, revenue: Optional[float]) -> str:
        """Convert revenue to range string"""
        if not revenue:
            return "Unknown"
        elif revenue < 1:
            return "<$1M"
        elif revenue < 10:
            return "$1M-$10M"
        elif revenue < 50:
            return "$10M-$50M"
        elif revenue < 100:
            return "$50M-$100M"
        elif revenue < 500:
            return "$100M-$500M"
        elif revenue < 1000:
            return "$500M-$1B"
        else:
            return "$1B+"
    
    def _calculate_confidence_score(self, search_result: CompanySearchResult) -> float:
        """Calculate confidence score based on data completeness"""
        score = 0.0
        weights = {
            'name': 0.2,
            'industry': 0.15,
            'employee_count': 0.15,
            'revenue': 0.1,
            'description': 0.1,
            'location': 0.1,
            'linkedin': 0.1,
            'website': 0.1
        }
        
        if search_result.name:
            score += weights['name']
        if search_result.industry:
            score += weights['industry']
        if hasattr(search_result, 'employee_count') and search_result.employee_count:
            score += weights['employee_count']
        if search_result.revenue:
            try:
                # Handle both string and numeric revenue values
                revenue_val = float(str(search_result.revenue).replace(',', '')) if search_result.revenue else 0
                if revenue_val > 0:
                    score += weights['revenue']
            except (ValueError, TypeError):
                # If revenue exists but can't be converted, still give some credit
                score += weights['revenue'] * 0.5
        # CompanySearchResult doesn't have description attribute, check raw_data
        description = search_result.raw_data.get('description', '')
        if description and len(str(description)) > 50:
            score += weights['description']
        # Check for location in raw_data or headquarters
        city = search_result.raw_data.get('city')
        country = search_result.raw_data.get('country')
        if city or country or search_result.headquarters:
            score += weights['location']
        # Check for linkedin in raw_data
        if search_result.raw_data.get('linkedin_url'):
            score += weights['linkedin']
        if search_result.website:
            score += weights['website']
        
        return round(score, 2)
    
    async def _classify_source_type(
        self, 
        company: CompanyProfile, 
        domain: str
    ) -> str:
        """Classify source type using AI analysis of all Cognism data"""
        try:
            # Get client and competitor information
            client_info = await self._get_client_info()
            client_domains = client_info.get('domains', [])
            competitors = await self._get_competitor_info()
            
            # Direct classification for exact domain matches
            if domain in client_domains:
                return "OWNED"
            
            # Check if domain matches any competitor domains exactly
            for comp in competitors:
                if isinstance(comp, dict) and domain in comp.get('domains', []):
                    return "COMPETITOR"
            
            # Prepare all Cognism data for AI analysis
            company_data = {
                "domain": company.domain,
                "company_name": company.company_name,
                "industry": company.industry,
                "sub_industry": company.sub_industry,
                "company_type": company.company_type,
                "description": company.description,
                "headcount": company.headcount,
                "employee_range": company.employee_range,
                "revenue_amount": company.revenue_amount,
                "revenue_range": company.revenue_range,
                "founded_year": company.founded_year,
                "website": company.website,
                "technologies": company.technologies,
                "headquarters_location": company.headquarters_location
            }
            
            # Build AI prompt with all available data
            data_summary = []
            for key, value in company_data.items():
                if value is not None and value != [] and value != "":
                    if isinstance(value, list):
                        data_summary.append(f"- {key.replace('_', ' ').title()}: {', '.join(map(str, value))}")
                    elif isinstance(value, dict):
                        data_summary.append(f"- {key.replace('_', ' ').title()}: {json.dumps(value)}")
                    else:
                        data_summary.append(f"- {key.replace('_', ' ').title()}: {value}")
            
            cognism_data_text = "\n".join(data_summary) if data_summary else "Limited company data available"
            
            # Build competitor context
            competitor_context = []
            for comp in competitors:
                if isinstance(comp, dict):
                    comp_name = comp.get('name', 'Unknown')
                    comp_domains = ', '.join(comp.get('domains', []))
                    competitor_context.append(f"- {comp_name}: {comp_domains}")
            competitor_text = "\n".join(competitor_context) if competitor_context else "No competitors defined"
            
            prompt = f"""Analyze this company data from Cognism and classify the content source type.
            
CLIENT COMPANY CONTEXT:
- Name: {client_info.get('name', 'Unknown')}
- Domains: {', '.join(client_domains)}
- Description: {client_info.get('description', 'Not provided')[:200]}...

KNOWN COMPETITORS:
{competitor_text}

COMPANY DATA BEING ANALYZED:
{cognism_data_text}

CLASSIFICATION OPTIONS:
- OWNED: A digital property owned by the client company (e.g., subsidiary, acquired company, product brand, or strong evidence of ownership relationship)
- COMPETITOR: A digital property of a named competitor or a company that is obviously a subsidiary/brand of a named competitor
- PREMIUM_PUBLISHER: Media companies, news outlets, research firms, analysts
- PROFESSIONAL_BODY: Industry associations, institutes, councils, standards bodies
- EDUCATION: Universities, academic institutions, research organizations
- GOVERNMENT: Government agencies, public sector, regulatory bodies
- NON_PROFIT: Non-profit organizations, foundations, charities
- SOCIAL_MEDIA: Social media platforms, community sites
- OTHER: Companies that don't clearly fit other categories

CLASSIFICATION CRITERIA:
1. First check if there's evidence this company is owned by or related to the client:
   - Look for parent/subsidiary relationships in the description
   - Check for brand mentions or product names that match the client
   - Consider if the company name contains parts of the client name
   - Look for acquisition mentions or ownership indicators

2. Then check if there's evidence this company is owned by or related to any known competitor:
   - Look for parent/subsidiary relationships with competitor names
   - Check if company name contains parts of competitor names
   - Look for brand or product associations with competitors
   - Consider acquisition or merger mentions with competitors

3. If neither OWNED nor COMPETITOR applies, classify based on the company's primary business:
   - Use industry and description as primary indicators
   - Consider company type and business model
   - Choose the MOST SPECIFIC category that applies

Return only the classification without any reasoning or explanation."""

            # Use OpenAI for intelligent classification
            if self.settings.OPENAI_API_KEY:
                import httpx
                
                headers = {
                    'Authorization': f'Bearer {self.settings.OPENAI_API_KEY}',
                    'Content-Type': 'application/json'
                }
                
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are an expert at analyzing company data and classifying content sources for competitive intelligence analysis. Return only the classification category."
                                },
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            "max_tokens": 50,
                            "temperature": 0.1
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("choices") and len(result["choices"]) > 0:
                            classification = result["choices"][0]["message"]["content"].strip()
                            
                            # Validate classification
                            valid_types = ["OWNED", "COMPETITOR", "PREMIUM_PUBLISHER", "PROFESSIONAL_BODY", 
                                         "EDUCATION", "GOVERNMENT", "NON_PROFIT", "SOCIAL_MEDIA", "OTHER"]
                            
                            if classification in valid_types:
                                self.logger.info(f"AI classified {domain} as {classification}")
                                return classification
            
            # Fallback to rule-based classification if AI fails
            return await self._fallback_classification(company, domain, client_info, competitors)
            
        except Exception as e:
            self.logger.error(f"Error in AI source classification for {domain}: {str(e)}")
            return await self._fallback_classification(company, domain, {}, [])
    
    async def _fallback_classification(self, company: CompanyProfile, domain: str, client_info: dict, competitors: list) -> str:
        """Fallback rule-based classification"""
        # Check for name-based ownership relationships
        company_name_lower = company.company_name.lower() if company.company_name else ""
        client_name_lower = client_info.get('name', '').lower()
        
        # Check if company name contains client name (potential subsidiary)
        if client_name_lower and len(client_name_lower) > 3:
            if client_name_lower in company_name_lower:
                self.logger.info(f"Fallback: {domain} classified as OWNED due to name match")
                return "OWNED"
        
        # Check if company name matches any competitor names
        for comp in competitors:
            if isinstance(comp, dict):
                comp_name_lower = comp.get('name', '').lower()
                if comp_name_lower and len(comp_name_lower) > 3:
                    if comp_name_lower in company_name_lower:
                        self.logger.info(f"Fallback: {domain} classified as COMPETITOR due to name match with {comp.get('name')}")
                        return "COMPETITOR"
        
        # Industry-based classification
        if company.industry:
            industry_lower = company.industry.lower()
            if any(pub in industry_lower for pub in ['media', 'publishing', 'news', 'journal']):
                return "PREMIUM_PUBLISHER"
            elif any(edu in industry_lower for edu in ['education', 'university', 'academic']):
                return "EDUCATION"
            elif any(gov in industry_lower for gov in ['government', 'public sector']):
                return "GOVERNMENT"
            elif any(npo in industry_lower for npo in ['non-profit', 'nonprofit', 'charity']):
                return "NON_PROFIT"
        
        # Domain-based classification
        domain_lower = domain.lower()
        if any(media in domain_lower for media in ['news', 'media', 'press', 'journal', 'magazine', 'times', 'post']):
            return "PREMIUM_PUBLISHER"
        elif '.org' in domain_lower or any(org in domain_lower for org in ['association', 'institute', 'foundation', 'society']):
            return "PROFESSIONAL_BODY"
        elif any(edu in domain_lower for edu in ['.edu', 'university', 'college', 'academic']):
            return "EDUCATION"
        elif any(gov in domain_lower for gov in ['.gov', 'government']):
            return "GOVERNMENT"
        
        self.logger.info(f"Fallback classification for {domain}: OTHER")
        return "OTHER"
    
    async def _get_client_info(self) -> Dict[str, Any]:
        """Get client company information including all domains"""
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT company_name, company_domain, additional_domains, description
                    FROM client_config 
                    LIMIT 1
                    """
                )
                if result:
                    domains = [result['company_domain']]
                    if result['additional_domains']:
                        domains.extend(result['additional_domains'])
                    return {
                        'name': result['company_name'],
                        'domains': domains,
                        'description': result['description']
                    }
                return {'name': '', 'domains': [], 'description': ''}
        except Exception as e:
            self.logger.error(f"Error getting client info: {e}")
            return {'name': '', 'domains': [], 'description': ''}
    
    async def _get_competitor_info(self) -> List[Dict[str, Any]]:
        """Get competitor information including names and domains"""
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT competitors FROM client_config LIMIT 1"
                )
                if result:
                    return result if isinstance(result, list) else []
                return []
        except Exception as e:
            self.logger.error(f"Error getting competitor info: {e}")
            return []
    
    async def _store_company_profile(self, profile: CompanyProfile):
        """Store company profile in database (aligned to current schema)."""
        if not self.db:
            return

        try:
            # Build social_profiles JSON from available links
            social_profiles = {}
            if getattr(profile, 'linkedin_url', None):
                social_profiles['linkedin'] = profile.linkedin_url
            if getattr(profile, 'twitter_url', None):
                social_profiles['twitter'] = profile.twitter_url
            if getattr(profile, 'facebook_url', None):
                social_profiles['facebook'] = profile.facebook_url

            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO company_profiles (
                        domain,
                        company_name,
                        industry,
                        sub_industry,
                        description,
                        revenue_amount,
                        revenue_currency,
                        employee_count,
                        founded_year,
                        headquarters_location,
                        technologies,
                        social_profiles,
                        source,
                        source_type
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11, $12, $13, $14
                    )
                    ON CONFLICT (domain) DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        industry = EXCLUDED.industry,
                        sub_industry = EXCLUDED.sub_industry,
                        description = EXCLUDED.description,
                        revenue_amount = EXCLUDED.revenue_amount,
                        revenue_currency = EXCLUDED.revenue_currency,
                        employee_count = EXCLUDED.employee_count,
                        founded_year = EXCLUDED.founded_year,
                        headquarters_location = EXCLUDED.headquarters_location,
                        technologies = EXCLUDED.technologies,
                        social_profiles = EXCLUDED.social_profiles,
                        source = EXCLUDED.source,
                        source_type = EXCLUDED.source_type,
                        updated_at = NOW()
                    """,
                    profile.domain,
                    getattr(profile, 'company_name', None) or getattr(profile, 'name', None),
                    getattr(profile, 'industry', None),
                    getattr(profile, 'sub_industry', None),
                    getattr(profile, 'description', None),
                    getattr(profile, 'revenue_amount', None) or getattr(profile, 'revenue', None),
                    getattr(profile, 'revenue_currency', None) or 'USD',
                    getattr(profile, 'headcount', None),
                    getattr(profile, 'founded_year', None) or getattr(profile, 'year_founded', None),
                    json.dumps(getattr(profile, 'headquarters_location', None)) if getattr(profile, 'headquarters_location', None) else None,
                    json.dumps(getattr(profile, 'technologies', []) or []),
                    json.dumps(social_profiles) if social_profiles else '{}',
                    getattr(profile, 'source', 'cognism'),
                    getattr(profile, 'source_type', 'OTHER')
                )

                self.logger.debug(
                    f"Stored company profile",
                    domain=profile.domain,
                    company_name=(getattr(profile, 'company_name', None) or getattr(profile, 'name', None))
                )
                
                # Also store in company_domains table
                # First get the company_id
                company_id = await conn.fetchval(
                    "SELECT id FROM company_profiles WHERE domain = $1",
                    profile.domain
                )
                
                if company_id:
                    # Check if entry already exists
                    exists = await conn.fetchval(
                        """
                        SELECT EXISTS(
                            SELECT 1 FROM company_domains 
                            WHERE company_id = $1 AND domain = $2
                        )
                        """,
                        company_id, profile.domain
                    )
                    
                    if not exists:
                        await conn.execute(
                            """
                            INSERT INTO company_domains (
                                company_id, domain, domain_type, is_active, is_primary,
                                created_at, updated_at
                            ) VALUES (
                                $1, $2, 'primary', true, true, NOW(), NOW()
                            )
                            """,
                            company_id, profile.domain
                        )
                        
                        self.logger.debug(f"Stored in company_domains table", domain=profile.domain)

        except Exception as e:
            self.logger.error(
                f"Failed to store company profile",
                domain=profile.domain,
                error=e
            )
    
    async def _get_from_cache(self, domain: str) -> Optional[CompanyProfile]:
        """Get company profile from cache"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"company:{domain}"
            cached = await self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return CompanyProfile(**data)
        except Exception as e:
            self.logger.warning(f"Cache read failed", domain=domain, error=e)
        
        return None
    
    async def _cache_result(self, domain: str, profile: CompanyProfile):
        """Cache company profile"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"company:{domain}"
            data = profile.dict()
            # Convert datetime to string for JSON serialization
            data['enriched_at'] = data['enriched_at'].isoformat()
            
            await self.redis_client.setex(
                cache_key,
                86400,  # 24 hour TTL
                json.dumps(data)
            )
            
            self.logger.debug(f"Cached company profile", domain=domain)
            
        except Exception as e:
            self.logger.warning(f"Cache write failed", domain=domain, error=e)
    
    @log_performance("company_enricher", "batch_enrich")
    async def batch_enrich(
        self,
        domains: List[str],
        concurrency_limit: int = 5,
        progress_callback=None
    ) -> BatchEnrichmentResult:
        """Batch enrich multiple domains with concurrency control"""
        
        self.logger.info(
            f"Starting batch enrichment",
            total_domains=len(domains),
            concurrency_limit=concurrency_limit
        )
        
        results = []
        errors = []
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        async def enrich_with_limit(domain: str, index: int):
            async with semaphore:
                try:
                    profile = await self.enrich_domain(domain)
                    if profile:
                        results.append(profile)
                    else:
                        errors.append({
                            'domain': domain,
                            'error': 'No company found'
                        })
                    
                    if progress_callback:
                        await progress_callback(index + 1, len(domains))
                        
                except Exception as e:
                    self.logger.error(
                        f"Batch enrichment error",
                        domain=domain,
                        error=e
                    )
                    errors.append({
                        'domain': domain,
                        'error': str(e)
                    })
        
        # Process all domains concurrently
        tasks = [
            enrich_with_limit(domain, i)
            for i, domain in enumerate(domains)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        batch_result = BatchEnrichmentResult(
            total_domains=len(domains),
            successful=len(results),
            failed=len(errors),
            profiles=results,
            errors=errors,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        
        self.logger.info(
            f"Batch enrichment completed",
            total=batch_result.total_domains,
            successful=batch_result.successful,
            failed=batch_result.failed
        )
        
        return batch_result
    
    async def detect_parent_company(self, company_profile: CompanyProfile, domain: str) -> Optional[Dict[str, Any]]:
        """
        Use OpenAI LLM to detect if this is a subsidiary and identify the parent company
        Returns parent company information if detected
        """
        if not self.settings.OPENAI_API_KEY:
            self.logger.debug("OpenAI API key not configured for parent company detection")
            return None
            
        try:
            self.logger.debug(
                f"Detecting parent company for {company_profile.company_name}",
                domain=domain,
                company_name=company_profile.company_name
            )
            
            # Build context for AI analysis
            company_context = f"""
Company Information:
- Name: {company_profile.company_name}
- Domain: {domain}
- Industry: {company_profile.industry or 'Unknown'}
- Employees: {company_profile.headcount or 'Unknown'}
- Revenue: {getattr(company_profile, 'revenue', 'Unknown')} {getattr(company_profile, 'revenue_currency', '')}
- Description: {getattr(company_profile, 'description', 'No description available')}
"""
            
            prompt = f"""
Analyze the following company and determine if it's a subsidiary, brand, or division of a larger parent company.

{company_context}

Guidelines:
- If this appears to be a subsidiary, brand, or division of a larger parent company, identify the parent
- Consider company naming patterns (e.g., "Alliance-IBM" suggests IBM as parent, "MTGoracle LLC" suggests Oracle)
- Look for industry context and typical corporate structures
- Be conservative - only suggest relationships with high confidence
- Common patterns: "CompanyName LLC" may be subsidiary of "CompanyName Inc.", regional offices, specialized divisions

Return JSON with:
{{
    "is_subsidiary": boolean,
    "parent_company_name": "string or null",
    "parent_domain": "string or null", 
    "relationship_type": "subsidiary|brand|division|partnership|none",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

If not a subsidiary, return is_subsidiary: false.
"""
            
            # Use the same model pattern as video enricher
            from openai import OpenAI
            client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
            
            # Run blocking OpenAI call off the event loop with timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: client.chat.completions.create(
                        model="gpt-4o-mini",  # Using fast, cheap model as requested
                        messages=[
                            {"role": "system", "content": "You are an expert at identifying corporate relationships and parent/subsidiary structures. Always return valid JSON as requested."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=500,
                        temperature=0.1
                    )
                ),
                timeout=30
            )
            
            # Parse response 
            content = response.choices[0].message.content.strip()
            
            try:
                # Handle markdown code fences around JSON
                if content.startswith('```json'):
                    start_idx = content.find('{')
                    end_idx = content.rfind('}')
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        content = content[start_idx:end_idx+1]
                elif content.startswith('```'):
                    # Handle other code fence variations
                    start_idx = content.find('{')
                    end_idx = content.rfind('}')
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        content = content[start_idx:end_idx+1]
                
                result = json.loads(content)
                
                self.logger.debug(
                    f"Parent company analysis complete",
                    domain=domain,
                    company_name=company_profile.company_name,
                    is_subsidiary=result.get('is_subsidiary', False),
                    parent_name=result.get('parent_company_name'),
                    confidence=result.get('confidence', 0.0)
                )
                
                return result
                
            except json.JSONDecodeError as e:
                # Try to salvage JSON if malformed
                self.logger.warning(f"Malformed JSON from parent detection: {content[:200]}...")
                return None
                
        except asyncio.TimeoutError:
            self.logger.warning(f"Parent company detection timeout for {domain}")
            return None
        except Exception as e:
            self.logger.error(f"Parent company detection error for {domain}: {e}")
            return None
    
    async def store_company_relationship(
        self, 
        parent_info: Dict[str, Any], 
        subsidiary_profile: CompanyProfile,
        subsidiary_domain: str
    ) -> bool:
        """Store parent/subsidiary relationship in database"""
        try:
            # Generate IDs for parent company if needed
            parent_company_id = str(uuid4())
            subsidiary_company_id = subsidiary_profile.id or str(uuid4())
            
            async with self.db.acquire() as conn:
                # Check if relationship already exists
                existing = await conn.fetchrow(
                    """
                    SELECT id FROM company_relationships 
                    WHERE subsidiary_domain = $1 AND parent_company_name = $2
                    """,
                    subsidiary_domain, 
                    parent_info['parent_company_name']
                )
                
                if existing:
                    self.logger.debug(f"Relationship already exists for {subsidiary_domain}")
                    return True
                
                # Store the relationship
                await conn.execute(
                    """
                    INSERT INTO company_relationships (
                        parent_company_id, parent_company_name, parent_domain,
                        subsidiary_company_id, subsidiary_company_name, subsidiary_domain,
                        relationship_type, confidence_score, source
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    parent_company_id,
                    parent_info['parent_company_name'],
                    parent_info['parent_domain'] or '',
                    subsidiary_company_id,
                    subsidiary_profile.company_name,
                    subsidiary_domain,
                    parent_info.get('relationship_type', 'subsidiary'),
                    parent_info.get('confidence', 0.0),
                    'ai_detection'
                )
                
                self.logger.info(
                    f"Stored company relationship",
                    subsidiary=subsidiary_profile.company_name,
                    subsidiary_domain=subsidiary_domain,
                    parent=parent_info['parent_company_name'],
                    relationship_type=parent_info.get('relationship_type', 'subsidiary'),
                    confidence=parent_info.get('confidence', 0.0)
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error storing company relationship: {e}")
            return False
    
    async def enrich_with_parent_detection(self, domain: str) -> Optional[CompanyProfile]:
        """
        Enhanced enrichment that includes parent company detection and relationship storage
        """
        # First, do standard enrichment
        profile = await self.enrich_domain(domain)
        if not profile:
            return None
        
        # Then detect parent company
        parent_info = await self.detect_parent_company(profile, domain)
        if parent_info and parent_info.get('is_subsidiary', False):
            # Store the relationship
            await self.store_company_relationship(parent_info, profile, domain)
            
            # Add parent info to profile metadata for convenience
            if hasattr(profile, 'metadata'):
                if not profile.metadata:
                    profile.metadata = {}
                profile.metadata['parent_company'] = parent_info
        
        return profile
