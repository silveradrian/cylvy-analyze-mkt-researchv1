#!/usr/bin/env python3
"""
Comprehensive test script to populate all configuration and run a test pipeline.
This avoids the need to manually fill out frontend forms.
"""
import asyncio
import aiohttp
import json
import sys
from datetime import datetime

# Base URL for the API - use localhost:8000 when running inside container
import os
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000/api/v1")

# Test data
COMPANY_CONFIG = {
    "company_name": "Finastra",
    "company_domain": "finastra.com",
    "legal_name": "Finastra International Limited",
    "description": """Finastra is one of the world's largest fintech companies, serving over 8,600 financial institutions globally. 
    We provide innovative software solutions that enable banks, credit unions, and other financial institutions to deliver 
    better customer experiences and operate more efficiently. Our open platform approach and commitment to innovation helps 
    our customers accelerate their digital transformation journey.""",
    "additional_domains": [
        "finastra.co.uk",
        "fusionbanking.com",
        "misys.com",
        "d3banking.com"
    ],
    "competitors": [
        {
            "name": "FIS Global",
            "domains": ["fisglobal.com", "worldpay.com"]
        },
        {
            "name": "Fiserv",
            "domains": ["fiserv.com", "firstdata.com"]
        },
        {
            "name": "Jack Henry",
            "domains": ["jackhenry.com", "banno.com"]
        }
    ],
    "primary_color": "#3B82F6",
    "secondary_color": "#10B981"
}

PERSONAS = [
    {
        "name": "Digital Banking Leader",
        "description": "Senior executive responsible for digital transformation strategy in financial institutions",
        "title": "VP of Digital Banking / Chief Digital Officer",
        "goals": [
            "Modernize legacy banking infrastructure",
            "Enhance digital customer experience",
            "Increase digital adoption rates",
            "Reduce operational costs through automation"
        ],
        "pain_points": [
            "Legacy system integration complexity",
            "Regulatory compliance requirements",
            "Customer data security concerns",
            "Resistance to change from traditional teams"
        ],
        "decision_criteria": [
            "Platform flexibility and openness",
            "Regulatory compliance capabilities",
            "Total cost of ownership",
            "Vendor stability and reputation"
        ],
        "content_preferences": [
            "Digital transformation case studies",
            "ROI calculators and business cases",
            "Executive briefings",
            "Regulatory compliance guides"
        ]
    },
    {
        "name": "Technical Architecture Expert",
        "description": "Technology leader responsible for enterprise architecture and technical implementation",
        "title": "Enterprise Architect / VP of Technology",
        "goals": [
            "Build scalable and secure architecture",
            "Enable API-first integration strategy",
            "Reduce technical debt",
            "Ensure platform flexibility"
        ],
        "pain_points": [
            "Complex legacy system dependencies",
            "Multiple vendor integration requirements",
            "Data migration and synchronization",
            "Performance at scale"
        ],
        "decision_criteria": [
            "API completeness and documentation",
            "Cloud-native architecture",
            "Security certifications and standards",
            "Developer experience and tools"
        ],
        "content_preferences": [
            "Technical architecture whitepapers",
            "API documentation and guides",
            "Security and compliance documentation",
            "Integration playbooks"
        ]
    }
]

