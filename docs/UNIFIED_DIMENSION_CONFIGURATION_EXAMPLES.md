# Unified Dimension Configuration Examples

This document shows how ALL analysis dimensions (Personas, JTBD Phases, Custom Dimensions) are configured using the same advanced framework structure for consistency and fine-tuning capability.

## 1. Persona as Advanced Dimension

```json
{
  "dimension_id": "persona_technical_decision_maker",
  "name": "Persona Alignment: Technical Decision Maker",
  "description": "Alignment with Technical Decision Maker (VP Engineering/CTO)",
  "ai_context": {
    "general_description": "This dimension measures how well content aligns with the needs, goals, and decision-making criteria of the Technical Decision Maker persona",
    "purpose": "Evaluate content relevance and value for VP Engineering/CTO professionals who are responsible for technical strategy and architecture decisions",
    "scope": "All content types that could influence or inform this persona's technical decision-making process",
    "key_focus_areas": [
      "Addressing goals: Ensure technical scalability, Reduce technical debt, Improve team productivity",
      "Solving pain points: Legacy system integration, Resource constraints, Keeping up with technology changes",
      "Supporting decision criteria: Technical architecture fit, API quality, Security certifications",
      "Role in buying journey: Technical Evaluator",
      "Influence level: Medium - Strong Voice"
    ],
    "analysis_approach": "Evaluate how directly and effectively the content speaks to technical leadership concerns, architecture decisions, and engineering team needs"
  },
  "criteria": {
    "what_counts": "Content that directly addresses Technical Decision Maker's goals, challenges, and decision criteria",
    "positive_signals": [
      "Technical architecture discussions",
      "Scalability and performance metrics",
      "API documentation and integration details",
      "Security certifications and compliance",
      "Developer experience considerations",
      "Technical debt reduction strategies",
      "Team productivity improvements",
      "Integration with existing tech stack"
    ],
    "negative_signals": [
      "Non-technical marketing fluff",
      "Business-only content without technical depth",
      "Sales-focused messaging",
      "Content for end users or business buyers",
      "Lack of technical specifications"
    ],
    "exclusions": [
      "Pure business case studies without technical details",
      "End-user training materials",
      "Marketing campaigns without substance"
    ],
    "additional_context": "Consider the technical sophistication level expected by VP/CTO level professionals"
  },
  "scoring_framework": {
    "levels": [
      {
        "range": [0, 2],
        "label": "Poor Fit",
        "description": "Content not relevant to technical decision makers",
        "requirements": ["No technical depth", "Wrong audience", "Marketing focused"]
      },
      {
        "range": [3, 4],
        "label": "Weak Alignment",
        "description": "Some technical relevance but not targeted",
        "requirements": ["Basic technical mentions", "Generic content", "Limited depth"]
      },
      {
        "range": [5, 6],
        "label": "Moderate Alignment",
        "description": "Addresses some technical decision maker needs",
        "requirements": ["Some architecture discussion", "Basic technical specs", "Relevant examples"]
      },
      {
        "range": [7, 8],
        "label": "Strong Alignment",
        "description": "Well-targeted to technical leadership",
        "requirements": ["Deep technical content", "Architecture details", "Security focus", "Integration guidance"]
      },
      {
        "range": [9, 10],
        "label": "Perfect Fit",
        "description": "Exceptionally well-suited for technical decision makers",
        "requirements": ["Comprehensive technical depth", "Clear architecture benefits", "Strong security story", "Developer-first approach"]
      }
    ],
    "evidence_requirements": {
      "min_words": 120,
      "word_increment": 80,
      "max_score_per_increment": 1,
      "specificity_weight": 0.45
    },
    "contextual_rules": [
      {
        "name": "non_technical_penalty",
        "description": "Reduce score if content lacks technical depth",
        "condition": "non_technical",
        "adjustment_type": "penalty",
        "adjustment_value": 3
      },
      {
        "name": "sales_focus_cap",
        "description": "Cap score if overly sales-focused",
        "condition": "sales_heavy",
        "adjustment_type": "cap",
        "adjustment_value": 4
      }
    ]
  },
  "metadata": {
    "persona_type": "technical_buyer",
    "department": "Engineering/IT",
    "seniority": "VP/C-Level",
    "influence_level": "Medium - Strong Voice",
    "typical_concerns": ["scalability", "security", "integration", "team productivity"]
  }
}
```

## 2. JTBD Phase as Advanced Dimension

