#!/usr/bin/env python3
"""
Direct database setup script for Finastra project configuration.
This bypasses API endpoints to directly populate the database.
"""
import asyncio
import sys
import os
from datetime import datetime
import json

# Add app to path
sys.path.append('/app')

from app.core.database import db_pool
from app.core.config import settings

# Company configuration
COMPANY_CONFIG = {
    "company_name": "Finastra",
    "company_domain": "finastra.com",
    "legal_name": "Finastra International Limited",
    "description": """Finastra is one of the world's largest fintech companies, serving over 8,600 financial institutions globally. 
    We provide innovative software solutions that enable banks, credit unions, and other financial institutions to deliver 
    better customer experiences and operate more efficiently. Our open platform approach and commitment to innovation helps 
    our customers accelerate their digital transformation journey. With offices in 42 countries and over 10,000 employees, 
    we process $4.5 trillion in transactions annually and unlock the value of financial services technology.""",
    "additional_domains": ["finastra.com", "finastrafs.com", "fusionbanking.com"],
    "competitors": [
        {"name": "Temenos", "domains": ["temenos.com"]},
        {"name": "FIS", "domains": ["fisglobal.com"]},
        {"name": "Jack Henry", "domains": ["jackhenry.com"]}
    ],
    "primary_color": "#3B82F6",
    "secondary_color": "#10B981"
}

# Personas
PERSONAS = [
    {
        "name": "The Payments Innovator",
        "description": "Modernize payments infrastructure while preserving compliance and operational stability. Balances high-volume processing with real-time speed, API integrations, and fraud/AML controls.",
        "title": "Head of Payments / VP of Transaction Banking / Director of Operations/Payment Systems / Chief Digital Officer",
        "goals": [
            "Modernize payments infrastructure",
            "Achieve real-time processing capabilities",
            "Unlock value from ISO 20022 data",
            "Drive business value from payments"
        ],
        "pain_points": [
            "Legacy systems limitations",
            "Regulatory change management",
            "Uptime/SLA expectations",
            "Risk management complexity"
        ],
        "decision_criteria": [
            "Scalability",
            "Interoperability",
            "Operational resilience",
            "Scheme compliance",
            "Customer experience"
        ],
        "content_preferences": [
            "Fresh thinking and co-solving approaches",
            "Collaborative problem solving",
            "Trusted partnership evidence",
            "Innovation case studies"
        ]
    },
    {
        "name": "The Modern Lending Leader",
        "description": "Transform legacy lending into streamlined, automated, compliant workflows across products. Under pressure to cut time-to-decision and origination costs while improving borrower experience.",
        "title": "Head of Lending / Director of Credit & Risk / VP of Commercial or Retail Lending / Chief Lending Officer",
        "goals": [
            "Transform lending workflows",
            "Cut time-to-decision",
            "Reduce origination costs",
            "Improve borrower experience"
        ],
        "pain_points": [
            "Changing regulations",
            "Diverse product lines (syndicated, mortgage, consumer, trade)",
            "Integration with existing LOS/LMS",
            "Fintech partner integration"
        ],
        "decision_criteria": [
            "Lifecycle coverage (origination → underwriting → docs/closing → servicing)",
            "Compliance-by-design",
            "Intelligent automation",
            "Measurable ROI"
        ],
        "content_preferences": [
            "Co-innovation approaches",
            "Evolution with needs",
            "Proven outcomes",
            "Modularity over rip-and-replace"
        ]
    },
    {
        "name": "The Digital Banking Architect",
        "description": "Drive digital transformation with an agile, cloud-ready core and unified, secure customer journeys. Aims to build connected, personalized banking without fragmentation.",
        "title": "Chief Technology Officer / Head of Core Banking / VP of Digital Transformation / Director of IT Architecture",
        "goals": [
            "Build agile, cloud-ready core",
            "Create unified customer journeys",
            "Eliminate system fragmentation",
            "Balance technical depth with commercial impact"
        ],
        "pain_points": [
            "Complexity reduction",
            "Regulatory agility",
            "Integration debt",
            "TCO management",
            "Time-to-launch pressure"
        ],
        "decision_criteria": [
            "Composable/open architecture",
            "Ecosystem compatibility",
            "Data-led decisions",
            "Security/resilience",
            "Multi-region scalability"
        ],
        "content_preferences": [
            "Architecture and business value alignment",
            "Platform thinking",
            "Long-term vision",
            "Operating model alignment"
        ]
    }
]

