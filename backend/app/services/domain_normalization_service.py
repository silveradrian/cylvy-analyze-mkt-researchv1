"""
Domain Normalization Service - Client-Agnostic Root Domain Extraction
Ensures schema relationship integrity across SERP domains and company profiles
"""

import re
from typing import Dict, Set, Optional
from urllib.parse import urlparse

class DomainNormalizationService:
    """Client-agnostic domain normalization for consistent data relationships"""
    
    @staticmethod
    def extract_root_domain(domain: str) -> str:
        """
        Extract root domain from any subdomain with comprehensive TLD handling
        
        Examples:
        - www.finastra.com → finastra.com
        - blog.finastra.com → finastra.com  
        - resources.gartner.co.uk → gartner.co.uk
        - api-docs.stripe.com → stripe.com
        """
        if not domain or not isinstance(domain, str):
            return domain or ''
        
        # Remove protocol and path
        domain = domain.replace('http://', '').replace('https://', '')
        domain = domain.split('/')[0].split('?')[0].split('#')[0]
        
        # Remove port
        domain = domain.split(':')[0]
        
        # Convert to lowercase
        domain = domain.lower().strip()
        
        if not domain:
            return ''
        
        # Split into parts
        parts = domain.split('.')
        
        if len(parts) < 2:
            return domain
        
        # Handle special TLD cases
        if len(parts) >= 3:
            # Multi-part TLDs (.co.uk, .com.au, .org.uk, etc.)
            if (parts[-2] in ['co', 'com', 'org', 'net', 'gov', 'edu', 'ac'] and 
                parts[-1] in ['uk', 'au', 'nz', 'za', 'in', 'ca', 'jp', 'de', 'fr']):
                # Keep domain.co.uk format (last 3 parts)
                return '.'.join(parts[-3:])
            
            # Regular domains - extract root (last 2 parts)
            return '.'.join(parts[-2:])
        
        # Already a root domain
        return domain
    
    @staticmethod
    def normalize_for_company_matching(domain: str) -> str:
        """
        Normalize domain specifically for company profile matching
        This is what should be used for JOINs with company_profiles table
        """
        root = DomainNormalizationService.extract_root_domain(domain)
        
        # Additional normalizations for company matching
        root = root.replace('www.', '')  # Remove any remaining www
        
        return root
    
    @staticmethod 
    def create_domain_mapping(serp_domains: list) -> Dict[str, str]:
        """
        Create mapping from SERP domains to normalized root domains
        Returns: {serp_domain: root_domain}
        """
        mapping = {}
        
        for domain in serp_domains:
            root = DomainNormalizationService.normalize_for_company_matching(domain)
            mapping[domain] = root
        
        return mapping
    
    @staticmethod
    def get_company_aggregation_key(
        serp_domain: str, 
        company_name: Optional[str] = None,
        parent_company_name: Optional[str] = None
    ) -> str:
        """
        Get the key for company aggregation in DSI calculations
        Priority: Parent Company > Enriched Company > Root Domain
        """
        if parent_company_name:
            return parent_company_name
        
        if company_name:
            return company_name
            
        # Fallback to cleaned root domain as company name
        root = DomainNormalizationService.normalize_for_company_matching(serp_domain)
        # Convert domain to readable company name
        company_fallback = root.replace('.com', '').replace('.net', '').replace('.org', '')
        company_fallback = company_fallback.replace('-', ' ').replace('_', ' ')
        return company_fallback.title()

# SQL Helper Functions for Database Usage

def get_root_domain_sql_expression(domain_column: str) -> str:
    """
    Get SQL expression to extract root domain from a domain column
    """
    return f"""
        LOWER(
            CASE 
                -- Handle www prefix
                WHEN {domain_column} LIKE 'www.%' THEN SUBSTRING({domain_column} FROM 5)
                -- Handle other subdomains (keep last 2 parts after splitting on .)
                WHEN array_length(string_to_array({domain_column}, '.'), 1) > 2 
                THEN array_to_string(
                    (string_to_array({domain_column}, '.'))[
                        array_length(string_to_array({domain_column}, '.'), 1) - 1:
                        array_length(string_to_array({domain_column}, '.'), 1)
                    ], '.')
                ELSE {domain_column}
            END
        )
    """

def get_company_aggregation_sql(
    serp_domain_column: str,
    company_name_column: str = 'cp.company_name',
    parent_company_column: str = 'cr.parent_company_name'
) -> str:
    """
    Get SQL expression for company aggregation key
    """
    root_domain_expr = get_root_domain_sql_expression(serp_domain_column)
    
    return f"""
        COALESCE(
            {parent_company_column},  -- Use parent company if available
            {company_name_column},    -- Use enriched company name
            INITCAP(REPLACE(REPLACE({root_domain_expr}, '.com', ''), '.', ' '))  -- Clean domain fallback
        )
    """