KEYWORDS = [
    {
        "keyword": "digital payments",
        "client_id": "default",
        "country": "US",
        "category": "Payments",
        "jtbd_stage": "SOLUTION_EXPLORATION",
        "avg_monthly_searches": 1900,
        "competition": 33,
        "competition_index": 28,
        "low_top_page_bid": 3.36,
        "high_top_page_bid": 14.89,
        "client_score": 95,
        "client_rationale": "Highly relevant as digital payments are a core offering of Finastra.",
        "persona_score": 90,
        "persona_rationale": "Highly relevant to the Payments Innovator focused on modernizing payment systems.",
        "seo_score": 90,
        "seo_rationale": "Excellent SEO opportunity with good volume and low competition",
        "composite_score": 92,
        "is_brand": False
    },
    {
        "keyword": "payment processing software",
        "client_id": "default",
        "country": "US",
        "category": "Payments",
        "jtbd_stage": "SOLUTION_EXPLORATION",
        "avg_monthly_searches": 1600,
        "competition": 33,
        "competition_index": 5,
        "low_top_page_bid": 13.03,
        "high_top_page_bid": 42,
        "client_score": 95,
        "client_rationale": "Highly relevant to company's business as it directly aligns with their payment solutions offerings.",
        "persona_score": 90,
        "persona_rationale": "Highly relevant to persona because payment processing is a key focus for payment innovators.",
        "seo_score": 90,
        "seo_rationale": "Excellent SEO opportunity with good volume and low competition",
        "composite_score": 92,
        "is_brand": False
    },
    {
        "keyword": "banking digital transformation",
        "client_id": "default",
        "country": "US",
        "category": "Universal Banking",
        "jtbd_stage": "SOLUTION_EXPLORATION",
        "avg_monthly_searches": 1000,
        "competition": 33,
        "competition_index": 2,
        "low_top_page_bid": 6.56,
        "high_top_page_bid": 19.35,
        "client_score": 95,
        "client_rationale": "Highly relevant to company's business as digital transformation is a core focus of Finastra's strategy and offerings.",
        "persona_score": 90,
        "persona_rationale": "Highly relevant to persona because it aligns with their goals of modernization and innovation in banking.",
        "seo_score": 90,
        "seo_rationale": "Excellent SEO opportunity with good volume and low competition",
        "composite_score": 92,
        "is_brand": False
    },
    {
        "keyword": "commercial loan origination system",
        "client_id": "default",
        "country": "US",
        "category": "Lending",
        "jtbd_stage": "SOLUTION_EXPLORATION",
        "avg_monthly_searches": 320,
        "competition": 33,
        "competition_index": 26,
        "low_top_page_bid": 6,
        "high_top_page_bid": 16.2,
        "client_score": 95,
        "client_rationale": "Highly relevant to company's business as it directly aligns with Finastra's lending solutions.",
        "persona_score": 95,
        "persona_rationale": "Highly relevant to persona, particularly the Modern Lending Leader, due to their focus on loan origination.",
        "seo_score": 80,
        "seo_rationale": "Excellent SEO opportunity with good volume and low competition",
        "composite_score": 92,
        "is_brand": False
    },
    {
        "keyword": "ai in financial services",
        "client_id": "default",
        "country": "US",
        "category": "Co-innovation",
        "jtbd_stage": "SOLUTION_EXPLORATION",
        "avg_monthly_searches": 1600,
        "competition": 33,
        "competition_index": 23,
        "low_top_page_bid": 7.37,
        "high_top_page_bid": 21.72,
        "client_score": 95,
        "client_rationale": "Highly relevant to company's business as AI is a key component of Finastra's technology strategy.",
        "persona_score": 90,
        "persona_rationale": "Highly relevant to persona because AI is crucial for driving efficiency and innovation in their roles.",
        "seo_score": 90,
        "seo_rationale": "Excellent SEO opportunity with good volume and low competition",
        "composite_score": 92,
        "is_brand": False
    }
]

CUSTOM_DIMENSIONS = [
    {
        "name": "Innovation Focus",
        "description": "Emphasis on cutting-edge technology and forward-thinking approaches",
        "scoring_criteria": [
            "Mentions of emerging technologies (AI, blockchain, cloud-native)",
            "Discussion of future trends and predictions",
            "Case studies of innovative implementations",
            "Focus on disruption and transformation"
        ],
        "relevance_indicators": [
            "Innovation",
            "Digital transformation",
            "Next-generation",
            "Future of banking"
        ],
        "group_id": "content-style"
    },
    {
        "name": "Regulatory Expertise",
        "description": "Demonstration of deep regulatory knowledge and compliance capabilities",
        "scoring_criteria": [
            "References to specific regulations (PSD2, Basel III, etc.)",
            "Compliance best practices",
            "Risk management strategies",
            "Regulatory change management"
        ],
        "relevance_indicators": [
            "Compliance",
            "Regulation",
            "Risk management",
            "Governance"
        ],
        "group_id": "expertise-depth"
    },
    {
        "name": "Customer Success Focus",
        "description": "Emphasis on real customer outcomes and success stories",
        "scoring_criteria": [
            "Specific customer metrics and KPIs",
            "Named customer case studies",
            "ROI and business impact data",
            "Implementation timelines and results"
        ],
        "relevance_indicators": [
            "Customer success",
            "Case study",
            "ROI",
            "Business impact"
        ],
        "group_id": "content-credibility"
    }
]