# Keywords from the CSV
KEYWORDS = [
    {
        "keyword": "digital payments",
        "client_id": "default",
        "country": "US",
        "category": "Payments",
        "jtbd_stage": "SOLUTION_EXPLORATION",
        "avg_monthly_searches": 1900,
        "competition": 33,
        "competition_index": 28.0,
        "low_top_page_bid": 3.36,
        "high_top_page_bid": 14.89,
        "client_score": 95.0,
        "client_rationale": "Highly relevant as digital payments are a core offering of Finastra.",
        "persona_score": 90.0,
        "persona_rationale": "Highly relevant to the Payments Innovator focused on modernizing payment systems.",
        "seo_score": 90.0,
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
        "competition_index": 5.0,
        "low_top_page_bid": 13.03,
        "high_top_page_bid": 42.0,
        "client_score": 95.0,
        "client_rationale": "Highly relevant to company's business as it directly aligns with their payment solutions offerings.",
        "persona_score": 90.0,
        "persona_rationale": "Highly relevant to persona because payment processing is a key focus for payment innovators.",
        "seo_score": 90.0,
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
        "competition_index": 2.0,
        "low_top_page_bid": 6.56,
        "high_top_page_bid": 19.35,
        "client_score": 95.0,
        "client_rationale": "Highly relevant to company's business as digital transformation is a core focus of Finastra's strategy and offerings.",
        "persona_score": 90.0,
        "persona_rationale": "Highly relevant to persona because it aligns with their goals of modernization and innovation in banking.",
        "seo_score": 90.0,
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
        "competition_index": 26.0,
        "low_top_page_bid": 6.0,
        "high_top_page_bid": 16.2,
        "client_score": 95.0,
        "client_rationale": "Highly relevant to company's business as it directly aligns with Finastra's lending solutions.",
        "persona_score": 95.0,
        "persona_rationale": "Highly relevant to persona, particularly the Modern Lending Leader, due to their focus on loan origination.",
        "seo_score": 80.0,
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
        "competition_index": 23.0,
        "low_top_page_bid": 7.37,
        "high_top_page_bid": 21.72,
        "client_score": 95.0,
        "client_rationale": "Highly relevant to company's business as AI is a key component of Finastra's technology strategy.",
        "persona_score": 90.0,
        "persona_rationale": "Highly relevant to persona because AI is crucial for driving efficiency and innovation in their roles.",
        "seo_score": 90.0,
        "seo_rationale": "Excellent SEO opportunity with good volume and low competition",
        "composite_score": 92,
        "is_brand": False
    }
]

async def setup_database():
    """Initialize database and create tables if needed."""
    print("Initializing database connection...")
    await db_pool.initialize()
    print("✓ Database connected")

async def setup_company_config():
    """Set up company configuration."""
    print("\n=== Setting up Company Configuration ===")
    
    async with db_pool.acquire() as conn:
        # Check if config exists
        existing = await conn.fetchval("SELECT id FROM client_config LIMIT 1")
        
        if existing:
            # Update existing
            await conn.execute("""
                UPDATE client_config SET
                    company_name = $1,
                    company_domain = $2,
                    legal_name = $3,
                    description = $4,
                    additional_domains = $5,
                    competitors = $6::jsonb,
                    primary_color = $7,
                    secondary_color = $8,
                    updated_at = NOW()
                WHERE id = $9
            """, 
                COMPANY_CONFIG['company_name'],
                COMPANY_CONFIG['company_domain'],
                COMPANY_CONFIG['legal_name'],
                COMPANY_CONFIG['description'],
                COMPANY_CONFIG['additional_domains'],
                json.dumps(COMPANY_CONFIG['competitors']),
                COMPANY_CONFIG['primary_color'],
                COMPANY_CONFIG['secondary_color'],
                existing
            )
            print(f"✓ Updated company config: {COMPANY_CONFIG['company_name']}")
        else:
            # Insert new
            await conn.execute("""
                INSERT INTO client_config (
                    company_name, company_domain, legal_name, description,
                    additional_domains, competitors, primary_color, secondary_color
                ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
            """,
                COMPANY_CONFIG['company_name'],
                COMPANY_CONFIG['company_domain'],
                COMPANY_CONFIG['legal_name'],
                COMPANY_CONFIG['description'],
                COMPANY_CONFIG['additional_domains'],
                json.dumps(COMPANY_CONFIG['competitors']),
                COMPANY_CONFIG['primary_color'],
                COMPANY_CONFIG['secondary_color']
            )
            print(f"✓ Created company config: {COMPANY_CONFIG['company_name']}")

