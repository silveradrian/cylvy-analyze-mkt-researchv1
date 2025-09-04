-- Multi-Domain Support for Companies and Competitors
-- Migration: 009_multi_domain_support.sql

-- Create company_domains table for multiple domains per company
CREATE TABLE company_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL,
    domain_type VARCHAR(50) NOT NULL DEFAULT 'primary', -- 'primary', 'country_tld', 'subsidiary', 'brand'
    country_code VARCHAR(10), -- US, UK, DE, etc. for country-specific domains
    is_active BOOLEAN DEFAULT true,
    is_primary BOOLEAN DEFAULT false, -- One primary domain per company
    
    -- Domain metadata
    notes TEXT, -- e.g., "German subsidiary", "Legacy domain", etc.
    discovered_date DATE DEFAULT CURRENT_DATE,
    last_verified DATE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(domain),
    UNIQUE(company_id, is_primary) WHERE is_primary = true -- Only one primary domain per company
);

-- Create competitor_domains table for multiple competitor domains
CREATE TABLE competitor_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    domain_type VARCHAR(50) NOT NULL DEFAULT 'primary',
    country_code VARCHAR(10),
    is_active BOOLEAN DEFAULT true,
    is_primary BOOLEAN DEFAULT false,
    
    -- Competitive intelligence metadata
    market_focus VARCHAR(100), -- e.g., "European Banking", "Asia-Pacific FinTech"
    competitive_strength VARCHAR(20), -- 'HIGH', 'MEDIUM', 'LOW'
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(domain),
    UNIQUE(competitor_name, is_primary) WHERE is_primary = true
);

-- Update SERP results to reference domain instead of company directly
-- (This allows linking to any domain in the company_domains table)
ALTER TABLE serp_results 
ADD COLUMN IF NOT EXISTS company_domain_id UUID REFERENCES company_domains(id);

-- Create indexes for performance
CREATE INDEX idx_company_domains_company ON company_domains(company_id);
CREATE INDEX idx_company_domains_country ON company_domains(country_code);
CREATE INDEX idx_company_domains_active ON company_domains(domain) WHERE is_active = true;
CREATE INDEX idx_company_domains_primary ON company_domains(company_id) WHERE is_primary = true;

CREATE INDEX idx_competitor_domains_name ON competitor_domains(competitor_name);
CREATE INDEX idx_competitor_domains_country ON competitor_domains(country_code);
CREATE INDEX idx_competitor_domains_active ON competitor_domains(domain) WHERE is_active = true;

-- Create view for easy company domain lookup
CREATE OR REPLACE VIEW company_all_domains AS
SELECT 
    cp.id as company_id,
    cp.company_name,
    cp.domain as legacy_primary_domain, -- Keep backward compatibility
    cd.id as domain_id,
    cd.domain,
    cd.domain_type,
    cd.country_code,
    cd.is_primary,
    cd.is_active,
    cd.notes as domain_notes
FROM company_profiles cp
LEFT JOIN company_domains cd ON cp.id = cd.company_id AND cd.is_active = true
ORDER BY cp.company_name, cd.is_primary DESC, cd.domain;

-- Create view for competitor domain analysis
CREATE OR REPLACE VIEW competitor_all_domains AS
SELECT 
    competitor_name,
    domain,
    domain_type,
    country_code,
    market_focus,
    competitive_strength,
    is_primary,
    is_active
FROM competitor_domains 
WHERE is_active = true
ORDER BY competitor_name, is_primary DESC, domain;

-- Create domain intelligence view for competitive analysis
CREATE OR REPLACE VIEW domain_intelligence AS
SELECT 
    d.domain,
    d.domain_type,
    d.country_code,
    'COMPANY' as entity_type,
    cp.company_name as entity_name,
    cp.source as company_source,
    d.is_primary
FROM company_domains d
JOIN company_profiles cp ON d.company_id = cp.id
WHERE d.is_active = true

UNION ALL

SELECT 
    d.domain,
    d.domain_type,
    d.country_code,
    'COMPETITOR' as entity_type,
    d.competitor_name as entity_name,
    d.competitive_strength as company_source,
    d.is_primary
FROM competitor_domains d
WHERE d.is_active = true

ORDER BY domain;

-- Add comments
COMMENT ON TABLE company_domains IS 'Multiple domains per company supporting country TLDs, subsidiaries, and brand domains';
COMMENT ON TABLE competitor_domains IS 'Multiple domains per competitor for comprehensive competitive intelligence';
COMMENT ON COLUMN company_domains.domain_type IS 'Domain classification: primary, country_tld, subsidiary, brand, legacy';
COMMENT ON COLUMN competitor_domains.competitive_strength IS 'Competitive threat level: HIGH, MEDIUM, LOW';

