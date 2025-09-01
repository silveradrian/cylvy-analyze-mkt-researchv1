-- Cylvy Digital Landscape Analyzer - Initial Schema
-- Single-instance deployment (no multi-tenancy)

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Client configuration (single record)
CREATE TABLE client_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    company_domain VARCHAR(255) NOT NULL,
    company_logo_url TEXT,
    primary_color VARCHAR(7) DEFAULT '#3B82F6',
    secondary_color VARCHAR(7) DEFAULT '#10B981',
    
    -- Contact Information
    admin_email VARCHAR(255),
    support_email VARCHAR(255),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Analysis configuration (single record)
CREATE TABLE analysis_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- JSON configurations
    personas JSONB NOT NULL DEFAULT '[]',
    jtbd_phases JSONB NOT NULL DEFAULT '[]',
    competitor_domains JSONB NOT NULL DEFAULT '[]',
    custom_dimensions JSONB NOT NULL DEFAULT '{}',
    
    -- AI Configuration
    temperature DECIMAL(3,2) DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4000,
    model VARCHAR(50) DEFAULT 'gpt-4-turbo-preview',
    
    -- Feature flags
    enable_mention_extraction BOOLEAN DEFAULT true,
    enable_sentiment_analysis BOOLEAN DEFAULT true,
    enable_competitor_tracking BOOLEAN DEFAULT true,
    enable_historical_tracking BOOLEAN DEFAULT true,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- API Keys (encrypted storage)
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(50) UNIQUE NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users table for authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_role CHECK (role IN ('viewer', 'analyst', 'admin', 'superadmin'))
);

-- Keywords
CREATE TABLE keywords (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100),
    jtbd_stage VARCHAR(100),
    is_brand BOOLEAN DEFAULT false,
    
    -- Scoring
    client_score DECIMAL(3,2),
    persona_score DECIMAL(3,2),
    seo_score DECIMAL(3,2),
    composite_score DECIMAL(3,2),
    
    -- Metrics
    avg_monthly_searches INTEGER,
    competition_level VARCHAR(20),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- SERP Results
CREATE TABLE serp_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword_id UUID NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    search_date DATE NOT NULL,
    location VARCHAR(10) NOT NULL, -- US, UK, etc.
    serp_type VARCHAR(20) NOT NULL, -- organic, news, video
    
    -- Result data
    position INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    domain VARCHAR(255),
    
    -- Additional metadata
    featured_snippet BOOLEAN DEFAULT false,
    site_links JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(keyword_id, search_date, location, serp_type, url)
);

-- Create indexes for SERP results
CREATE INDEX idx_serp_keyword_date ON serp_results(keyword_id, search_date DESC);
CREATE INDEX idx_serp_domain ON serp_results(domain);
CREATE INDEX idx_serp_type ON serp_results(serp_type);

-- Scraped Content
CREATE TABLE scraped_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL UNIQUE,
    domain VARCHAR(255),
    
    -- Content
    title TEXT,
    content TEXT,
    html TEXT,
    meta_description TEXT,
    
    -- Metadata
    word_count INTEGER,
    language VARCHAR(10),
    published_date DATE,
    author VARCHAR(255),
    
    -- Status
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Company Profiles
CREATE TABLE company_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(255) NOT NULL UNIQUE,
    
    -- Company info
    company_name VARCHAR(255),
    industry VARCHAR(255),
    sub_industry VARCHAR(255),
    description TEXT,
    
    -- Size metrics
    revenue_amount DECIMAL(15,2),
    revenue_currency VARCHAR(10),
    employee_count INTEGER,
    founded_year INTEGER,
    
    -- Location
    headquarters_location JSONB,
    
    -- Additional data
    technologies JSONB DEFAULT '[]',
    social_profiles JSONB DEFAULT '{}',
    
    -- Source tracking
    source VARCHAR(50), -- cognism, clearbit, manual
    source_updated_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Video Content
CREATE TABLE video_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id VARCHAR(100) NOT NULL UNIQUE,
    platform VARCHAR(20) DEFAULT 'youtube',
    
    -- Video metadata
    title TEXT,
    description TEXT,
    channel_id VARCHAR(100),
    channel_name VARCHAR(255),
    
    -- Metrics
    view_count BIGINT,
    like_count INTEGER,
    comment_count INTEGER,
    
    -- Additional info
    duration_seconds INTEGER,
    published_at TIMESTAMPTZ,
    tags JSONB DEFAULT '[]',
    
    -- Transcript
    transcript TEXT,
    transcript_available BOOLEAN DEFAULT false,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content Analysis Results
CREATE TABLE content_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    
    -- Categorization
    content_classification VARCHAR(50),
    sub_category VARCHAR(100),
    
    -- Persona alignment
    primary_persona VARCHAR(100),
    persona_alignment_scores JSONB DEFAULT '{}',
    
    -- JTBD alignment  
    jtbd_phase VARCHAR(100),
    jtbd_alignment_score DECIMAL(3,2),
    
    -- Analysis results
    summary TEXT,
    key_topics JSONB DEFAULT '[]',
    buyer_intent_signals JSONB DEFAULT '[]',
    
    -- Mentions
    brand_mentions JSONB DEFAULT '[]',
    competitor_mentions JSONB DEFAULT '[]',
    
    -- Sentiment
    overall_sentiment VARCHAR(20),
    sentiment_score DECIMAL(3,2),
    
    -- Quality metrics
    content_quality_score DECIMAL(3,2),
    readability_score DECIMAL(3,2),
    
    -- Custom dimensions
    custom_dimension_scores JSONB DEFAULT '{}',
    
    -- AI Analysis metadata
    model_used VARCHAR(50),
    confidence_scores JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(url, analysis_date)
);

-- DSI Calculations
CREATE TABLE dsi_calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_date DATE NOT NULL,
    
    -- Company rankings
    company_rankings JSONB NOT NULL DEFAULT '[]',
    
    -- Page rankings
    page_rankings JSONB NOT NULL DEFAULT '[]',
    
    -- Calculation metadata
    total_companies INTEGER,
    total_pages INTEGER,
    keywords_analyzed INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Prompt Configurations
CREATE TABLE prompt_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Prompt templates
    system_prompt TEXT,
    analysis_prompt_template TEXT,
    persona_prompt_template TEXT,
    jtbd_prompt_template TEXT,
    
    -- Configuration
    prompt_variables JSONB DEFAULT '{}',
    output_schema JSONB,
    
    -- Status
    is_active BOOLEAN DEFAULT false,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Create update triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_client_config_updated_at BEFORE UPDATE ON client_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analysis_config_updated_at BEFORE UPDATE ON analysis_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_keywords_updated_at BEFORE UPDATE ON keywords
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_company_profiles_updated_at BEFORE UPDATE ON company_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_video_content_updated_at BEFORE UPDATE ON video_content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_prompt_configurations_updated_at BEFORE UPDATE ON prompt_configurations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Default admin user will be created by initialization script
-- This allows for customizable admin credentials per deployment