# Gartner JTBD Phases
JTBD_PHASES = [
    {
        "name": "Problem Identification",
        "description": "Clear articulation of the customer's business/operational problem, stakes, and urgency.",
        "evaluation_criteria": {
            "what_counts": "Clear articulation of the customer's business/operational problem, stakes, and urgency (regulatory deadlines, risk exposure, cost/time impact). Problems should be framed in the customer's words and context (role, process, metrics).",
            "strong_signals": [
                "Quantified pain (%, cost, time, risk)",
                "External triggers (e.g., regulatory date)",
                "Before/after baselines",
                "Role/process specificity",
                "Real customer voice or research insight"
            ],
            "weak_signals": [
                "Vague 'businesses face challenges'",
                "Generic trends without who/why/impact"
            ],
            "scoring_guidance": {
                "0-2": "Generic problem talk; no role/process/metric",
                "3-4": "Names a problem area but lacks stakes or context",
                "5-6": "Specific, role/process-anchored problem with some quantification",
                "7-8": "Clear urgency (e.g., dated trigger) + quantified business impact",
                "9-10": "Customer-voiced problem with baselines and quantified stakes across multiple contexts"
            }
        }
    },
    {
        "name": "Solution Exploration",
        "description": "Exploration of viable approaches/categories and how they work, with options and trade-offs.",
        "evaluation_criteria": {
            "what_counts": "Exploration of viable approaches/categories and how they work, with options and trade-offs (not yet vendor selection). Early experiments (POCs/pilots/workshops) and learnings show rigor.",
            "strong_signals": [
                "Multiple solution paths with pros/cons",
                "Architecture/operating model explanations",
                "Pilot results",
                "Decision criteria defined",
                "Alignment to buyer roles/use cases"
            ],
            "weak_signals": [
                "'Technology can help' without mechanisms, categories, or trade-offs"
            ],
            "scoring_guidance": {
                "0-2": "Generic solution rhetoric",
                "3-4": "Names a category but no 'how it works' or alternatives",
                "5-6": "Explains ≥2 approaches with context/trade-offs",
                "7-8": "Adds pilot/workshop learnings and explicit decision criteria",
                "9-10": "Repeatable exploration framework with validated learnings applied across scenarios"
            }
        }
    },
    {
        "name": "Requirements Building",
        "description": "Explicit, testable requirements (functional + non-functional), acceptance criteria, constraints, and measurement plans.",
        "evaluation_criteria": {
            "what_counts": "Explicit, testable requirements (functional + non-functional), acceptance criteria, constraints, and measurement plans tied to the problem. Traceability from problem → requirement → success metric.",
            "strong_signals": [
                "Detailed criteria (e.g., throughput/SLA, compliance controls, integration boundaries)",
                "Prioritization (MoSCoW/RICE)",
                "Governance and validation methods"
            ],
            "weak_signals": [
                "'Secure/flexible/scalable' with no targets, thresholds, or tests"
            ],
            "scoring_guidance": {
                "0-2": "Generalized 'need features' statements",
                "3-4": "Single vague requirement",
                "5-6": "Several explicit requirements with some measurability",
                "7-8": "Prioritized, testable requirements mapped to outcomes and constraints",
                "9-10": "Comprehensive, governed requirements set with full traceability and metrics"
            }
        }
    },
    {
        "name": "Supplier Selection",
        "description": "Evidence-based comparison of vendors/offerings against weighted criteria.",
        "evaluation_criteria": {
            "what_counts": "Evidence-based comparison of vendors/offerings against weighted criteria; risk/cost models; feasibility/roadmap fit. Clear reasons-to-believe (proof points) tied to requirements.",
            "strong_signals": [
                "Comparative matrices",
                "Quantified TCO/ROI/performance",
                "Risk/mitigation",
                "Implementation plan",
                "Scale/credibility evidence used appropriately"
            ],
            "weak_signals": [
                "'We're trusted/leading' with no evidence or criteria linkage"
            ],
            "scoring_guidance": {
                "0-2": "Generic supplier claims",
                "3-4": "Mentions differentiators, no proof",
                "5-6": "Concrete differentiators with partial evidence",
                "7-8": "Structured comparison with quantified proof tied to criteria",
                "9-10": "Multi-criteria, quantified evaluation with risks, costs, and credible scale proof integrated"
            }
        }
    },
    {
        "name": "Validation",
        "description": "Proof that the chosen solution delivered results.",
        "evaluation_criteria": {
            "what_counts": "Proof that the chosen solution delivered results: case studies with metrics, multiple references, time-bounded outcomes, ongoing KPI governance, and post-implementation learning.",
            "strong_signals": [
                "Quantified before/after",
                "Repeatability across customers/segments",
                "Third-party corroboration (analyst/media/audit)",
                "Sustained KPI reviews and continuous improvement"
            ],
            "weak_signals": [
                "Single testimonial without specifics or timeframe"
            ],
            "scoring_guidance": {
                "0-2": "Generic 'customers succeed with us'",
                "3-4": "One example, minimal detail",
                "5-6": "Case with some quantified outcomes",
                "7-8": "Multiple cases with quantified, time-boxed results and learnings",
                "9-10": "Programmatic validation (multi-customer, repeatable, corroborated) with ongoing governance"
            }
        }
    }
]

