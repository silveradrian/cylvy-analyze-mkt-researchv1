"""
B2B Content/Page Type Dimension Configuration
"""
from typing import Dict, List
from app.models.generic_dimensions import GenericCustomDimension


# B2B Page Type Categories and Values
B2B_PAGE_TYPES = {
    "Core Website Pages": [
        "Homepage",
        "About / Company overview",
        "Contact / Get in touch",
        "Careers / Employer branding",
        "Newsroom / Press releases"
    ],
    "Solution & Offering Pages": [
        "Product pages",
        "Solution / Service pages",
        "Industry / Vertical pages",
        "Partner / Alliance pages",
        "Pricing pages"
    ],
    "Content Hubs & SEO Structures": [
        "Pillar pages",
        "Cluster pages",
        "Resource library / Content hub",
        "Knowledge base / Help center",
        "FAQ pages",
        "Glossaries / Terminology hubs"
    ],
    "Content Assets": [
        "Blog posts / Thought leadership articles",
        "Case studies / Customer stories",
        "Whitepapers",
        "eBooks / Guides",
        "Reports / Research studies",
        "Datasheets / One-pagers",
        "Infographics",
        "Checklists / Templates",
        "Buyer's guides / How-to guides",
        "Analyst reports / Reprints"
    ],
    "Multimedia & Interactive": [
        "Webinars (live & on-demand)",
        "Videos (explainer, demo, testimonial, thought leadership)",
        "Podcasts",
        "Interactive tools (ROI/TCO calculators, assessments, configurators)",
        "Virtual events / Expos"
    ],
    "Sales & Conversion-Focused": [
        "Landing pages (campaign/gated content)",
        "Demo request pages",
        "Comparison pages (vs. competitors, alternatives)",
        "Proposal / Quote request forms"
    ],
    "Trust & Authority": [
        "Customer testimonial pages",
        "Award / Recognition pages",
        "Security / Compliance trust centers",
        "ESG / CSR responsibility pages"
    ]
}


def get_page_type_dimension() -> GenericCustomDimension:
    """Create the B2B Content/Page Types dimension"""
    
    # Flatten all page types for signals
    all_page_types = []
    for category, types in B2B_PAGE_TYPES.items():
        all_page_types.extend(types)
    
    # Create category descriptions for AI context
    category_context = []
    for category, types in B2B_PAGE_TYPES.items():
        category_context.append(f"{category}: {', '.join(types[:3])}...")
    
    return GenericCustomDimension(
        dimension_id="b2b_page_type",
        name="B2B Content/Page Types",
        dimension_type="content_classification",
        description="Identifies the primary B2B content or page type based on structure, purpose, and content patterns",
        ai_context={
            "purpose": "Classify B2B content into standard page types for better content strategy insights",
            "scope": "B2B website pages and content assets",
            "key_focus_areas": [
                "Page structure and navigation patterns",
                "Content purpose and buyer journey stage",
                "Conversion elements and CTAs",
                "Content format and media type",
                "Trust signals and authority markers"
            ],
            "categories": category_context
        },
        criteria={
            "what_counts": "Primary page type based on dominant purpose and structure",
            "positive_signals": [
                # Core indicators for each category
                "Homepage indicators: hero sections, value propositions, main navigation",
                "Product page indicators: feature lists, pricing, demos, technical specs",
                "Content hub indicators: resource filtering, category navigation, download options",
                "Landing page indicators: form prominence, single CTA focus, limited navigation",
                "Case study indicators: customer quotes, results metrics, challenge-solution format",
                "Blog indicators: publication date, author info, related posts, comments",
                "Trust page indicators: certifications, awards, security badges, compliance info"
            ],
            "negative_signals": [
                "Unclear page purpose",
                "Mixed content types without clear primary focus",
                "Non-B2B content patterns"
            ],
            "exclusions": [
                "Consumer-focused pages",
                "Pure technical documentation",
                "Internal/admin pages"
            ]
        },
        scoring_framework={
            "levels": [
                {"range": [0, 3], "label": "Unclear", "description": "Page type not clearly identifiable"},
                {"range": [4, 6], "label": "Mixed", "description": "Multiple page types present"},
                {"range": [7, 8], "label": "Clear", "description": "Primary page type is evident"},
                {"range": [9, 10], "label": "Definitive", "description": "Textbook example of page type"}
            ],
            "evidence_requirements": {
                "min_indicators": 3,
                "structural_weight": 0.4,
                "content_weight": 0.4,
                "purpose_weight": 0.2
            }
        },
        metadata={
            "categories": list(B2B_PAGE_TYPES.keys()),
            "total_types": len(all_page_types),
            "default_dimension": True,
            "buyer_journey_alignment": {
                "awareness": ["Blog posts", "Reports", "Infographics", "Webinars"],
                "consideration": ["Solution pages", "Case studies", "Whitepapers", "Comparison pages"],
                "decision": ["Product pages", "Pricing pages", "Demo request", "ROI calculators"],
                "retention": ["Knowledge base", "Help center", "Customer testimonials"]
            }
        }
    )


def get_page_type_detection_prompt() -> str:
    """Get specialized prompt for page type detection"""
    return """
Analyze the content and identify the PRIMARY B2B page type. Consider:

1. **Page Structure**: Navigation, layout, sections, CTAs
2. **Content Purpose**: Information delivery, lead generation, trust building, conversion
3. **Content Format**: Article, product description, resource download, interactive tool
4. **Buyer Journey Stage**: Awareness, consideration, decision, retention
5. **Key Indicators**: Specific elements that define each page type

Categories and Types:
""" + "\n".join([f"\n**{cat}**:\n" + "\n".join([f"- {t}" for t in types]) for cat, types in B2B_PAGE_TYPES.items()]) + """

Return the SINGLE most appropriate page type based on the dominant purpose and structure.
If multiple types are present, choose the PRIMARY one based on main content focus.
"""