DIMENSION_GROUPS = [
    {
        "id": "content-style",
        "name": "Content Style & Tone",
        "description": "How the content is presented and its tonal qualities",
        "selection_strategy": "highest_score"
    },
    {
        "id": "expertise-depth",
        "name": "Expertise & Authority",
        "description": "Level of domain expertise and thought leadership demonstrated",
        "selection_strategy": "highest_confidence"
    },
    {
        "id": "content-credibility",
        "name": "Credibility & Evidence",
        "description": "Use of data, proof points, and substantiation",
        "selection_strategy": "most_evidence"
    }
]

GARTNER_JTBD = [
    {
        "name": "Problem Identification",
        "description": "Recognizing challenges and exploring potential solutions",
        "scoring_criteria": [
            "Problem definition and pain points",
            "Impact analysis and urgency",
            "Initial solution exploration",
            "Budget considerations"
        ],
        "relevance_indicators": [
            "challenges",
            "problems",
            "pain points",
            "issues"
        ]
    },
    {
        "name": "Solution Exploration",
        "description": "Researching and evaluating different solution options",
        "scoring_criteria": [
            "Feature comparisons",
            "Vendor landscape analysis",
            "Technology evaluations",
            "Requirements gathering"
        ],
        "relevance_indicators": [
            "comparison",
            "evaluation",
            "alternatives",
            "options"
        ]
    }
]

SCHEDULE_CONFIG = {
    "schedule_name": "Weekly Analysis",
    "frequency": "weekly",
    "day_of_week": 1,  # Monday
    "time_of_day": "09:00",
    "time_zone": "America/New_York",
    "max_keywords_per_run": 5,
    "is_active": True
}

async def make_request(session, method, endpoint, data=None, headers=None):
    """Make an HTTP request and return the response."""
    url = f"{BASE_URL}{endpoint}"
    default_headers = {
        "Authorization": "Bearer test-token-for-development",
        "Content-Type": "application/json"
    }
    if headers:
        default_headers.update(headers)
    
    try:
        async with session.request(method, url, json=data, headers=default_headers) as response:
            text = await response.text()
            print(f"{method} {endpoint}: {response.status}")
            
            if response.status >= 400:
                print(f"Error response: {text}")
                return None
            
            if text:
                return json.loads(text)
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

async def setup_company_config(session):
    """Set up company configuration."""
    print("\n=== Setting up Company Configuration ===")
    result = await make_request(session, "PUT", "/config", COMPANY_CONFIG)
    if result:
        print(f"✓ Company configured: {result.get('company_name')}")
    return result

async def setup_personas(session):
    """Create buyer personas."""
    print("\n=== Setting up Buyer Personas ===")
    
    # Update personas using PUT endpoint
    result = await make_request(session, "PUT", "/analysis/personas", {"personas": PERSONAS})
    if result:
        print(f"✓ Created {len(PERSONAS)} personas")
        for persona in PERSONAS:
            print(f"  - {persona['name']}: {persona['title']}")
    
    return PERSONAS

async def setup_keywords(session):
    """Create keywords."""
    print("\n=== Setting up Keywords ===")
    
    # First, delete existing keywords
    existing = await make_request(session, "GET", "/keywords")
    if existing and existing.get('keywords'):
        for keyword in existing['keywords']:
            await make_request(session, "DELETE", f"/keywords/{keyword['id']}")
    
    # Create new keywords
    created_keywords = []
    for keyword in KEYWORDS:
        result = await make_request(session, "POST", "/keywords", keyword)
        if result:
            print(f"✓ Created keyword: {keyword['keyword']}")
            created_keywords.append(result)
    
    return created_keywords

async def setup_analysis_config(session):
    """Set up analysis configuration with dimension groups and custom dimensions."""
    print("\n=== Setting up Analysis Configuration ===")
    
    # Create dimension groups
    print("\nCreating dimension groups...")
    for group in DIMENSION_GROUPS:
        result = await make_request(session, "POST", "/analysis/dimension-groups", group)
        if result:
            print(f"✓ Created dimension group: {group['name']}")
    
    # Create custom dimensions
    print("\nCreating custom dimensions...")
    for dimension in CUSTOM_DIMENSIONS:
        result = await make_request(session, "POST", "/analysis/custom-dimensions", dimension)
        if result:
            print(f"✓ Created custom dimension: {dimension['name']}")
    
    # Set up JTBD phases
    print("\nConfiguring JTBD phases...")
    for phase in GARTNER_JTBD:
        result = await make_request(session, "POST", "/analysis/jtbd-phases", phase)
        if result:
            print(f"✓ Created JTBD phase: {phase['name']}")
    
    return True