# Custom Dimensions
CUSTOM_DIMENSIONS = [
    # Strategic Pillars
    {
        "name": "Customer Obsession",
        "description": "Customer-centricity in financial services means showing up as a true partner. It's not just about providing solutions, but solving problems side-by-side. The most forward-thinking institutions listen carefully—through advisory boards, feedback loops, and open conversations—and act quickly. Whether it's helping clients modernize critical systems, strengthen security, or adopt new innovations, the goal is always to advise, challenge, and lead when needed. By supporting modernization, improving operations, and enabling growth, financial services providers help customers succeed on their own terms and realize tangible value from technology and expertise.",
        "dimension_type": "strategic_pillar",
        "evaluation_criteria": {
            "strong_signals": [
                "Customer Advisory Boards / VOC",
                "Roadmap co-creation",
                "QBRs/success plans", 
                "Rapid response and guided modernization",
                "Named outcomes/metrics"
            ],
            "weak_signals": [
                "Slogans ('customer-first')",
                "Generic testimonials without actions or results"
            ],
            "scoring_guidance": {
                "0-2": "Generic partner language; no mechanisms or outcomes",
                "3-4": "Mentions programs but no evidence of impact",
                "5-6": "Describes mechanisms and at least one concrete customer action taken",
                "7-8": "Mechanisms + named customer(s) with quantified outcome(s)",
                "9-10": "Programmatic, repeatable practice with multiple quantified outcomes"
            }
        }
    },
    {
        "name": "Reliable, Secure & Trusted Financial Services Software",
        "description": "Trust is the foundation of financial services. Institutions and providers must deliver secure, reliable, and trusted systems that underpin critical operations worldwide. Proven expertise, combined with modern technology, helps organizations remain resilient, compliant, and ready for the future. A secure-by-design approach ensures that innovation can move forward with confidence—customers know their systems are protected, operations are dependable, and they are backed by partners they can rely on.",
        "dimension_type": "strategic_pillar",
        "evaluation_criteria": {
            "strong_signals": [
                "SOC 2/ISO 27001/PCI",
                "Secure SDLC/threat modeling/pen tests",
                "Encryption & key mgmt (HSM/KMS/SBOM)",
                "SLO/SLA, RTO/RPO, active-active, DR drills/postmortems",
                "Data residency, audit trails, SoD"
            ],
            "weak_signals": [
                "Bank-grade/enterprise-grade security",
                "Trusted", 
                "Robust with no artifact"
            ],
            "scoring_guidance": {
                "0-2": "Trust/security claims only",
                "3-4": "One control or certification mentioned without depth",
                "5-6": "Multiple controls/certs or clear reliability targets",
                "7-8": "Controls + reliability patterns + compliance specifics",
                "9-10": "Comprehensive program with continuous improvement"
            }
        }
    },
    {
        "name": "Co-Innovation",
        "description": "Innovation in financial services isn't something handed down—it's something built together. Leading institutions collaborate with customers, partners, fintechs, and experts to create solutions that address real-world challenges and unlock new opportunities. Through design thinking, joint pilots, and continuous feedback loops, every innovation—from process improvements to advancements in AI—is made practical, scalable, and impactful. By working together, the industry can move faster, stay ahead of change, and deliver better outcomes for businesses, individuals, and communities alike.",
        "dimension_type": "strategic_pillar",
        "evaluation_criteria": {
            "strong_signals": [
                "Design thinking/discovery workshops",
                "Joint pilots/POCs",
                "Co-authored features/IP",
                "Marketplace or partner integrations",
                "Feedback incorporated into GA releases"
            ],
            "weak_signals": [
                "We innovate with customers without programs",
                "No artifacts or outcomes"
            ],
            "scoring_guidance": {
                "0-2": "Innovation rhetoric only",
                "3-4": "Mentions pilots/partners but no detail or results",
                "5-6": "Describes a concrete workshop/pilot with learning",
                "7-8": "Joint initiative with measurable impact that shipped",
                "9-10": "Repeatable co-innovation framework with multiple outcomes"
            }
        }
    },
    # Business Units
    {
        "name": "Payments",
        "description": "The payments space is evolving rapidly, driven by changing customer expectations, new standards like ISO 20022, and the global rise of real-time, digital-first services. Today's financial institutions must process high volumes efficiently, reduce operational friction, and meet growing compliance demands across domestic, cross-border and instant payment rails.  modern payments strategy requires more than speed. It calls for scalable infrastructure, fraud protection, interoperability, and API-led connectivity to fintechs and partners. Institutions are prioritizing automation, cost reduction, and customer experience, all while navigating legacy constraints and ongoing regulatory shifts.",
        "dimension_type": "business_unit",
        "evaluation_criteria": {
            "strong_signals": [
                "ISO 20022, SWIFT gpi, SEPA, FedNow, RTP, UPI, PIX, TIPS",
                "Payment hubs/orchestration",
                "Sanctions screening/AML/3DS2",
                "Event-driven/microservices",
                "Ops metrics"
            ],
            "competitors": ["FIS", "Fiserv", "Temenos", "ACI Worldwide", "Kyriba", "Oracle Banking Payments", "AccessPay", "Mambu", "Nomentia", "PayU"],
            "scoring_guidance": {
                "0-2": "Vague payments mentions",
                "3-4": "Names a rail/standard without depth",
                "5-6": "Covers 2–3 concrete elements",
                "7-8": "Architectural/operational depth with compliance",
                "9-10": "End-to-end modernization narrative with outcomes"
            }
        }
    },
    {
        "name": "Lending",
        "description": "Lending is a core engine of banking revenue, but outdated systems, manual workflows and compliance pressures are holding many financial institutions back. Whether managing complex syndicated loans, digitizing mortgage processes or scaling consumer lending, banks are looking to simplify operations and improve time to value. Modern lending solutions help automate origination, enhance decision-making, ensure compliance, and deliver better borrower experiences. Financial institutions are also seeking flexibility, like modular tools, digital journeys and seamless integration with fintech partners, to adapt to fast-changing market needs.",
        "dimension_type": "business_unit",
        "evaluation_criteria": {
            "strong_signals": [
                "LOS/LMS, rule engines, model governance",
                "KYC/AML, income/asset verification",
                "Pricing/decisioning",
                "E-closing/e-vault",
                "Open banking data",
                "Borrower CX metrics"
            ],
            "competitors": ["FIS", "Fiserv", "Temenos", "nCino", "TCS BaNCS", "Infosys Finacle", "LendingFront", "Mambu"],
            "scoring_guidance": {
                "0-2": "Superficial lending references",
                "3-4": "Single step named without specifics",
                "5-6": "Multiple lifecycle steps or concrete tooling",
                "7-8": "Full lifecycle + controls/integrations + outcomes",
                "9-10": "Comprehensive program with demonstrated impact"
            }
        }
    },
    {
        "name": "Universal Banking",
        "description": "Universal banks face the challenge of delivering personalized, seamless experiences across multiple lines of business—retail, corporate, wealth, and beyond—while modernizing their core infrastructure. Success depends on unifying data, unlocking flexibility, and reducing complexity through cloud adoption and open architecture. Financial institutions are moving towards composable banking platforms, integrated customer experiences, and real-time insights. The goal: agility to launch new services quickly, scale across regions and channels, and respond faster to market and regulatory change – all without compromising resilience or security.",
        "dimension_type": "business_unit",
        "evaluation_criteria": {
            "strong_signals": [
                "Composable/microservices/event streaming",
                "API gateways/open architecture", 
                "Single customer view, personalization, omnichannel",
                "Cloud migration patterns, regionalization, resilience"
            ],
            "competitors": ["FIS", "Fiserv", "Temenos", "Oracle FLEXCUBE", "TCS BaNCS", "Infosys Finacle", "SDK.finance"],
            "scoring_guidance": {
                "0-2": "Broad platform claims only",
                "3-4": "Mentions multi-LOB without tech detail",
                "5-6": "Names composable/Open APIs or unified CX",
                "7-8": "Clear architecture + operational model + CX",
                "9-10": "Proven multi-region deployment with outcomes"
            }
        }
    }
]

