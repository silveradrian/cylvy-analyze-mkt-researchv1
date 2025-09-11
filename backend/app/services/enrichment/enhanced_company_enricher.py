"""
Enhanced Company Enrichment Service with Robustness Features
Includes circuit breaker, retry logic, and detailed logging
"""

import httpx
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import json
import re
import asyncio
from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool
from app.models.company import (
    CompanyProfile, CompanySearchResult, CompanyEnrichmentResult,
    BatchEnrichmentResult
)
from app.core.robustness_logging import get_logger, log_performance


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
    
    @log_performance("company_enricher", "enrich_domain")
    async def enrich_domain(
        self, 
        domain: str, 
        country: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[CompanyProfile]:
        """Enrich company data from domain with robustness"""
        
        # Clean domain
        domain = self._clean_domain(domain)
        
        self.logger.debug(
            f"Starting domain enrichment",
            domain=domain,
            country=country,
            force_refresh=force_refresh
        )
        
        # Check cache first if not forcing refresh
        if not force_refresh:
            cached = await self._get_from_cache(domain)
            if cached:
                self.logger.info(f"Cache hit for domain", domain=domain)
                return cached
        
        # Use circuit breaker if available
        if self.circuit_breaker:
            try:
                company_data = await self.circuit_breaker.call(
                    self._search_company_with_retry,
                    domain,
                    country,
                    fallback=lambda *args: None
                )
            except Exception as e:
                self.logger.error(
                    "Company search failed with circuit breaker",
                    domain=domain,
                    error=e
                )
                return None
        else:
            company_data = await self._search_company_with_retry(domain, country)
        
        if company_data:
            # Enrich with additional data
            enriched = await self._enrich_company_data(company_data)
            
            # Classify source type
            source_type = await self._classify_source_type(enriched, domain)
            enriched.source_type = source_type
            
            # Store in database
            await self._store_company_profile(enriched)
            
            # Cache result
            await self._cache_result(domain, enriched)
            
            self.logger.info(
                f"Successfully enriched domain",
                domain=domain,
                company_name=enriched.name,
                employees=enriched.employee_count
            )
            
            return enriched
        
        self.logger.warning(f"No company found for domain", domain=domain)
        return None
    
    def _clean_domain(self, domain: str) -> str:
        """Clean and normalize domain"""
        domain = domain.replace('http://', '').replace('https://', '')
        domain = domain.replace('www.', '')
        domain = domain.split('/')[0]
        return domain.lower()
    
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
        
        if not self.api_key:
            self.logger.error("Cognism API key not configured")
            return None
        
        start_time = datetime.utcnow()
        
        params = {"indexSize": 100}
        payload = {
            "domains": [domain],
            "accountSearchOptions": {
                "match_exact_domain": 1,  # Boolean - exact domain match
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
                
                # Get the first result (best match)
                company = results[0]
                
                # Create CompanySearchResult
                search_result = CompanySearchResult(
                    company_id=str(company.get("companyId", "")),
                    name=company.get("companyName", ""),
                    domain=domain,
                    website=company.get("companyUrl", f"https://{domain}"),
                    industry=company.get("primaryIndustry", ""),
                    employee_count=company.get("employeeCount", 0),
                    revenue=company.get("revenue", 0),
                    country=company.get("country", ""),
                    city=company.get("city", ""),
                    description=company.get("description", ""),
                    linkedin_url=company.get("linkedinUrl", ""),
                    raw_data=company
                )
                
                self.logger.debug(
                    f"Found company",
                    domain=domain,
                    company_name=search_result.name,
                    company_id=search_result.company_id
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
    
    async def _enrich_company_data(
        self, 
        search_result: CompanySearchResult
    ) -> CompanyProfile:
        """Enrich company data with additional information"""
        
        # Map search result to company profile
        profile = CompanyProfile(
            domain=search_result.domain,
            name=search_result.name,
            website=search_result.website,
            industry=search_result.industry,
            sub_industry=search_result.raw_data.get("subIndustry", ""),
            employee_count=search_result.employee_count,
            employee_range=self._get_employee_range(search_result.employee_count),
            revenue=search_result.revenue,
            revenue_range=self._get_revenue_range(search_result.revenue),
            year_founded=search_result.raw_data.get("yearFounded"),
            description=search_result.description,
            headquarters_location=f"{search_result.city}, {search_result.country}".strip(", "),
            countries=[search_result.country] if search_result.country else [],
            linkedin_url=search_result.linkedin_url,
            twitter_url=search_result.raw_data.get("twitterUrl", ""),
            facebook_url=search_result.raw_data.get("facebookUrl", ""),
            technologies=search_result.raw_data.get("technologies", []),
            keywords=search_result.raw_data.get("keywords", []),
            enriched_at=datetime.utcnow(),
            data_source="cognism",
            confidence_score=self._calculate_confidence_score(search_result)
        )
        
        return profile
    
    def _get_employee_range(self, count: Optional[int]) -> str:
        """Convert employee count to range string"""
        if not count:
            return "Unknown"
        elif count < 10:
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
        if search_result.employee_count and search_result.employee_count > 0:
            score += weights['employee_count']
        if search_result.revenue and search_result.revenue > 0:
            score += weights['revenue']
        if search_result.description and len(search_result.description) > 50:
            score += weights['description']
        if search_result.city or search_result.country:
            score += weights['location']
        if search_result.linkedin_url:
            score += weights['linkedin']
        if search_result.website:
            score += weights['website']
        
        return round(score, 2)
    
    async def _classify_source_type(
        self, 
        company: CompanyProfile, 
        domain: str
    ) -> str:
        """Classify the source type based on company and domain info"""
        
        # Check for news/media indicators
        media_keywords = ['news', 'media', 'press', 'journal', 'magazine', 'times', 'post']
        domain_lower = domain.lower()
        industry_lower = (company.industry or '').lower()
        
        for keyword in media_keywords:
            if keyword in domain_lower or keyword in industry_lower:
                return 'media'
        
        # Check for association/org indicators
        org_indicators = ['.org', 'association', 'institute', 'foundation', 'society']
        for indicator in org_indicators:
            if indicator in domain_lower or indicator in company.name.lower():
                return 'association'
        
        # Check for analyst/research firms
        analyst_keywords = ['gartner', 'forrester', 'idc', 'research', 'analyst']
        for keyword in analyst_keywords:
            if keyword in domain_lower or keyword in company.name.lower():
                return 'analyst'
        
        # Check for vendor/competitor
        if company.industry and 'technology' in industry_lower:
            return 'vendor'
        
        # Check for influencer (smaller companies with high social presence)
        if company.employee_count and company.employee_count < 50 and company.linkedin_url:
            return 'influencer'
        
        # Default to vendor
        return 'vendor'
    
    async def _store_company_profile(self, profile: CompanyProfile):
        """Store company profile in database"""
        if not self.db:
            return
        
        try:
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO company_profiles (
                        domain, name, website, industry, sub_industry,
                        employee_count, employee_range, revenue, revenue_range,
                        year_founded, description, headquarters_location,
                        countries, linkedin_url, twitter_url, facebook_url,
                        technologies, keywords, source_type, enriched_at,
                        data_source, confidence_score
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                        $21, $22
                    )
                    ON CONFLICT (domain) DO UPDATE SET
                        name = EXCLUDED.name,
                        website = EXCLUDED.website,
                        industry = EXCLUDED.industry,
                        sub_industry = EXCLUDED.sub_industry,
                        employee_count = EXCLUDED.employee_count,
                        employee_range = EXCLUDED.employee_range,
                        revenue = EXCLUDED.revenue,
                        revenue_range = EXCLUDED.revenue_range,
                        year_founded = EXCLUDED.year_founded,
                        description = EXCLUDED.description,
                        headquarters_location = EXCLUDED.headquarters_location,
                        countries = EXCLUDED.countries,
                        linkedin_url = EXCLUDED.linkedin_url,
                        twitter_url = EXCLUDED.twitter_url,
                        facebook_url = EXCLUDED.facebook_url,
                        technologies = EXCLUDED.technologies,
                        keywords = EXCLUDED.keywords,
                        source_type = EXCLUDED.source_type,
                        enriched_at = EXCLUDED.enriched_at,
                        data_source = EXCLUDED.data_source,
                        confidence_score = EXCLUDED.confidence_score,
                        updated_at = NOW()
                    """,
                    profile.domain,
                    profile.name,
                    profile.website,
                    profile.industry,
                    profile.sub_industry,
                    profile.employee_count,
                    profile.employee_range,
                    profile.revenue,
                    profile.revenue_range,
                    profile.year_founded,
                    profile.description,
                    profile.headquarters_location,
                    profile.countries,
                    profile.linkedin_url,
                    profile.twitter_url,
                    profile.facebook_url,
                    profile.technologies,
                    profile.keywords,
                    profile.source_type,
                    profile.enriched_at,
                    profile.data_source,
                    profile.confidence_score
                )
                
                self.logger.debug(
                    f"Stored company profile",
                    domain=profile.domain,
                    company_name=profile.name
                )
                
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