async def setup_schedule(session):
    """Set up pipeline schedule."""
    print("\n=== Setting up Pipeline Schedule ===")
    
    # Delete existing schedules
    existing = await make_request(session, "GET", "/schedules")
    if existing and existing.get('schedules'):
        for schedule in existing['schedules']:
            await make_request(session, "DELETE", f"/schedules/{schedule['id']}")
    
    # Create new schedule
    result = await make_request(session, "POST", "/schedules", SCHEDULE_CONFIG)
    if result:
        print(f"✓ Created schedule: {result.get('schedule_name')}")
    
    return result

async def verify_setup(session):
    """Verify all configuration is in place."""
    print("\n=== Verifying Setup ===")
    
    # Check company config
    config = await make_request(session, "GET", "/config")
    if config:
        print(f"✓ Company: {config.get('company_name')}")
        print(f"  - Domains: {len(config.get('additional_domains', [])) + 1}")
        print(f"  - Competitors: {len(config.get('competitors', []))}")
    
    # Check personas
    personas = await make_request(session, "GET", "/analysis/personas")
    if personas:
        print(f"✓ Personas: {len(personas.get('personas', []))}")
    
    # Check keywords
    keywords = await make_request(session, "GET", "/keywords")
    if keywords:
        print(f"✓ Keywords: {len(keywords.get('keywords', []))}")
    
    # Check custom dimensions
    dimensions = await make_request(session, "GET", "/analysis/custom-dimensions")
    if dimensions:
        print(f"✓ Custom Dimensions: {len(dimensions.get('dimensions', []))}")
    
    # Check schedules
    schedules = await make_request(session, "GET", "/schedules")
    if schedules:
        print(f"✓ Schedules: {len(schedules.get('schedules', []))}")
    
    return True

async def run_test_pipeline(session):
    """Run a test pipeline with a small batch of keywords."""
    print("\n=== Running Test Pipeline ===")
    
    # Get first 3 keywords
    keywords_response = await make_request(session, "GET", "/keywords")
    if not keywords_response or not keywords_response.get('keywords'):
        print("No keywords found!")
        return
    
    keyword_ids = [kw['id'] for kw in keywords_response['keywords'][:3]]
    
    # Start pipeline
    pipeline_data = {
        "keyword_ids": keyword_ids,
        "run_type": "manual"
    }
    
    print(f"Starting pipeline with {len(keyword_ids)} keywords...")
    result = await make_request(session, "POST", "/pipeline/start", pipeline_data)
    
    if result:
        pipeline_id = result.get('pipeline_id')
        print(f"✓ Pipeline started: {pipeline_id}")
        
        # Monitor status
        print("\nMonitoring pipeline status...")
        for i in range(30):  # Check for 5 minutes
            await asyncio.sleep(10)
            status = await make_request(session, "GET", f"/pipeline/{pipeline_id}/status")
            if status:
                current_status = status.get('status', 'unknown')
                current_phase = status.get('current_phase', 'none')
                print(f"  Status: {current_status} | Phase: {current_phase}")
                
                if current_status in ['completed', 'failed']:
                    print(f"\nPipeline {current_status}!")
                    if current_status == 'failed':
                        print(f"Error: {status.get('error_message', 'Unknown error')}")
                    break
    
    return result

async def main():
    """Main test function."""
    print("=== Cylvy Digital Landscape Analyzer - Full Setup Test ===")
    print(f"API URL: {BASE_URL}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Setup all configuration
            await setup_company_config(session)
            await setup_personas(session)
            await setup_keywords(session)
            await setup_analysis_config(session)
            await setup_schedule(session)
            
            # Verify setup
            await verify_setup(session)
            
            # Run test pipeline
            print("\nReady to run test pipeline? Press Enter to continue or Ctrl+C to exit...")
            input()
            
            await run_test_pipeline(session)
            
            print(f"\n✓ Test completed at: {datetime.now().isoformat()}")
            
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Check if backend is accessible
    import requests
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"Backend health check failed: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Cannot connect to backend at {BASE_URL}")
        print("Make sure the backend is running: docker-compose up -d")
        sys.exit(1)
    
    # Run the test
    asyncio.run(main())