async def setup_personas():
    """Set up buyer personas in analysis config."""
    print("\n=== Setting up Buyer Personas ===")
    
    async with db_pool.acquire() as conn:
        # Check if analysis config exists
        existing = await conn.fetchval("SELECT id FROM analysis_config LIMIT 1")
        
        if not existing:
            # Create default analysis config
            await conn.execute("""
                INSERT INTO analysis_config (personas, jtbd_phases, competitor_domains, custom_dimensions)
                VALUES ($1::jsonb, $2::jsonb, $3::jsonb, $4::jsonb)
            """, 
                json.dumps(PERSONAS),
                json.dumps([]),
                json.dumps([]),
                json.dumps({})
            )
            print(f"✓ Created analysis config with {len(PERSONAS)} personas")
        else:
            # Update personas
            await conn.execute("""
                UPDATE analysis_config 
                SET personas = $1::jsonb, updated_at = NOW()
                WHERE id = $2
            """, json.dumps(PERSONAS), existing)
            print(f"✓ Updated {len(PERSONAS)} personas")
        
        for persona in PERSONAS:
            print(f"  - {persona['name']}: {persona['title']}")

async def setup_jtbd_phases():
    """Set up JTBD phases in analysis config."""
    print("\n=== Setting up JTBD Phases ===")
    
    async with db_pool.acquire() as conn:
        # Update analysis_config with JTBD phases
        await conn.execute("""
            UPDATE analysis_config 
            SET jtbd_phases = $1::jsonb
        """, json.dumps(JTBD_PHASES))
        
        print(f"✓ Updated {len(JTBD_PHASES)} JTBD phases")
        
        for phase in JTBD_PHASES:
            print(f"  - {phase['name']}: {phase['description'][:60]}...")

