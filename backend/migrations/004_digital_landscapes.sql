-- Digital Landscape Manager Schema
-- Migration: 003_digital_landscapes.sql

-- 1. Digital Landscape Definitions
CREATE TABLE IF NOT EXISTS digital_landscapes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Keyword-to-Landscape Mapping
CREATE TABLE IF NOT EXISTS landscape_keywords (
    landscape_id UUID NOT NULL,
    keyword_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (landscape_id, keyword_id),
    FOREIGN KEY (landscape_id) REFERENCES digital_landscapes(id) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
);

-- 3. Comprehensive Landscape DSI Metrics Storage
CREATE TABLE IF NOT EXISTS landscape_dsi_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landscape_id UUID NOT NULL,
    calculation_date DATE NOT NULL,
    entity_type VARCHAR(20) NOT NULL, -- 'company' or 'page'
    
    -- Entity identification
    entity_id UUID,
    entity_name VARCHAR(255),
    entity_domain VARCHAR(255),
    entity_url VARCHAR(500), -- For page-level metrics
    
    -- Core DSI Metrics
    unique_keywords INTEGER NOT NULL DEFAULT 0,
    unique_pages INTEGER NOT NULL DEFAULT 0,
    keyword_coverage DECIMAL(8,4) NOT NULL DEFAULT 0,
    estimated_traffic BIGINT NOT NULL DEFAULT 0,
    traffic_share DECIMAL(8,4) NOT NULL DEFAULT 0,
    
    -- DSI Score Components
    persona_alignment DECIMAL(8,4) DEFAULT 0,
    funnel_value DECIMAL(8,4) DEFAULT 0,
    dsi_score DECIMAL(8,4) NOT NULL DEFAULT 0,
    
    -- Rankings
    rank_in_landscape INTEGER NOT NULL,
    total_entities_in_landscape INTEGER NOT NULL,
    market_position VARCHAR(20) DEFAULT 'NICHE', -- 'LEADER', 'CHALLENGER', 'COMPETITOR', 'NICHE'
    
    -- Calculation metadata
    calculation_period_days INTEGER DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    FOREIGN KEY (landscape_id) REFERENCES digital_landscapes(id) ON DELETE CASCADE,
    UNIQUE(landscape_id, calculation_date, entity_type, entity_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_digital_landscapes_active ON digital_landscapes(is_active);
CREATE INDEX IF NOT EXISTS idx_landscape_keywords_landscape ON landscape_keywords(landscape_id);
CREATE INDEX IF NOT EXISTS idx_landscape_keywords_keyword ON landscape_keywords(keyword_id);

CREATE INDEX IF NOT EXISTS idx_landscape_dsi_landscape_date ON landscape_dsi_metrics(landscape_id, calculation_date);
CREATE INDEX IF NOT EXISTS idx_landscape_dsi_entity ON landscape_dsi_metrics(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_landscape_dsi_rankings ON landscape_dsi_metrics(landscape_id, calculation_date, rank_in_landscape);
CREATE INDEX IF NOT EXISTS idx_landscape_dsi_score ON landscape_dsi_metrics(dsi_score DESC);

-- Try to create TimescaleDB hypertable (will fail gracefully if TimescaleDB not installed)
DO $$
BEGIN
    -- Create hypertable for time-series optimization
    PERFORM create_hypertable('landscape_dsi_metrics', 'calculation_date', if_not_exists => TRUE);
    RAISE NOTICE 'Created TimescaleDB hypertable for landscape_dsi_metrics';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'TimescaleDB not available, using regular table for landscape_dsi_metrics';
END
$$;