```json
{
  "dimension_id": "jtbd_phase_3_requirements",
  "name": "JTBD Phase 3: Requirements Building",
  "description": "Definition of specific needs and criteria",
  "ai_context": {
    "general_description": "This dimension evaluates how well content aligns with the 'Requirements Building' phase of the B2B buying journey, where buyers define their specific needs and evaluation criteria",
    "purpose": "Determine if content effectively serves buyers who are building their requirements and defining what they need in a solution",
    "scope": "All content types that help buyers understand and define their requirements",
    "key_focus_areas": [
      "Answering buyer questions: What do we need specifically? What are must-haves vs nice-to-haves? What's our criteria?",
      "Providing frameworks for requirements definition",
      "Helping buyers understand feature implications",
      "Guiding criteria development",
      "Supporting requirements documentation"
    ],
    "analysis_approach": "Look for content that helps buyers move from general solution awareness to specific requirements definition"
  },
  "criteria": {
    "what_counts": "Content that helps buyers define and document their specific requirements",
    "positive_signals": [
      "Requirements checklists",
      "Feature comparison frameworks",
      "Criteria definition guides",
      "Must-have vs nice-to-have discussions",
      "Specification templates",
      "Evaluation criteria examples",
      "Requirements gathering methodologies",
      "Feature deep-dives with use cases",
      "ROI calculation frameworks"
    ],
    "negative_signals": [
      "High-level problem discussion only",
      "Premature pricing information",
      "Vendor-specific features without context",
      "Pure marketing messages",
      "Implementation details too early"
    ],
    "exclusions": [
      "General awareness content",
      "Late-stage negotiation content",
      "Pure technical documentation without business context"
    ],
    "additional_context": "Phase 3 of 6 in the Gartner B2B buying journey - critical for moving from exploration to evaluation"
  },
  "scoring_framework": {
    "levels": [
      {
        "range": [0, 2],
        "label": "Wrong Phase",
        "description": "Content for different buying phase",
        "requirements": ["No requirements focus", "Wrong buyer stage", "Premature or late content"]
      },
      {
        "range": [3, 4],
        "label": "Weak Match",
        "description": "Some requirements relevance",
        "requirements": ["Minimal requirements content", "Generic feature lists", "Limited guidance"]
      },
      {
        "range": [5, 6],
        "label": "Moderate Match",
        "description": "Helps with requirements definition",
        "requirements": ["Some criteria guidance", "Basic requirements help", "Feature context"]
      },
      {
        "range": [7, 8],
        "label": "Strong Match",
        "description": "Excellent requirements building content",
        "requirements": ["Clear requirements framework", "Criteria examples", "Evaluation guides", "Use case mapping"]
      },
      {
        "range": [9, 10],
        "label": "Perfect Match",
        "description": "Ideal requirements building resource",
        "requirements": ["Comprehensive requirements toolkit", "Customizable frameworks", "Industry-specific criteria", "Clear next steps"]
      }
    ],
    "evidence_requirements": {
      "min_words": 150,
      "word_increment": 100,
      "max_score_per_increment": 1,
      "specificity_weight": 0.4
    },
    "contextual_rules": [
      {
        "name": "premature_vendor_pitch",
        "description": "Reduce score for premature vendor-specific content",
        "condition": "vendor_pitch",
        "adjustment_type": "penalty",
        "adjustment_value": 2
      },
      {
        "name": "wrong_phase_cap",
        "description": "Cap score if content is for wrong phase",
        "condition": "wrong_phase",
        "adjustment_type": "cap",
        "adjustment_value": 3
      }
    ]
  },
  "metadata": {
    "dimension_type": "jtbd_phase",
    "phase_number": 3,
    "phase_name": "Requirements Building",
    "gartner_framework": true,
    "typical_duration": "4-8 weeks",
    "key_stakeholders": ["technical evaluators", "business analysts", "procurement"]
  }
}
```

## 3. Custom Dimension (Cloud Maturity) as Advanced Dimension