async def setup_custom_dimensions():
    """Set up custom dimensions and dimension groups."""
    print("\n=== Setting up Custom Dimensions ===")
    
    async with db_pool.acquire() as conn:
        # Delete existing dimension groups and dimensions (check if tables exist first)
        tables_exist = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('analysis_primary_dimensions', 'dimension_group_members', 'dimension_groups', 'generic_custom_dimensions')
        """)
        existing_tables = [row['tablename'] for row in tables_exist]
        
        if 'analysis_primary_dimensions' in existing_tables:
            await conn.execute("DELETE FROM analysis_primary_dimensions")
        if 'dimension_group_members' in existing_tables:
            await conn.execute("DELETE FROM dimension_group_members")
        if 'dimension_groups' in existing_tables:
            await conn.execute("DELETE FROM dimension_groups")
        if 'generic_custom_dimensions' in existing_tables:
            await conn.execute("DELETE FROM generic_custom_dimensions")
        
        # Check if dimension_groups table exists
        dimension_groups_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = 'dimension_groups'
            )
        """)
        
        strategic_group_id = None
        business_group_id = None
        
        if not dimension_groups_exists:
            print("⚠️  Dimension groups table not found. Skipping dimension grouping.")
            # Still create dimensions without groups
        else:
            # Create dimension groups
            print("\n📁 Creating dimension groups...")
            
            # Strategic Pillars group
            strategic_group_id = await conn.fetchval("""
                INSERT INTO dimension_groups (
                    group_id, name, description, selection_strategy, display_order, is_active
                ) VALUES ($1, $2, $3, $4, $5, true) RETURNING id
            """,
                "strategic_pillars",
                "Strategic Pillars",
                "Core strategic focus areas that guide all content and messaging",
                "highest_score",
                1
            )
            print(f"  ✓ Created group: Strategic Pillars")
            
            # Business Units group
            business_group_id = await conn.fetchval("""
                INSERT INTO dimension_groups (
                    group_id, name, description, selection_strategy, display_order, is_active
                ) VALUES ($1, $2, $3, $4, $5, true) RETURNING id
            """,
                "business_units",
                "Business Units",
                "Primary business domains and solution areas",
                "highest_score",
                2
            )
            print(f"  ✓ Created group: Business Units")
        
        # Insert new custom dimensions and track their types
        print("\n📐 Creating custom dimensions...")
        dimension_mappings = []  # Track dimension_id, name, and type
        
        for i, dim in enumerate(CUSTOM_DIMENSIONS):
            dimension_id = f"dim_{i+1:03d}"
            
            # Build AI context
            ai_context = {
                "general_description": dim['description'],
                "purpose": f"Evaluate content relevance to {dim['name']}",
                "scope": dim.get('dimension_type', 'custom'),
                "key_focus_areas": dim['evaluation_criteria'].get('strong_signals', []),
                "analysis_approach": "Evidence-based scoring with specific signals"
            }
            
            # Build criteria
            criteria = {
                "what_counts": dim['description'],
                "positive_signals": dim['evaluation_criteria'].get('strong_signals', []),
                "negative_signals": dim['evaluation_criteria'].get('weak_signals', []),
                "exclusions": [],
                "additional_context": []  # Removed competitors - this should not be hardcoded
            }
            
            # Build scoring framework
            scoring_framework = {
                "levels": dim['evaluation_criteria'].get('scoring_guidance', {}),
                "evidence_requirements": "Strong, verifiable details required for high scores",
                "contextual_rules": "Score based on depth and specificity of evidence"
            }
            
            await conn.execute("""
                INSERT INTO generic_custom_dimensions (
                    client_id, dimension_id, name, description, ai_context, criteria, 
                    scoring_framework, is_active
                ) VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, true)
            """,
                'default',  # client_id
                dimension_id,
                dim['name'],
                dim['description'],
                json.dumps(ai_context),
                json.dumps(criteria),
                json.dumps(scoring_framework)
            )
            print(f"  ✓ Created dimension: {dim['name']} ({dim.get('dimension_type', 'custom')})")
            
            # Track for group assignment
            dimension_mappings.append({
                'dimension_id': dimension_id,
                'name': dim['name'],
                'type': dim.get('dimension_type', 'custom')
            })
        
        # Assign dimensions to groups only if dimension groups exist
        if dimension_groups_exists:
            print("\n🔗 Assigning dimensions to groups...")
            priority = 1
            
            # Assign strategic pillars
            for dim in dimension_mappings:
                if dim['type'] == 'strategic_pillar':
                    await conn.execute("""
                        INSERT INTO dimension_group_members (
                            group_id, dimension_id, priority
                        ) VALUES ($1, $2, $3)
                    """, strategic_group_id, dim['dimension_id'], priority)
                    priority += 1
                    print(f"  ✓ Assigned '{dim['name']}' to Strategic Pillars")
            
            # Reset priority for business units
            priority = 1
            
            # Assign business units
            for dim in dimension_mappings:
                if dim['type'] == 'business_unit':
                    await conn.execute("""
                        INSERT INTO dimension_group_members (
                            group_id, dimension_id, priority
                        ) VALUES ($1, $2, $3)
                    """, business_group_id, dim['dimension_id'], priority)
                    priority += 1
                    print(f"  ✓ Assigned '{dim['name']}' to Business Units")
            
            print(f"\n✓ Total custom dimensions created: {len(CUSTOM_DIMENSIONS)}")
            print(f"✓ Dimension groups configured: 2")
        else:
            print(f"\n✓ Total custom dimensions created: {len(CUSTOM_DIMENSIONS)}")

