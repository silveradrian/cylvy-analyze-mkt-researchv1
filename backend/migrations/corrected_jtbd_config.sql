-- ================================
-- CORRECTED JTBD PHASES CONFIGURATION
-- Fixed JSON syntax issues and complete detailed framework
-- ================================

UPDATE analysis_config SET jtbd_phases = '[
  {
    "name": "Problem Identification",
    "description": "Buyer is defining/recognizing a problem or opportunity. Content should help them name, frame, and understand urgency/impact.",
    "buyer_mindset": "Defining and recognizing problems or opportunities. Looking to name, frame, and understand urgency and business impact of current challenges.",
    "content_types": [
      "Problem framing content",
      "Industry trend reports",
      "Risk assessment frameworks", 
      "Quantified pain point analysis",
      "Industry driver analysis"
    ],
    "key_questions": [
      "What specific challenges do we face?",
      "How urgent is this problem?",
      "What is the business impact of inaction?",
      "How do industry trends affect us?",
      "What are the quantified costs of our current state?"
    ],
    "ai_context": {
      "purpose": "Help buyer define, recognize, and frame problems or opportunities with urgency and impact context",
      "positive_signals": ["Problem framing", "Industry trends", "Risk analysis", "Industry drivers", "Quantified pain points"],
      "negative_signals": ["Immediate product pitching", "Vendor-heavy language", "Jargon without context"],
      "exclusions": ["Generic thought leadership lacking tie to buyer operating context"]
    },
    "scoring_framework": {
      "min_words": 100,
      "word_increment": 80,
      "bonus_per_increment": 1,
      "required_elements": "At least one industry-specific or role-specific example",
      "levels": [
        {"score": 0, "description": "No mention of challenges/problems"},
        {"score_range": "1-3", "description": "Vague references (businesses face challenges) without specificity"},
        {"score_range": "4-6", "description": "Defines problem with some context (e.g., Healthcare organizations struggle with legacy EMR systems)"},
        {"score_range": "7-8", "description": "Uses evidence (data, industry insight, consequences of inaction)"},
        {"score_range": "9-10", "description": "Clear, specific, contextualized problem framing, quantified stakes, industry examples"}
      ],
      "contextual_rules": [
        {"condition": "shifts_to_solution_early", "adjustment": -2, "description": "Deduct if content shifts to solution/product too early"},
        {"condition": "generic_problem", "adjustment": -1, "description": "Deduct if problem is generic (e.g., businesses must innovate)"}
      ]
    }
  },
  {
    "name": "Solution Exploration", 
    "description": "Buyer is researching approaches to solve the problem. Content should explore categories/approaches, not just one product.",
    "buyer_mindset": "Researching different approaches to solve identified problems. Exploring solution categories and options rather than focusing on specific products.",
    "content_types": [
      "Solution category guides",
      "Approach comparison frameworks",
      "Benefits and risks analysis",
      "Technology option overviews", 
      "Implementation approach guides"
    ],
    "key_questions": [
      "What are the different approaches available?",
      "What are the pros and cons of each approach?",
      "Which solution categories fit our context?",
      "What are the trade-offs between options?",
      "How do other organizations approach this problem?"
    ],
    "ai_context": {
      "purpose": "Help buyer research and explore different approaches to solve problems, focusing on solution categories rather than specific products",
      "positive_signals": ["Explains solution types", "Compares approaches", "Outlines benefits/risks", "Multiple option analysis"],
      "negative_signals": ["Single vendor/product promotion only", "Biased toward one approach"],
      "exclusions": ["Content that restates problem without providing options"]
    },
    "scoring_framework": {
      "min_words": 120,
      "required_elements": "At least 2 distinct solution categories described, specific examples: tools, case examples, frameworks",
      "levels": [
        {"score": 0, "description": "No solutions discussed"},
        {"score_range": "1-3", "description": "Mentions a product vaguely without context"},
        {"score_range": "4-6", "description": "Identifies general solution categories (e.g., cloud migration vs. on-prem)"},
        {"score_range": "7-8", "description": "Provides pros/cons, trade-offs between approaches"},
        {"score_range": "9-10", "description": "Rich comparative analysis, contextualized for industry/role"}
      ],
      "contextual_rules": [
        {"condition": "skips_to_requirements", "adjustment": -2, "description": "Deduct if content skips to requirements/vendor capabilities without exploring categories"},
        {"condition": "single_vendor_focus", "adjustment": -1, "description": "Deduct if only vendors product mentioned as the solution"}
      ]
    }
  },
  {
    "name": "Requirements Building",
    "description": "Buyer is defining must-have features, specifications, and evaluation criteria.",
    "buyer_mindset": "Defining specific requirements, must-have features, and evaluation criteria. Building detailed specifications for solution selection.",
    "content_types": [
      "Requirements frameworks",
      "Specification guides", 
      "Evaluation criteria checklists",
      "Compliance and security requirements",
      "Performance indicator frameworks"
    ],
    "key_questions": [
      "What are our must-have requirements?",
      "How should we measure solution performance?",
      "What compliance and security criteria apply?",
      "What are industry-specific requirements?",
      "How do we create evaluation scorecards?"
    ],
    "ai_context": {
      "purpose": "Help buyer define detailed requirements, specifications, and evaluation criteria for solution selection",
      "positive_signals": ["Clear list of needs", "Performance indicators", "Compliance/security criteria", "Role/industry nuances"],
      "negative_signals": ["Marketing fluff without actionable detail", "Vague requirements"],
      "exclusions": ["Requirements that are vendor-skewed (must choose X vendor)"]
    },
    "scoring_framework": {
      "min_words": 150,
      "required_elements": "At least 3 distinct requirement categories (security, scalability, usability), measurable language (99.9% uptime not reliable)",
      "levels": [
        {"score": 0, "description": "No requirements"},
        {"score_range": "1-3", "description": "Vague (solution should be secure and easy to use)"},
        {"score_range": "4-6", "description": "Several requirements defined, partial detail"},
        {"score_range": "7-8", "description": "Detailed criteria with measurable or role-specific indicators"},
        {"score_range": "9-10", "description": "Robust requirements framework, industry benchmarks, scoring matrices, or checklists"}
      ],
      "contextual_rules": [
        {"condition": "veiled_product_features", "adjustment": -2, "description": "Deduct if requirements written as veiled product features"},
        {"condition": "single_dimension_focus", "adjustment": -1, "description": "Deduct if only one dimension (e.g., cost) covered"}
      ]
    }
  },
  {
    "name": "Supplier Selection",
    "description": "Buyer is narrowing down vendors, comparing, and evaluating supplier credibility.",
    "buyer_mindset": "Narrowing down vendor options, comparing suppliers, and evaluating credibility and fit. Looking for structured comparison approaches.",
    "content_types": [
      "Vendor comparison frameworks",
      "Evaluation checklists and rubrics",
      "Supplier credibility assessment",
      "ROI and TCO analysis guides",
      "Case studies and references"
    ],
    "key_questions": [
      "How do we compare vendors effectively?",
      "What evaluation criteria matter most?",
      "How do we assess supplier credibility?",
      "What are the ROI/TCO considerations?",
      "Where can we find independent validation?"
    ],
    "ai_context": {
      "purpose": "Help buyer systematically evaluate and compare vendors using structured frameworks and independent validation",
      "positive_signals": ["Comparison frameworks", "Evaluation checklists", "Case studies", "ROI/TCO discussions", "Independent references"],
      "negative_signals": ["We are the best style content without evidence", "Promotional content without substance"],
      "exclusions": ["Lists of vendors without context"]
    },
    "scoring_framework": {
      "min_words": 120,
      "required_elements": "At least 2 supplier selection factors (cost, support, security, integration), independent references for 8+ score",
      "levels": [
        {"score": 0, "description": "No vendor evaluation context"},
        {"score_range": "1-3", "description": "Mentions single supplier without comparison"},
        {"score_range": "4-6", "description": "Lists some selection factors but generic"},
        {"score_range": "7-8", "description": "Uses case studies, evaluation rubrics, industry references"},
        {"score_range": "9-10", "description": "Structured comparison, includes validation sources (analyst reports, third-party benchmarks)"}
      ],
      "contextual_rules": [
        {"condition": "overly_promotional", "adjustment": -2, "description": "Deduct for overly promotional content"},
        {"condition": "no_third_party_validation", "adjustment": -1, "description": "Deduct if no third-party validation present"}
      ]
    }
  },
  {
    "name": "Validation",
    "description": "Buyer seeks assurance they are making the right choice (proof, references, outcomes).",
    "buyer_mindset": "Seeking final assurance and validation for decision. Looking for proof points, references, and outcome evidence to confirm choice.",
    "content_types": [
      "Customer case studies",
      "Reference stories and testimonials", 
      "Compliance certifications",
      "Outcome metrics and ROI evidence",
      "Third-party analyst validation"
    ],
    "key_questions": [
      "What proof do we have this will work?",
      "Are there similar customer success stories?",
      "What certifications and compliance evidence exist?",
      "What are the quantified outcomes?",
      "What do independent analysts say?"
    ],
    "ai_context": {
      "purpose": "Provide buyer with concrete validation, proof points, and assurance for their decision through independent evidence",
      "positive_signals": ["Case studies", "Customer references", "Compliance certifications", "Outcome metrics", "Third-party validation"],
      "negative_signals": ["Aspirational marketing without proof", "Vague trust us messaging"],
      "exclusions": ["Coming soon or vague claims", "Vendor-only validation without independence"]
    },
    "scoring_framework": {
      "min_words": 100,
      "required_elements": "At least 1 independent validation asset (case study, analyst report), quantified outcomes needed for scores >7",
      "levels": [
        {"score": 0, "description": "No validation"},
        {"score_range": "1-3", "description": "Weak, generic claims (trusted by leading companies)"},
        {"score_range": "4-6", "description": "At least one case study or testimonial"},
        {"score_range": "7-8", "description": "Multiple forms of validation, with quantifiable outcomes"},
        {"score_range": "9-10", "description": "Rich validation (certifications, customer results, analyst references, ROI models)"}
      ],
      "contextual_rules": [
        {"condition": "vague_trust_messaging", "adjustment": -2, "description": "Deduct for vague trust us messaging"},
        {"condition": "vendor_only_validation", "adjustment": -1, "description": "Deduct if all validation is vendor-generated without third-party evidence"}
      ]
    }
  }
]'::jsonb WHERE id = (SELECT id FROM analysis_config LIMIT 1);

-- Verify the update
SELECT 
    'DETAILED JTBD CONFIGURATION COMPLETE' as status,
    jsonb_array_length(jtbd_phases) as phase_count,
    jsonb_path_query_array(jtbd_phases, '$[*].name') as phase_names,
    jsonb_path_query(jtbd_phases, '$[0].scoring_framework.min_words') as sample_min_words
FROM analysis_config 
LIMIT 1;
