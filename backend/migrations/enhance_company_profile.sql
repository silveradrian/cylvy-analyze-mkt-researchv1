-- Enhance company profile for comprehensive AI analysis context
-- This provides rich context about the analyzing company to help AI better evaluate content

-- Add comprehensive company profile fields to client_config table
ALTER TABLE client_config ADD COLUMN IF NOT EXISTS company_profile JSONB DEFAULT '{}';

-- The company_profile JSONB will contain:
-- {
--   "basic_info": {
--     "full_name": "Acme Corporation Inc.",
--     "legal_name": "Acme Corp",
--     "founded_year": 2010,
--     "headquarters": "San Francisco, CA",
--     "employee_count": "100-500",
--     "funding_stage": "Series B",
--     "company_type": "B2B SaaS"
--   },
--   "business_model": {
--     "primary_offering": "Cloud-based project management software",
--     "target_market": "Mid-market technology companies",
--     "pricing_model": "Subscription-based SaaS",
--     "average_deal_size": "$50,000-$100,000",
--     "sales_cycle": "3-6 months",
--     "go_to_market": "Product-led growth with enterprise sales"
--   },
--   "positioning": {
--     "value_proposition": "The only project management tool built specifically for agile software teams",
--     "key_differentiators": [
--       "AI-powered sprint planning",
--       "Native Git integration",
--       "Real-time collaboration"
--     ],
--     "competitive_advantages": [
--       "10x faster onboarding than competitors",
--       "Only solution with predictive analytics"
--     ],
--     "market_position": "Challenger brand disrupting legacy players"
--   },
--   "target_audience": {
--     "ideal_customer_profile": {
--       "company_size": "100-1000 employees",
--       "industries": ["Technology", "Financial Services", "Healthcare Tech"],
--       "characteristics": ["Fast-growing", "Tech-forward", "Agile methodology"]
--     },
--     "buyer_personas": [
--       {
--         "title": "VP of Engineering",
--         "pain_points": ["Team productivity", "Project visibility", "Tool sprawl"],
--         "goals": ["Ship faster", "Reduce technical debt", "Improve team morale"]
--       }
--     ],
--     "use_cases": [
--       "Sprint planning and tracking",
--       "Cross-team collaboration",
--       "Executive reporting"
--     ]
--   },
--   "brand_attributes": {
--     "personality": ["Innovative", "Approachable", "Reliable", "Expert"],
--     "tone_of_voice": "Professional yet friendly, avoiding jargon",
--     "core_values": ["Transparency", "Customer Success", "Continuous Innovation"],
--     "mission": "Empower software teams to build better products faster"
--   },
--   "competitive_landscape": {
--     "direct_competitors": ["Jira", "Monday.com", "Asana"],
--     "indirect_competitors": ["Notion", "ClickUp", "Linear"],
--     "market_category": "Agile Project Management",
--     "competitive_positioning": "Premium features at mid-market pricing"
--   },
--   "growth_metrics": {
--     "current_arr": "$10M-$20M",
--     "growth_rate": "150% YoY",
--     "customer_count": "500+",
--     "nps_score": 72,
--     "churn_rate": "5% annually"
--   },
--   "strategic_priorities": {
--     "current_focus": ["Enterprise expansion", "AI feature development", "Partner ecosystem"],
--     "expansion_plans": ["European market entry", "Mobile app launch", "API marketplace"],
--     "key_initiatives": ["SOC2 certification", "Gartner Magic Quadrant inclusion"]
--   }
-- }

-- Create function to validate company profile
CREATE OR REPLACE FUNCTION validate_company_profile(profile JSONB)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check for required top-level keys
    IF NOT (profile ? 'basic_info' AND profile ? 'business_model' AND profile ? 'positioning') THEN
        RETURN FALSE;
    END IF;
    
    -- Check for minimum required fields in basic_info
    IF NOT (profile->'basic_info' ? 'full_name' AND profile->'basic_info' ? 'primary_offering') THEN
        RETURN FALSE;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Add constraint to ensure valid profile when set
ALTER TABLE client_config ADD CONSTRAINT valid_company_profile 
    CHECK (company_profile = '{}' OR validate_company_profile(company_profile));