async def setup_keywords():
    """Set up keywords."""
    print("\n=== Setting up Keywords ===")
    
    async with db_pool.acquire() as conn:
        # Delete related historical data first
        await conn.execute("""
            DELETE FROM historical_keyword_metrics 
            WHERE keyword_id IN (SELECT id FROM keywords)
        """)
        
        # Delete existing keywords
        await conn.execute("DELETE FROM keywords")
        
        # Insert new keywords
        for kw in KEYWORDS:
            # Map competition index to competition level
            competition_level = 'Low'
            if kw['competition_index'] > 30:
                competition_level = 'Medium'
            if kw['competition_index'] > 60:
                competition_level = 'High'
            
            await conn.execute("""
                INSERT INTO keywords (
                    keyword, category, jtbd_stage,
                    avg_monthly_searches, competition_level,
                    client_score, persona_score, seo_score,
                    composite_score, is_brand
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
                )
            """,
                kw['keyword'], kw['category'], kw['jtbd_stage'],
                kw['avg_monthly_searches'], competition_level,
                float(kw['client_score']), float(kw['persona_score']), float(kw['seo_score']),
                float(kw['composite_score']), kw['is_brand']
            )
            print(f"✓ Created keyword: {kw['keyword']} (score: {kw['composite_score']})")
        
        print(f"\n✓ Total keywords created: {len(KEYWORDS)}")