```json
{
  "dimension_id": "custom_cloud_maturity",
  "name": "Cloud Architecture Maturity",
  "description": "Evaluates the depth and sophistication of cloud architecture capabilities",
  "ai_context": {
    "general_description": "This dimension assesses how well an organization demonstrates mature cloud architecture capabilities, from basic cloud adoption to advanced multi-cloud strategies",
    "purpose": "Distinguish between surface-level cloud claims and genuine cloud architecture expertise that indicates a mature, scalable platform",
    "scope": "Technical content, architecture documentation, case studies, and any content discussing cloud infrastructure and capabilities",
    "key_focus_areas": [
      "Multi-cloud and hybrid cloud capabilities",
      "Cloud-native architecture patterns",
      "Scalability and elasticity demonstrations",
      "Security and compliance in cloud environments",
      "Cost optimization strategies",
      "Disaster recovery and business continuity",
      "Performance metrics and SLAs",
      "Migration strategies and tools"
    ],
    "analysis_approach": "Look for specific technical details, certifications, architectural patterns, and real-world performance metrics rather than generic cloud marketing"
  },
  "criteria": {
    "what_counts": "Concrete evidence of sophisticated cloud architecture and operational excellence",
    "positive_signals": [
      "Multi-cloud platform support (AWS, Azure, GCP)",
      "Cloud certifications mentioned",
      "Specific architectural patterns (microservices, serverless, containers)",
      "Auto-scaling capabilities with metrics",
      "Multi-region deployment options",
      "Cloud security certifications (SOC2, ISO27001 for cloud)",
      "Performance SLAs with specific numbers",
      "Cost optimization features",
      "Infrastructure as Code practices",
      "Cloud-native development practices",
      "Disaster recovery metrics (RTO/RPO)",
      "Compliance frameworks for cloud"
    ],
    "negative_signals": [
      "Generic 'cloud-based' claims without details",
      "Single cloud vendor lock-in",
      "No mention of scalability specifics",
      "Missing security certifications",
      "No performance metrics",
      "Outdated architecture patterns",
      "No multi-tenancy discussion"
    ],
    "exclusions": [
      "On-premise only solutions",
      "Desktop software without cloud components",
      "Generic business benefits without technical backing"
    ],
    "additional_context": "Focus on technical depth and operational maturity rather than marketing claims"
  },
  "scoring_framework": {
    "levels": [
      {
        "range": [0, 2],
        "label": "Basic/Legacy",
        "description": "Minimal or legacy cloud adoption",
        "requirements": ["Basic cloud hosting only", "No cloud-native features", "Single region", "Limited scalability"]
      },
      {
        "range": [3, 4],
        "label": "Cloud-Enabled",
        "description": "Basic cloud deployment with limited features",
        "requirements": ["Single cloud provider", "Basic auto-scaling", "Standard security", "Regional presence"]
      },
      {
        "range": [5, 6],
        "label": "Cloud-Optimized",
        "description": "Good cloud practices with room for growth",
        "requirements": ["Multi-region support", "Container-based", "Good security practices", "Performance monitoring"]
      },
      {
        "range": [7, 8],
        "label": "Cloud-Native",
        "description": "Strong cloud architecture with modern practices",
        "requirements": ["Multi-cloud capable", "Microservices architecture", "Advanced security", "Global scale", "IaC practices"]
      },
      {
        "range": [9, 10],
        "label": "Cloud Leader",
        "description": "Best-in-class cloud architecture and operations",
        "requirements": ["Multi-cloud excellence", "Serverless options", "Zero-trust security", "Global edge presence", "Cost optimization AI"]
      }
    ],
    "evidence_requirements": {
      "min_words": 100,
      "word_increment": 75,
      "max_score_per_increment": 1,
      "specificity_weight": 0.5
    },
    "contextual_rules": [
      {
        "name": "no_technical_details",
        "description": "Cap score if no specific technical details provided",
        "condition": "no_technical_details",
        "adjustment_type": "cap",
        "adjustment_value": 4
      },
      {
        "name": "security_bonus",
        "description": "Bonus for strong security certifications",
        "condition": "strong_security",
        "adjustment_type": "bonus",
        "adjustment_value": 1
      },
      {
        "name": "multi_cloud_bonus",
        "description": "Bonus for true multi-cloud capabilities",
        "condition": "multi_cloud",
        "adjustment_type": "bonus",
        "adjustment_value": 1
      }
    ]
  },
  "metadata": {
    "dimension_type": "custom",
    "category": "technical_capability",
    "importance": "high",
    "industry_relevance": ["saas", "paas", "enterprise_software"],
    "evaluation_frequency": "quarterly"
  }
}
```

## Key Benefits of Unified Structure

### 1. **Consistency Across All Dimensions**
- Every dimension (persona, JTBD, custom) follows the same structure
- AI receives consistent context and scoring frameworks
- Easier to train and fine-tune AI models

### 2. **Rich AI Context**
- `ai_context` provides comprehensive understanding
- Clear purpose and analysis approach
- Key focus areas guide attention

### 3. **Flexible Criteria System**
- `what_counts` clearly defines scope
- Positive/negative signals are explicit
- Exclusions prevent false positives

### 4. **Advanced Scoring Framework**
- Multi-level scoring with clear requirements
- Evidence-based adjustments
- Contextual rules for nuanced scoring

### 5. **Metadata for Intelligence**
- Dimension type classification
- Additional context for analysis
- Support for fine-tuning and optimization

## Configuration Best Practices

1. **AI Context is Critical**
   - Provide rich `general_description`
   - Clear `purpose` statement
   - Specific `key_focus_areas`
   - Actionable `analysis_approach`

2. **Criteria Should Be Specific**
   - Use concrete examples in signals
   - Include industry-specific terminology
   - Balance positive and negative signals

3. **Scoring Levels Need Clear Boundaries**
   - Each level should be distinctly different
   - Requirements should be measurable
   - Avoid overlap between levels

4. **Evidence Requirements Drive Quality**
   - Set appropriate word minimums
   - Higher specificity weight for technical dimensions
   - Adjust increments based on content type

5. **Contextual Rules Add Nuance**
   - Use caps for hard limits
   - Apply penalties for anti-patterns
   - Give bonuses for excellence indicators

## Implementation Checklist

- [ ] Convert all personas to advanced dimension format
- [ ] Convert all JTBD phases to advanced dimension format  
- [ ] Update existing custom dimensions to advanced format
- [ ] Validate all dimensions have complete ai_context
- [ ] Ensure scoring frameworks are consistent
- [ ] Test with sample content
- [ ] Monitor AI performance and adjust
- [ ] Implement fine-tuning based on results

This unified structure enables sophisticated AI analysis and continuous improvement through fine-tuning based on analysis outputs.