-- Create view for easy access to company context
CREATE OR REPLACE VIEW company_analysis_context AS
SELECT 
    id as project_id,
    company_name,
    company_domain,
    description,
    company_profile->>'basic_info' as basic_info,
    company_profile->>'business_model' as business_model,
    company_profile->>'positioning' as positioning,
    company_profile->>'target_audience' as target_audience,
    company_profile->>'brand_attributes' as brand_attributes,
    company_profile->>'competitive_landscape' as competitive_landscape,
    -- Generate AI context summary
    CONCAT(
        'Company: ', company_name, ' (', company_domain, '). ',
        COALESCE(company_profile->'basic_info'->>'primary_offering', description), '. ',
        'Target Market: ', COALESCE(company_profile->'business_model'->>'target_market', 'Not specified'), '. ',
        'Value Prop: ', COALESCE(company_profile->'positioning'->>'value_proposition', 'Not specified'), '. ',
        'Key Differentiators: ', COALESCE(company_profile->'positioning'->>'key_differentiators'::text, 'Not specified')
    ) as ai_context_summary
FROM client_config;

-- Function to get comprehensive company context for AI
CREATE OR REPLACE FUNCTION get_company_ai_context(p_project_id UUID)
RETURNS TEXT AS $$
DECLARE
    context TEXT;
    profile JSONB;
BEGIN
    SELECT company_profile INTO profile
    FROM client_config
    WHERE id = p_project_id;
    
    IF profile IS NULL OR profile = '{}'::jsonb THEN
        -- Return basic context if no enhanced profile
        SELECT CONCAT(
            'Analyzing content for ', company_name, ' (', company_domain, '). ',
            COALESCE(description, 'No additional context available.')
        ) INTO context
        FROM client_config
        WHERE id = p_project_id;
    ELSE
        -- Build comprehensive context
        context := 'COMPANY CONTEXT FOR ANALYSIS:' || E'\n\n';
        
        -- Basic info
        context := context || '**Company Overview**' || E'\n';
        context := context || '- Name: ' || COALESCE(profile->'basic_info'->>'full_name', 'Not specified') || E'\n';
        context := context || '- Type: ' || COALESCE(profile->'basic_info'->>'company_type', 'Not specified') || E'\n';
        context := context || '- Size: ' || COALESCE(profile->'basic_info'->>'employee_count', 'Not specified') || E'\n';
        
        -- Business model
        context := context || E'\n**Business Model**' || E'\n';
        context := context || '- Offering: ' || COALESCE(profile->'business_model'->>'primary_offering', 'Not specified') || E'\n';
        context := context || '- Target Market: ' || COALESCE(profile->'business_model'->>'target_market', 'Not specified') || E'\n';
        context := context || '- Pricing: ' || COALESCE(profile->'business_model'->>'pricing_model', 'Not specified') || E'\n';
        
        -- Positioning
        context := context || E'\n**Market Positioning**' || E'\n';
        context := context || '- Value Proposition: ' || COALESCE(profile->'positioning'->>'value_proposition', 'Not specified') || E'\n';
        context := context || '- Key Differentiators: ' || COALESCE(profile->'positioning'->>'key_differentiators'::text, 'Not specified') || E'\n';
        context := context || '- Market Position: ' || COALESCE(profile->'positioning'->>'market_position', 'Not specified') || E'\n';
        
        -- Target audience
        context := context || E'\n**Target Audience**' || E'\n';
        context := context || '- ICP: ' || COALESCE(profile->'target_audience'->'ideal_customer_profile'::text, 'Not specified') || E'\n';
        
        -- Brand
        context := context || E'\n**Brand Attributes**' || E'\n';
        context := context || '- Personality: ' || COALESCE(profile->'brand_attributes'->>'personality'::text, 'Not specified') || E'\n';
        context := context || '- Tone: ' || COALESCE(profile->'brand_attributes'->>'tone_of_voice', 'Not specified') || E'\n';
        
        -- Competition
        context := context || E'\n**Competitive Context**' || E'\n';
        context := context || '- Direct Competitors: ' || COALESCE(profile->'competitive_landscape'->>'direct_competitors'::text, 'Not specified') || E'\n';
        context := context || '- Market Category: ' || COALESCE(profile->'competitive_landscape'->>'market_category', 'Not specified') || E'\n';
    END IF;
    
    RETURN context;
END;
$$ LANGUAGE plpgsql;

-- Add comment explaining the enhancement
COMMENT ON COLUMN client_config.company_profile IS 
'Comprehensive company profile providing rich context for AI analysis including business model, positioning, target audience, brand attributes, and competitive landscape';