async def verify_setup():
    """Verify the setup."""
    print("\n=== Verifying Setup ===")
    
    async with db_pool.acquire() as conn:
        # Check company config
        config = await conn.fetchrow("SELECT * FROM client_config LIMIT 1")
        if config:
            print(f"✓ Company: {config['company_name']}")
            print(f"  - Legal name: {config['legal_name']}")
            print(f"  - Domains: {len(config.get('additional_domains', [])) + 1}")
            print(f"  - Competitors: {len(config.get('competitors', []))}")
        
        # Check analysis config
        analysis = await conn.fetchrow("SELECT * FROM analysis_config LIMIT 1")
        if analysis:
            personas = json.loads(analysis['personas']) if isinstance(analysis['personas'], str) else analysis['personas']
            print(f"✓ Personas: {len(personas)}")
            
            # Check JTBD phases
            jtbd_phases = json.loads(analysis['jtbd_phases']) if isinstance(analysis['jtbd_phases'], str) else analysis['jtbd_phases']
            if jtbd_phases:
                print(f"✓ JTBD Phases: {len(jtbd_phases)}")
        
        # Check custom dimensions
        dimension_count = await conn.fetchval("SELECT COUNT(*) FROM generic_custom_dimensions")
        print(f"✓ Custom Dimensions: {dimension_count}")
        
        # Check dimension groups if table exists
        dimension_groups_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = 'dimension_groups'
            )
        """)
        
        if dimension_groups_exists:
            groups = await conn.fetch("""
                SELECT dg.name, COUNT(dgm.dimension_id) as dimension_count
                FROM dimension_groups dg
                LEFT JOIN dimension_group_members dgm ON dg.id = dgm.group_id
                GROUP BY dg.id, dg.name
                ORDER BY dg.display_order
            """)
            if groups:
                print(f"✓ Dimension Groups: {len(groups)}")
                for group in groups:
                    print(f"  - {group['name']}: {group['dimension_count']} dimensions")
        
        # Check keywords
        keyword_count = await conn.fetchval("SELECT COUNT(*) FROM keywords")
        print(f"✓ Keywords: {keyword_count}")
        
        # Show top keywords
        top_keywords = await conn.fetch("""
            SELECT keyword, composite_score, category 
            FROM keywords 
            ORDER BY composite_score DESC 
            LIMIT 3
        """)
        if top_keywords:
            print("\nTop Keywords:")
            for kw in top_keywords:
                print(f"  - {kw['keyword']} (score: {kw['composite_score']}, category: {kw['category']})")

async def main():
    """Main setup function."""
    print("=== Finastra Project Data Setup ===")
    print(f"Started at: {datetime.utcnow().isoformat()}")
    
    try:
        await setup_database()
        await setup_company_config()
        await setup_personas()
        await setup_jtbd_phases()
        await setup_custom_dimensions()
        await setup_keywords()
        await verify_setup()
        
        print("\n✅ Setup completed successfully!")
        print("\nYou can now:")
        print("1. Visit http://localhost:3000 to see the frontend")
        print("2. Run a pipeline test with: docker exec -it cylvy-analyze-mkt-analysis-backend-1 python start_pipeline.py")
        
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_pool.close()

if __name__ == "__main__":
    asyncio.run(main())
