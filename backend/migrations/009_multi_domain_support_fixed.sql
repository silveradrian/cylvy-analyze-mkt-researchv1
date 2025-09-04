-- Multi-Domain Support for Companies and Competitors (Fixed)
-- Migration: 009_multi_domain_support_fixed.sql

-- Create company_domains table for multiple domains per company
CREATE TABLE company_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL,
    domain_type VARCHAR(50) NOT NULL DEFAULT 'primary',
    country_code VARCHAR(10),
    is_active BOOLEAN DEFAULT true,
    is_primary BOOLEAN DEFAULT false,
    
    -- Domain metadata
    notes TEXT,
    discovered_date DATE DEFAULT CURRENT_DATE,
    last_verified DATE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(domain)
);

-- Create unique constraint for primary domain per company (conditional)
CREATE UNIQUE INDEX company_domains_primary_unique 
ON company_domains(company_id) 
WHERE is_primary = true;

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
    market_focus VARCHAR(100),
    competitive_strength VARCHAR(20),
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(domain)
);

-- Create unique constraint for primary domain per competitor (conditional)
CREATE UNIQUE INDEX competitor_domains_primary_unique 
ON competitor_domains(competitor_name) 
WHERE is_primary = true;

-- Create indexes for performance
CREATE INDEX idx_company_domains_company ON company_domains(company_id);
CREATE INDEX idx_company_domains_country ON company_domains(country_code);
CREATE INDEX idx_company_domains_active ON company_domains(domain) WHERE is_active = true;

CREATE INDEX idx_competitor_domains_name ON competitor_domains(competitor_name);
CREATE INDEX idx_competitor_domains_country ON competitor_domains(country_code);
CREATE INDEX idx_competitor_domains_active ON competitor_domains(domain) WHERE is_active = true;

-- Add comment for documentation
COMMENT ON TABLE company_domains IS 'Multiple domains per company supporting country TLDs, subsidiaries, and brand domains';
COMMENT ON TABLE competitor_domains IS 'Multiple domains per competitor for comprehensive competitive intelligence';

