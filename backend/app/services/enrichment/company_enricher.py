"""Company enrichment service using Cognism API"""
import httpx
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import json
import re
import asyncio
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.core.database import DatabasePool
from app.models.company import (
    CompanyProfile, CompanySearchResult, CompanyEnrichmentResult,
    BatchEnrichmentResult
)


class CompanyEnricher:
    """Service for enriching company data using Cognism API"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        self.api_key = settings.COGNISM_API_KEY
        
        # Workaround for API key parsing issue
        if self.api_key and self.api_key.startswith("PI-P-"):
            # Fix the known parsing issue where "API-P" becomes "PI-P"
            self.api_key = "A" + self.api_key
            logger.warning("Applied workaround for API key parsing issue")
        
        self.base_url = "https://app.cognism.com/api"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.redis_client = None  # Will be set if available
        
        # Note: The Cognism API endpoint structure may vary based on your subscription
        # Please refer to your Cognism API documentation for the correct endpoints
        # Common endpoints include:
        # - https://api.cognism.com/api/v1
        # - https://app.cognism.com/api/public/v2
        # - https://api.cognism.com/v2
    
    async def enrich_domain(
        self, 
        domain: str, 
        country: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[CompanyProfile]:
        """Enrich company data from domain"""
        
        # Clean domain
        domain = self._clean_domain(domain)
        
        # Check cache first if not forcing refresh
        if not force_refresh:
            cached = await self._get_from_cache(domain)
            if cached:
                logger.info(f"Cache hit for domain: {domain}")
                return cached
        
        # Search for company
        logger.info(f"Searching for company: {domain}")
        company_data = await self._search_company(domain, country)
        
        if company_data:
            # Enrich with additional data
            enriched = await self._enrich_company_data(company_data)
            
            # Classify source type based on company data
            source_type = await self._classify_source_type(enriched, domain)
            enriched.source_type = source_type
            
            # Cache result
            await self._cache_result(domain, enriched)
            
            return enriched
        
        logger.warning(f"No company found for domain: {domain}")
        return None
    
    def _clean_domain(self, domain: str) -> str:
        """Clean and normalize domain"""
        # Remove protocol
        domain = domain.replace('http://', '').replace('https://', '')
        # Remove path
        domain = domain.split('/')[0]
        # Remove port if any
        domain = domain.split(':')[0]
        # Convert to lowercase
        domain = domain.lower()
        
        # Extract primary domain (remove all subdomains)
        parts = domain.split('.')
        
        # Handle special cases like co.uk, com.au, etc.
        if len(parts) >= 3:
            # Check if it's a known multi-part TLD
            if len(parts) >= 3 and parts[-2] in ['co', 'com', 'net', 'org', 'gov', 'edu', 'ac']:
                # Keep last 3 parts (e.g., example.co.uk)
                primary_domain = '.'.join(parts[-3:])
            else:
                # Keep last 2 parts (e.g., example.com)
                primary_domain = '.'.join(parts[-2:])
        elif len(parts) == 2:
            primary_domain = domain
        else:
            # Single part domain (shouldn't happen for valid domains)
            primary_domain = domain
        
        logger.debug(f"Cleaned domain: {domain} -> {primary_domain}")
        return primary_domain
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def _search_company(self, domain: str, country: Optional[str] = None) -> Optional[CompanySearchResult]:
        """Search for company by domain using Cognism API"""
        
        if not self.api_key:
            logger.error("Cognism API key not configured")
            return None
            
        params = {"indexSize": 100}
        payload = {
            "domains": [domain],
            "accountSearchOptions": {
                "match_exact_domain": 1,  # Boolean - exact domain match
                "filter_domain": "exists",
                "exclude_dataTypes": ["companyHiring", "locations", "officePhoneNumbers", "hqPhoneNumbers", "technologies"]
            }
        }
        
        # Country filter is not supported in this endpoint structure
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/search/account/search",
                    headers=self.headers,
                    params=params,
                    json=payload
                )
                
                if response.status_code == 401:
                    logger.error("Cognism: Invalid API key")
                    return None
                elif response.status_code == 429:
                    logger.warning("Cognism: Rate limit exceeded, waiting before retry")
                    # Wait longer when rate limited
                    await asyncio.sleep(60)  # Wait 60 seconds before allowing retry
                    raise Exception("Rate limit exceeded - waiting 60s before retry")
                elif response.status_code != 200:
                    logger.error(f"Cognism API error: {response.status_code} - {response.text}")
                    return None
                
                data = response.json()
                logger.info(f"Cognism API response for {domain}: {json.dumps(data, indent=2)[:500]}...")
                
                # Extract search results - API returns 'results' not 'result'
                results = data.get("results", [])
                if not results:
                    logger.warning(f"No results found for domain: {domain}")
                    return None
                
                # Get the first result (best match)
                company_id = results[0].get("id")
                if not company_id:
                    return None
                
                # Fetch detailed company information
                return await self._get_company_details(company_id)
                
            except httpx.TimeoutException:
                logger.error(f"Cognism API timeout for domain: {domain}")
                return None
            except Exception as e:
                logger.error(f"Error searching company {domain}: {e}")
                raise
    
    async def _get_company_details(self, company_id: str) -> Optional[CompanySearchResult]:
        """Get detailed company information by ID"""
        
        params = {"mergePhonesAndLocations": "true"}
        payload = {
            "redeemIds": [company_id],
            "selectedFields": [
                "headcount", "location", "type", "domain", "industry", "revenue",
                "linkedinUrl", "website", "founded", "lastConfirmed", "naics",
                "sic", "shortDescription", "description"
            ]
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/search/account/redeem",
                    headers=self.headers,
                    params=params,
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to get company details: {response.status_code} - {response.text}")
                    return None
                
                data = response.json()
                results = data.get("results", [])  # Changed from "result" to "results"
                
                if results and len(results) > 0:
                    company = results[0]
                    return self._parse_company_result(company)
                
                return None
                
            except Exception as e:
                logger.error(f"Error getting company details: {e}")
                return None
    
    def _select_best_match(self, target_domain: str, companies: List[Dict]) -> Optional[CompanySearchResult]:
        """Select the best matching company from multiple results"""
        
        if not companies:
            return None
            
        if len(companies) == 1:
            return self._parse_company_result(companies[0])
        
        # Score each company
        scored_companies = []
        for company in companies:
            score = self._calculate_match_score(target_domain, company)
            parsed = self._parse_company_result(company)
            parsed.score = score
            scored_companies.append(parsed)
        
        # Sort by score (highest first)
        scored_companies.sort(key=lambda x: x.score, reverse=True)
        
        # Return best match if score is reasonable
        best_match = scored_companies[0]
        if best_match.score >= 0.6:  # Minimum 60% match score
            return best_match
        
        return None
    
    def _parse_company_result(self, company: Dict) -> CompanySearchResult:
        """Parse raw company data into CompanySearchResult"""
        return CompanySearchResult(
            id=str(company.get("id", "")),
            name=company.get("name", ""),
            domain=company.get("domain", ""),
            website=company.get("website"),
            industry=company.get("industry") if isinstance(company.get("industry"), str) else (company.get("industry", [None])[0] if company.get("industry") else None),
            revenue=str(company.get("revenue", "")) if company.get("revenue") else None,
            employee_count=str(company.get("headcount", "")) if company.get("headcount") else None,
            headquarters=company.get("location"),
            raw_data=company
        )
    
    def _calculate_match_score(self, target_domain: str, company: Dict) -> float:
        """Calculate match score for a company"""
        score = 0.0
        
        # Domain match (highest weight)
        company_domain = company.get("domain", "").lower()
        if company_domain == target_domain:
            score += 1.0
        elif target_domain in company_domain:
            score += 0.8
        elif company_domain in target_domain:
            score += 0.6
        
        # Data completeness
        important_fields = [
            'name', 'domain', 'industry', 'description',
            'employeeCount', 'revenue', 'headquarters', 'foundedYear'
        ]
        
        filled_fields = sum(1 for field in important_fields if company.get(field))
        score += (filled_fields / len(important_fields)) * 0.5
        
        # Company size (tiebreaker)
        revenue = self._parse_revenue(company.get('revenue'))
        if revenue:
            if revenue > 1_000_000_000:  # $1B+
                score += 0.2
            elif revenue > 100_000_000:  # $100M+
                score += 0.1
        
        return score
    
    async def _enrich_company_data(self, company: CompanySearchResult) -> CompanyProfile:
        """Enrich company data with additional information"""
        
        # Parse and clean data from Cognism v2 API format
        raw_data = company.raw_data
        
        # Parse industry - can be array or string
        # Parse industry - disabled due to inaccuracy
        # industry = raw_data.get("industry")
        # if isinstance(industry, list) and industry:
        #     industry_str = industry[0]
        # elif isinstance(industry, str):
        #     industry_str = industry
        # else:
        #     industry_str = None
        
        enriched = CompanyProfile(
            domain=company.domain,
            company_name=company.name,
            website=company.website or raw_data.get("website"),
            industry=None,  # Disabled - Cognism industry data unreliable
            sub_industry=None,  # Not provided by Cognism
            sic_code=raw_data.get("sic", [None])[0] if raw_data.get("sic") else None,
            naics_code=raw_data.get("naics", [None])[0] if raw_data.get("naics") else None,
            revenue_amount=self._parse_revenue(raw_data.get("revenue")),
            revenue_range=None,  # Not provided in this format
            revenue_currency="USD",
            headcount=self._parse_headcount(raw_data.get("headcount")),
            employee_range=None,  # Not provided in this format
            founded_year=self._parse_year(raw_data.get("founded")),
            description=raw_data.get("description") or raw_data.get("shortDescription"),
            company_type=raw_data.get("type"),
            phone=None,  # Not included in selected fields
            last_confirmed=str(raw_data.get("lastConfirmed")) if raw_data.get("lastConfirmed") else None,
            technologies=[],  # Excluded from API request
            headquarters_location=self._parse_headquarters(raw_data.get("location")),
            social_profiles={"linkedin": raw_data.get("linkedinUrl")} if raw_data.get("linkedinUrl") else None,
            linkedin_url=raw_data.get("linkedinUrl"),
            source="cognism",
            confidence_score=self._calculate_confidence_score(raw_data)
        )
        
        return enriched
    
    def _parse_revenue(self, revenue_str: Any) -> Optional[float]:
        """Parse revenue string to float"""
        if not revenue_str:
            return None
            
        if isinstance(revenue_str, (int, float)):
            return float(revenue_str)
            
        if not isinstance(revenue_str, str):
            return None
        
        # Remove currency symbols and spaces
        revenue_str = revenue_str.replace('$', '').replace(',', '').strip()
        
        # Handle formats like "1B", "100M", "10K"
        match = re.match(r'^([\d.]+)\s*([BMK]?)$', revenue_str, re.IGNORECASE)
        if not match:
            try:
                return float(revenue_str)
            except:
                return None
        
        value = float(match.group(1))
        unit = match.group(2).upper()
        
        multipliers = {
            'B': 1_000_000_000,
            'M': 1_000_000,
            'K': 1_000
        }
        
        return value * multipliers.get(unit, 1)
    
    def _parse_headcount(self, headcount_str: Any) -> Optional[int]:
        """Parse employee count string to integer"""
        if not headcount_str:
            return None
            
        if isinstance(headcount_str, (int, float)):
            return int(headcount_str)
            
        if not isinstance(headcount_str, str):
            return None
        
        # Extract first number from strings like "100-500", "1000+"
        numbers = re.findall(r'\d+', headcount_str)
        if numbers:
            return int(numbers[0])
        
        return None
    
    def _parse_year(self, year_str: Any) -> Optional[int]:
        """Parse year string to integer"""
        if not year_str:
            return None
            
        if isinstance(year_str, (int, float)):
            return int(year_str)
            
        if not isinstance(year_str, str):
            return None
        
        # Extract 4-digit year
        match = re.search(r'\d{4}', year_str)
        if match:
            return int(match.group())
        
        return None
    
    def _parse_headquarters(self, hq_data: Any) -> Optional[Dict[str, str]]:
        """Parse headquarters location data"""
        if not hq_data:
            return None
            
        if isinstance(hq_data, str):
            return {"location": hq_data}
            
        if isinstance(hq_data, dict):
            location = {}
            if hq_data.get("city"):
                location["city"] = hq_data["city"]
            if hq_data.get("state"):
                location["state"] = hq_data["state"]
            if hq_data.get("country"):
                location["country"] = hq_data["country"]
            if hq_data.get("postalCode"):
                location["postal_code"] = hq_data["postalCode"]
            return location if location else None
        
        return None
    
    def _parse_social_profiles(self, social_data: Any) -> Optional[Dict[str, str]]:
        """Parse social media profiles"""
        if not social_data:
            return None
            
        if isinstance(social_data, dict):
            return social_data
            
        if isinstance(social_data, list):
            profiles = {}
            for profile in social_data:
                if isinstance(profile, dict) and profile.get("type") and profile.get("url"):
                    profiles[profile["type"]] = profile["url"]
            return profiles if profiles else None
        
        return None
    
    def _calculate_confidence_score(self, company_data: Dict) -> float:
        """Calculate confidence score based on data completeness"""
        important_fields = [
            'name', 'domain', 'industry', 'description',
            'employeeCount', 'revenue', 'headquarters', 'foundedYear',
            'website', 'phone', 'lastConfirmed'
        ]
        
        filled_count = sum(1 for field in important_fields if company_data.get(field))
        base_score = filled_count / len(important_fields)
        
        # Boost score if data is recent
        if company_data.get("lastConfirmed"):
            try:
                last_confirmed = datetime.fromisoformat(
                    company_data["lastConfirmed"].replace("Z", "+00:00")
                )
                days_old = (datetime.utcnow() - last_confirmed.replace(tzinfo=None)).days
                if days_old < 180:  # Less than 6 months old
                    base_score = min(1.0, base_score * 1.1)
            except:
                pass
        
        return round(base_score, 2)
    
    async def _classify_source_type(self, company_profile: CompanyProfile, domain: str) -> str:
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
                "domain": company_profile.domain,
                "company_name": company_profile.company_name,
                "industry": company_profile.industry,
                "sub_industry": company_profile.sub_industry,
                "company_type": company_profile.company_type,
                "description": company_profile.description,
                "headcount": company_profile.headcount,
                "employee_range": company_profile.employee_range,
                "revenue_amount": company_profile.revenue_amount,
                "revenue_range": company_profile.revenue_range,
                "founded_year": company_profile.founded_year,
                "website": company_profile.website,
                "technologies": company_profile.technologies,
                "headquarters_location": company_profile.headquarters_location
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
                
                function_schema = {
                    "name": "classify_company_source",
                    "description": "Classify company source type based on Cognism data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_type": {
                                "type": "string",
                                "enum": ["OWNED", "COMPETITOR", "PREMIUM_PUBLISHER", "PROFESSIONAL_BODY", 
                                        "EDUCATION", "GOVERNMENT", "NON_PROFIT", "SOCIAL_MEDIA", "OTHER"]
                            }
                        },
                        "required": ["source_type"]
                    }
                }
                
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/responses",
                        headers=headers,
                        json={
                            "model": "gpt-4.1",
                            "input": [
                                {
                                    "role": "system",
                                    "content": "You are an expert at analyzing company data and classifying content sources for competitive intelligence analysis."
                                },
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            "tools": [
                                {
                                    "type": "function",
                                    "name": "classify_company_source",
                                    "description": "Classify company source type based on Cognism data",
                                    "parameters": function_schema["parameters"]
                                }
                            ]
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        # Extract result from the new API format
                        if result.get("choices") and len(result["choices"]) > 0:
                            choice = result["choices"][0]
                            if choice.get("message") and choice["message"].get("tool_calls"):
                                tool_call = choice["message"]["tool_calls"][0]
                                if tool_call.get("function") and tool_call["function"].get("arguments"):
                                    classification = json.loads(tool_call["function"]["arguments"])
                                    source_type = classification.get('source_type', 'OTHER')
                                    
                                    # Simple logging without reasoning
                                    logger.info(f"AI classified {domain} as {source_type}")
                                    
                                    return source_type
            
            # Fallback to simple rule-based classification if AI fails
            # Check for name-based ownership relationships
            company_name_lower = company_profile.company_name.lower() if company_profile.company_name else ""
            client_name_lower = client_info.get('name', '').lower()
            
            # Check if company name contains client name (potential subsidiary)
            if client_name_lower and len(client_name_lower) > 3:  # Avoid false positives with short names
                if client_name_lower in company_name_lower:
                    logger.info(f"Fallback: {domain} classified as OWNED due to name match")
                    return "OWNED"
            
            # Check if company name matches any competitor names
            for comp in competitors:
                if isinstance(comp, dict):
                    comp_name_lower = comp.get('name', '').lower()
                    if comp_name_lower and len(comp_name_lower) > 3:
                        if comp_name_lower in company_name_lower:
                            logger.info(f"Fallback: {domain} classified as COMPETITOR due to name match with {comp.get('name')}")
                            return "COMPETITOR"
            
            # Industry-based classification
            if company_profile.industry:
                industry_lower = company_profile.industry.lower()
                if any(pub in industry_lower for pub in ['media', 'publishing', 'news', 'journal']):
                    return "PREMIUM_PUBLISHER"
                elif any(edu in industry_lower for edu in ['education', 'university', 'academic']):
                    return "EDUCATION"
                elif any(gov in industry_lower for gov in ['government', 'public sector']):
                    return "GOVERNMENT"
                elif any(npo in industry_lower for npo in ['non-profit', 'nonprofit', 'charity']):
                    return "NON_PROFIT"
            
            logger.info(f"Fallback classification for {domain}: OTHER")
            return "OTHER"
            
        except Exception as e:
            logger.error(f"Error in AI source classification for {domain}: {str(e)}")
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
            logger.error(f"Error getting client info: {e}")
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
            logger.error(f"Error getting competitor info: {e}")
            return []
    
    async def _get_client_domains(self) -> List[str]:
        """Get all client domains (for backward compatibility)"""
        client_info = await self._get_client_info()
        return client_info.get('domains', [])
    
    async def _get_competitor_domains(self) -> List[str]:
        """Get all competitor domains (for backward compatibility)"""
        competitors = await self._get_competitor_info()
        domains = []
        for comp in competitors:
            if isinstance(comp, dict) and 'domains' in comp:
                domains.extend(comp.get('domains', []))
        return domains
    
    async def _get_from_cache(self, domain: str) -> Optional[CompanyProfile]:
        """Get company data from cache"""
        if self.redis_client:
            try:
                cache_key = f"company:{domain}"
                cached = await self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    return CompanyProfile(**data)
            except Exception as e:
                logger.error(f"Cache error: {e}")
        
        # Also check database cache
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT profile_data
                    FROM company_profiles_cache
                    WHERE domain = $1
                    AND expires_at > NOW()
                    """,
                    domain
                )
                if result:
                    # Parse JSON data from the database
                    profile_data = json.loads(result['profile_data'])
                    return CompanyProfile(**profile_data)
        except Exception as e:
            logger.error(f"Database cache error: {e}")
        
        return None
    
    async def _cache_result(self, domain: str, profile: CompanyProfile):
        """Cache company data for 30 days"""
        # Redis cache
        if self.redis_client and profile:
            try:
                cache_key = f"company:{domain}"
                await self.redis_client.setex(
                    cache_key,
                    2592000,  # 30 days
                    json.dumps(profile.model_dump(), default=str)
                )
            except Exception as e:
                logger.error(f"Redis cache error: {e}")
        
        # Database cache
        try:
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO company_profiles_cache (domain, profile_data, expires_at)
                    VALUES ($1, $2, NOW() + INTERVAL '30 days')
                    ON CONFLICT (domain) DO UPDATE SET
                        profile_data = EXCLUDED.profile_data,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW()
                    """,
                    domain,
                    json.dumps(profile.model_dump(), default=str)
                )
        except Exception as e:
            logger.error(f"Database cache error: {e}")
    
    async def batch_enrich(
        self,
        domains: List[str],
        country: Optional[str] = None,
        max_concurrent: int = 2  # Reduced from 5 to avoid rate limits
    ) -> BatchEnrichmentResult:
        """Enrich multiple domains concurrently with rate limiting"""
        
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        
        async def enrich_with_semaphore(domain: str):
            async with semaphore:
                try:
                    # Add delay between requests to respect rate limits
                    await asyncio.sleep(0.5)  # 500ms delay = max 2 requests per second
                    profile = await self.enrich_domain(domain, country)
                    return CompanyEnrichmentResult(
                        domain=domain,
                        success=profile is not None,
                        profile=profile,
                        cached=False  # TODO: Track if from cache
                    )
                except Exception as e:
                    logger.error(f"Error enriching {domain}: {e}")
                    return CompanyEnrichmentResult(
                        domain=domain,
                        success=False,
                        error=str(e)
                    )
        
        # Process all domains
        tasks = [enrich_with_semaphore(domain) for domain in domains]
        results = await asyncio.gather(*tasks)
        
        # Calculate summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        return BatchEnrichmentResult(
            job_id="",  # Will be set by caller
            client_id="",  # Will be set by caller
            total=len(domains),
            successful=successful,
            failed=failed,
            results=results,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
    
    async def store_company_profile(self, client_id: str, profile: CompanyProfile):
        """Store enriched company profile in database"""
        
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO company_profiles (
                    domain, company_name, industry, sub_industry,
                    revenue_amount, revenue_currency, headcount,
                    founded_year, description, technologies,
                    headquarters_location, source, client_id, source_type
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (domain) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    industry = EXCLUDED.industry,
                    sub_industry = EXCLUDED.sub_industry,
                    revenue_amount = EXCLUDED.revenue_amount,
                    headcount = EXCLUDED.headcount,
                    description = EXCLUDED.description,
                    technologies = EXCLUDED.technologies,
                    headquarters_location = EXCLUDED.headquarters_location,
                    source_type = EXCLUDED.source_type,
                    enriched_at = NOW()
                """,
                profile.domain,
                profile.company_name,
                profile.industry,
                profile.sub_industry,
                profile.revenue_amount,
                profile.revenue_currency,
                profile.headcount,
                profile.founded_year,
                profile.description,
                json.dumps(profile.technologies),
                json.dumps(profile.headquarters_location) if profile.headquarters_location else None,
                profile.source,
                client_id,
                profile.source_type
            )