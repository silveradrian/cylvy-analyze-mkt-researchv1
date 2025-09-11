# Advanced Custom Dimensions Feature

## Overview

This feature extends the existing custom dimensions system to support **completely generic, criteria-based analysis dimensions** with sophisticated scoring methodologies. The system is **dimension-agnostic** and can handle any type of custom analysis framework without hardcoded logic.

## 🎯 Feature Requirements

### Current vs. New System

| Current System | New Advanced System |
|---|---|
| Simple key-value pairs | Generic criteria-based dimensions |
| Predefined option lists | Flexible scoring criteria |
| Basic confidence scoring | Evidence-based scoring (0-10) |
| Generic prompts | Dynamic criterion-specific prompts |

### New Capabilities

1. **Complete Flexibility**: No hardcoded dimension types or categories
2. **Evidence-Based Scoring**: Configurable word count thresholds and content depth analysis  
3. **Dynamic Contextual Rules**: Client-configurable scoring adjustments
4. **Flexible Criteria**: Configurable "what counts", signals, and exclusions per dimension
5. **Generic Scoring Logic**: Multi-factor scoring with configurable rules

---

## 📊 Data Structure Requirements

### 1. Generic Dimension Configuration

```typescript
interface GenericCustomDimension {
  id: string;
  name: string;
  description: string;
  
  // Overall AI context for this dimension
  ai_context: {
    general_description: string;
    purpose: string;
    scope: string;
    key_focus_areas: string[];
    analysis_approach?: string;
  };
  
  // Flexible criteria structure
  criteria: {
    what_counts: string;
    positive_signals: string[];
    negative_signals: string[];
    exclusions: string[];
    additional_context?: string;
  };
  
  // Configurable scoring framework
  scoring_framework: {
    levels: ScoringLevel[];
    evidence_requirements: EvidenceConfig;
    contextual_rules: ContextualRule[];
  };
  
  // Client-specific metadata
  metadata?: Record<string, any>;
}

interface ScoringLevel {
  range: [number, number]; // e.g., [0, 2]
  label: string;
  description: string;
  requirements: string[];
}

interface EvidenceConfig {
  min_words: number;
  word_increment: number;
  max_score_per_increment: number;
  specificity_weight?: number;
}

interface ContextualRule {
  name: string;
  description: string;
  condition: string; // e.g., "off_topic", "competitor_focused", "generic_language"
  adjustment_type: "cap" | "penalty" | "bonus";
  adjustment_value: number;
}
```

### 2. Generic Analysis Result Structure

```typescript
interface GenericDimensionAnalysis {
  dimension_id: string;
  final_score: number; // 0-10
  evidence_summary: string;
  
  // Evidence analysis (configurable based on dimension requirements)
  evidence_analysis: {
    total_relevant_words: number;
    evidence_threshold_met: boolean;
    specificity_score: number; // 0-10
    quality_indicators: Record<string, number>; // Flexible quality metrics
  };
  
  // Flexible scoring breakdown
  scoring_breakdown: {
    base_score: number;
    evidence_adjustments: Record<string, number>; // Dynamic adjustments
    contextual_adjustments: Record<string, number>; // Rule-based adjustments
    scoring_rationale: string;
  };
  
  confidence_score: number; // 0-10
  detailed_reasoning: string;
  matched_criteria: string[]; // Which criteria were found in content
  
  // Extensible metadata
  analysis_metadata?: Record<string, any>;
}
```

---

## 🗃️ Database Schema Updates

### 1. New Tables

```sql
-- Generic custom dimensions configuration (completely dimension-agnostic)
CREATE TABLE generic_custom_dimensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id VARCHAR(100) NOT NULL,
    dimension_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- AI context for overall understanding (stored as JSONB)
    ai_context JSONB NOT NULL, -- general_description, purpose, scope, key_focus_areas, analysis_approach
    
    -- Flexible criteria structure (stored as JSONB for complete flexibility)
    criteria JSONB NOT NULL, -- what_counts, positive_signals, negative_signals, exclusions
    
    -- Configurable scoring framework
    scoring_framework JSONB NOT NULL, -- levels, evidence_requirements, contextual_rules
    
    -- Client-specific metadata (completely open-ended)
    metadata JSONB DEFAULT '{}',
    
    -- System metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(client_id, dimension_id)
);

-- Generic analysis results (no hardcoded fields)
CREATE TABLE generic_dimension_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_analysis_id UUID NOT NULL REFERENCES content_analysis(id),
    dimension_id VARCHAR(100) NOT NULL,
    
    -- Core analysis result
    final_score INTEGER NOT NULL CHECK (final_score >= 0 AND final_score <= 10),
    evidence_summary TEXT,
    
    -- Flexible evidence analysis (structure defined by dimension config)
    evidence_analysis JSONB DEFAULT '{}',
    
    -- Dynamic scoring breakdown (accommodates any scoring logic)
    scoring_breakdown JSONB DEFAULT '{}',
    
    -- AI outputs
    confidence_score INTEGER DEFAULT 0 CHECK (confidence_score >= 0 AND confidence_score <= 10),
    detailed_reasoning TEXT,
    matched_criteria JSONB DEFAULT '[]', -- Array of matched criteria
    
    -- Extensible analysis metadata
    analysis_metadata JSONB DEFAULT '{}',
    
    -- System metadata
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_used VARCHAR(100),
    analysis_version VARCHAR(20) DEFAULT '3.0',
    
    INDEX(content_analysis_id),
    INDEX(dimension_id),
    INDEX(final_score)
);
```

### 2. Migration Scripts

```sql
-- Migration: Add generic dimensions support to existing tables
ALTER TABLE client_analysis_config 
ADD COLUMN generic_dimensions_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN generic_dimensions_config JSONB DEFAULT '{}';

-- Migration: Update content_analysis table
ALTER TABLE content_analysis 
ADD COLUMN generic_dimension_scores JSONB DEFAULT '{}',
ADD COLUMN evidence_analysis JSONB DEFAULT '{}';
```

---

## 🔧 API Changes

### 1. Generic Configuration Endpoints

```http
# Create/Update any custom dimension (completely flexible structure)
POST /api/clients/{client_id}/generic-dimensions
PUT /api/clients/{client_id}/generic-dimensions/{dimension_id}

{
  "dimension_id": "any_custom_dimension_name",
  "name": "Any Custom Dimension Name",
  "description": "Description of what this dimension measures",
  "ai_context": {
    "general_description": "This dimension measures the organization's ability to demonstrate expertise, thought leadership, and practical value in their domain of focus.",
    "purpose": "Evaluate content for depth of knowledge, practical application, and industry recognition",
    "scope": "All content types including articles, whitepapers, case studies, and technical documentation",
    "key_focus_areas": [
      "Technical depth and accuracy",
      "Real-world implementation examples", 
      "Industry best practices and standards",
      "Quantifiable outcomes and results",
      "Thought leadership and innovation"
    ],
    "analysis_approach": "Look for concrete evidence of expertise through specific examples, technical details, industry terminology, and demonstrated results. Prioritize substance over marketing language."
  },
  "criteria": {
    "what_counts": "Define what evidence should be considered...",
    "positive_signals": [
      "Signal 1 that indicates high score",
      "Signal 2 that indicates presence"
    ],
    "negative_signals": [
      "Signal that indicates low score",
      "Signal that indicates absence"
    ],
    "exclusions": [
      "Content that should be excluded from analysis"
    ],
    "additional_context": "Any additional context for analysis"
  },
  "scoring_framework": {
    "levels": [
      {
        "range": [0, 2],
        "label": "Minimal",
        "description": "Low evidence or presence",
        "requirements": ["Requirement 1", "Requirement 2"]
      },
      {
        "range": [9, 10], 
        "label": "Exceptional",
        "description": "Strong evidence and comprehensive presence",
        "requirements": ["Advanced requirement", "Excellence indicator"]
      }
    ],
    "evidence_requirements": {
      "min_words": 120,
      "word_increment": 80,
      "max_score_per_increment": 1,
      "specificity_weight": 0.3
    },
    "contextual_rules": [
      {
        "name": "off_topic_penalty",
        "description": "Penalize content not directly related to this dimension",
        "condition": "off_topic",
        "adjustment_type": "cap",
        "adjustment_value": 2
      }
    ]
  },
  "metadata": {
    "client_specific_field": "Any client-specific data",
    "tags": ["tag1", "tag2"],
    "priority": "high"
  }
}
```

### 2. Analysis Request Enhancement

```http
# Generic content analysis request (works with any dimension configuration)
POST /api/content-analysis/analyze

{
  "client_id": "any-client-id",
  "url": "https://example.com/content",
  "analysis_type": "generic_dimensions", // NEW: triggers generic dimensions analysis
  "dimension_filters": ["dimension_id_1", "dimension_id_2"] // Optional: analyze specific dimensions only
}
```

### 3. Generic Results Endpoint

```http
# Get generic dimension analysis results (structure adapts to configured dimensions)
GET /api/content-analysis/results/{analysis_id}/generic-dimensions

{
  "analysis_id": "uuid",
  "url": "https://example.com/content", 
  "generic_dimensions": {
    "any_dimension_id": {
      "final_score": 7,
      "evidence_summary": "Contextual summary based on dimension criteria...",
      "evidence_analysis": {
        "total_relevant_words": 245,
        "evidence_threshold_met": true,
        "specificity_score": 8,
        "quality_indicators": {
          "depth_score": 7,
          "relevance_score": 8,
          "specificity_score": 6
        }
      },
      "scoring_breakdown": {
        "base_score": 6,
        "evidence_adjustments": {
          "word_count_bonus": 2,
          "specificity_bonus": 1
        },
        "contextual_adjustments": {
          "off_topic_penalty": 0,
          "generic_language_penalty": -2
        },
        "scoring_rationale": "Score based on configured criteria and evidence analysis"
      },
      "confidence_score": 8,
      "detailed_reasoning": "Analysis reasoning based on matched criteria...",
      "matched_criteria": [
        "positive_signal_1",
        "positive_signal_3",
        "evidence_requirement_2"
      ],
      "analysis_metadata": {
        "processing_time_ms": 1250,
        "criteria_matches": 5,
        "custom_metrics": {}
      }
    }
  }
}
```

---

## 🤖 AI Processing Changes

### 1. Dynamic Prompt Engineering (Completely Generic)

```python
# Generic prompt builder that works with any dimension configuration
def build_generic_dimension_prompt(content: str, dimensions: List[GenericCustomDimension]) -> str:
    prompt_sections = []
    
    for dimension in dimensions:
        # Build dimension-specific section dynamically from configuration
        section = f"""
## ANALYZE: {dimension.name} (Score 0-10)

**AI Context & Overall Understanding**:
{build_ai_context_section(dimension.ai_context)}

**Description**: {dimension.description}

**What Counts**: {dimension.criteria['what_counts']}

**Positive Signals**: {', '.join(dimension.criteria['positive_signals'])}

**Negative Signals**: {', '.join(dimension.criteria['negative_signals'])}

**Exclusions**: {', '.join(dimension.criteria['exclusions'])}

{build_additional_context(dimension.criteria)}

**Scoring Framework**:
{build_dynamic_scoring_guidance(dimension.scoring_framework['levels'])}

**Evidence Requirements**: 
{build_evidence_requirements(dimension.scoring_framework['evidence_requirements'])}

**Contextual Rules**:
{build_contextual_rules(dimension.scoring_framework['contextual_rules'])}

{build_metadata_instructions(dimension.metadata)}
"""
        prompt_sections.append(section)
    
    return build_complete_prompt(content, prompt_sections)

def build_ai_context_section(ai_context: dict) -> str:
    """Build AI context section to provide overall understanding of the dimension"""
    context_text = f"""
**General Description**: {ai_context['general_description']}

**Purpose**: {ai_context['purpose']}

**Scope**: {ai_context['scope']}

**Key Focus Areas**:
{chr(10).join([f"- {area}" for area in ai_context['key_focus_areas']])}

**Analysis Approach**: {ai_context.get('analysis_approach', 'Apply standard analysis methodology')}

---
**IMPORTANT**: Before analyzing the specific criteria below, consider this overall context to understand what this dimension is fundamentally measuring and how to approach the analysis.
---
"""
    return context_text

def build_dynamic_scoring_guidance(levels: List[ScoringLevel]) -> str:
    """Dynamically build scoring guidance from any configuration"""
    guidance = []
    for level in levels:
        score_range = f"{level['range'][0]}-{level['range'][1]}"
        requirements = '; '.join(level['requirements'])
        guidance.append(f"- **{score_range} ({level['label']})**: {level['description']} - {requirements}")
    return '\n'.join(guidance)

def build_contextual_rules(rules: List[ContextualRule]) -> str:
    """Dynamically build contextual rules from any configuration"""
    rule_text = []
    for rule in rules:
        rule_text.append(f"- **{rule['name']}**: {rule['description']} ({rule['adjustment_type']}: {rule['adjustment_value']})")
    return '\n'.join(rule_text)
    
def build_evidence_requirements(evidence_config: EvidenceConfig) -> str:
    """Build evidence requirements dynamically"""
    return f"""
- Minimum {evidence_config['min_words']} relevant words for meaningful analysis
- Each additional {evidence_config['word_increment']} words can improve score by up to +{evidence_config['max_score_per_increment']} point(s)
- Specificity weighting: {evidence_config.get('specificity_weight', 'standard')}
"""
```

### 2. Dynamic Response Schema (Generated from Dimension Configurations)

```python
def build_generic_analysis_schema(dimensions: List[GenericCustomDimension]) -> dict:
    """Build OpenAI function schema dynamically based on configured dimensions"""
    
    # Base schema structure that works with any dimension configuration
    base_schema = {
        "type": "object",
        "properties": {
            "generic_dimensions": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "final_score": {"type": "integer", "minimum": 0, "maximum": 10},
                        "evidence_summary": {"type": "string"},
                        "evidence_analysis": {
                            "type": "object",
                            "properties": {
                                "total_relevant_words": {"type": "integer"},
                                "evidence_threshold_met": {"type": "boolean"},
                                "specificity_score": {"type": "integer", "minimum": 0, "maximum": 10},
                                "quality_indicators": {
                                    "type": "object",
                                    "additionalProperties": {"type": "number", "minimum": 0, "maximum": 10}
                                }
                            }
                        },
                        "scoring_breakdown": {
                            "type": "object",
                            "properties": {
                                "base_score": {"type": "integer"},
                                "evidence_adjustments": {
                                    "type": "object",
                                    "additionalProperties": {"type": "number"}
                                },
                                "contextual_adjustments": {
                                    "type": "object", 
                                    "additionalProperties": {"type": "number"}
                                },
                                "scoring_rationale": {"type": "string"}
                            }
                        },
                        "confidence_score": {"type": "integer", "minimum": 0, "maximum": 10},
                        "detailed_reasoning": {"type": "string"},
                        "matched_criteria": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "analysis_metadata": {
                            "type": "object",
                            "additionalProperties": True  # Completely flexible metadata
                        }
                    },
                    "required": ["final_score", "evidence_summary", "confidence_score", "detailed_reasoning"]
                }
            }
        },
        "required": ["generic_dimensions"]
    }
    
    # Schema adapts to any dimension configuration - no hardcoded dimension-specific logic
    return base_schema

# Example usage - works with any dimension configuration:
schema = build_generic_analysis_schema(client_dimensions)
```

### 3. Example Generated AI Prompt (with AI Context)

Here's what the AI would receive when analyzing content with the above configuration:

```
## ANALYZE: Domain Expertise Demonstration (Score 0-10)

**AI Context & Overall Understanding**:

**General Description**: This dimension evaluates how well an organization demonstrates genuine expertise, thought leadership, and practical competence in their specific domain or industry vertical.

**Purpose**: Distinguish between surface-level marketing content and content that demonstrates deep, authentic expertise that would be valued by industry professionals and potential customers

**Scope**: All forms of content including technical documentation, thought leadership pieces, case studies, whitepapers, blog posts, and educational materials

**Key Focus Areas**:
- Technical accuracy and depth of knowledge
- Use of industry-specific terminology and concepts
- Reference to recognized standards, frameworks, and best practices
- Concrete examples from real implementations or experiences
- Quantifiable results and measurable outcomes
- Recognition of nuances, challenges, and trade-offs in the domain
- Forward-thinking perspectives and innovation

**Analysis Approach**: Look beyond marketing language to find substance. Prioritize specific, verifiable details over generic claims. Consider whether the content would be respected by domain experts and whether it provides actionable insights that demonstrate genuine understanding.

---
**IMPORTANT**: Before analyzing the specific criteria below, consider this overall context to understand what this dimension is fundamentally measuring and how to approach the analysis.
---

**What Counts**: Evidence of deep domain knowledge, practical experience, and thought leadership that would be recognized as valuable by industry experts and knowledgeable practitioners

**Positive Signals**: Technical depth indicators and specific implementation details, Real-world implementation examples with context and outcomes, Proper use of industry-specific terminology and frameworks...

[... rest of criteria and scoring framework ...]
```

This comprehensive context helps the AI understand:
1. **The big picture** of what the dimension measures
2. **The quality bar** for evaluation 
3. **The mindset** to adopt when analyzing content
4. **The focus areas** to pay attention to
5. **The approach** to take when making judgments

---

## 🚀 Implementation Plan

### Phase 1: Generic Database & Models (Week 1-2)
1. Create completely generic database tables with JSONB fields
2. Update existing models to support flexible dimension structures
3. Create migration scripts with backward compatibility
4. Add generic Pydantic models with dynamic validation

### Phase 2: Configuration Management (Week 2-3)
1. Build generic dimension configuration APIs (no hardcoded fields)
2. Create admin UI for any dimension type management
3. Add flexible validation logic based on configuration
4. Implement import/export for any dimension structure

### Phase 3: Dynamic AI Processing (Week 3-4)
1. Enhance ContentAnalyzer with generic dimension processing
2. Implement dynamic prompt generation from any configuration
3. Create flexible scoring logic engine
4. Add configurable evidence analysis framework

### Phase 4: Generic APIs & Results (Week 4-5)
1. Update analysis APIs to handle any dimension structure
2. Create generic results endpoints with flexible response formats
3. Add filtering and search for any dimension type
4. Implement caching for any analysis configuration

### Phase 5: Flexible Frontend (Week 5-6)
1. Create dynamic analysis results UI that adapts to any dimension
2. Build generic dimension configuration interface
3. Implement flexible scoring visualization
4. Add export functionality for any dimension structure

---

## 🔍 Testing Strategy

### 1. Unit Tests
```python
# Example test structure
def test_advanced_dimension_scoring():
    analyzer = AdvancedContentAnalyzer()
    content = "Sample content with customer advisory boards..."
    dimension = load_customer_obsession_dimension()
    
    result = analyzer.analyze_dimension(content, dimension)
    
    assert result.selected_score == 7
    assert result.evidence_summary is not None
    assert result.word_count_analysis.evidence_threshold_met is True
```

### 2. Integration Tests
- End-to-end analysis pipeline
- API request/response validation  
- Database persistence verification
- AI model response validation

### 3. Performance Tests
- Large content analysis (10K+ words)
- Multiple dimension analysis
- Concurrent request handling
- Cache effectiveness

---

## ⚠️ Migration Considerations

### 1. Backward Compatibility
- Existing simple custom dimensions continue working
- New `advanced_dimensions_enabled` flag controls feature activation
- Graceful fallback for clients not using advanced features

### 2. Data Migration
```python
# Migration script pseudocode
def migrate_existing_custom_dimensions():
    for client in get_clients_with_custom_dimensions():
        # Convert simple dimensions to basic advanced format
        for dim_name, options in client.custom_dimensions.items():
            create_basic_advanced_dimension(
                client_id=client.id,
                name=dim_name,
                options=options,
                scoring_type='simple'  # Legacy mode
            )
```

### 3. Feature Rollout
1. **Alpha**: Internal testing with sample dimensions
2. **Beta**: Select client testing with Finastra dimensions  
3. **GA**: Full rollout with migration tools

---

## 📋 Generic Configuration Examples

### Example 1: Any Domain-Specific Dimension
```json
{
  "dimension_id": "custom_expertise_area",
  "name": "Domain Expertise Demonstration", 
  "description": "Measures depth of expertise in a specific domain",
  "ai_context": {
    "general_description": "This dimension evaluates how well an organization demonstrates genuine expertise, thought leadership, and practical competence in their specific domain or industry vertical.",
    "purpose": "Distinguish between surface-level marketing content and content that demonstrates deep, authentic expertise that would be valued by industry professionals and potential customers",
    "scope": "All forms of content including technical documentation, thought leadership pieces, case studies, whitepapers, blog posts, and educational materials",
    "key_focus_areas": [
      "Technical accuracy and depth of knowledge",
      "Use of industry-specific terminology and concepts",
      "Reference to recognized standards, frameworks, and best practices", 
      "Concrete examples from real implementations or experiences",
      "Quantifiable results and measurable outcomes",
      "Recognition of nuances, challenges, and trade-offs in the domain",
      "Forward-thinking perspectives and innovation"
    ],
    "analysis_approach": "Look beyond marketing language to find substance. Prioritize specific, verifiable details over generic claims. Consider whether the content would be respected by domain experts and whether it provides actionable insights that demonstrate genuine understanding."
  },
  "criteria": {
    "what_counts": "Evidence of deep domain knowledge, practical experience, and thought leadership that would be recognized as valuable by industry experts and knowledgeable practitioners",
    "positive_signals": [
      "Technical depth indicators and specific implementation details",
      "Real-world implementation examples with context and outcomes", 
      "Proper use of industry-specific terminology and frameworks",
      "Reference to recognized standards, methodologies, and best practices",
      "Quantified outcomes and measurable business results",
      "Discussion of challenges, trade-offs, and lessons learned",
      "Forward-thinking perspectives and innovative approaches"
    ],
    "negative_signals": [
      "Generic marketing language without specific substance",
      "Vague claims without supporting evidence or details",
      "Surface-level treatment that lacks depth or nuance",
      "Misuse of technical terminology or industry concepts",
      "Pure feature lists without context or application guidance"
    ],
    "exclusions": [
      "Pure promotional content without technical or practical substance",
      "Content focused solely on company achievements without domain insights",
      "Generic business advice that could apply to any industry"
    ],
    "additional_context": "Focus on actionable insights, practical guidance, and evidence of deep understanding that would be valuable to domain practitioners"
  },
  "scoring_framework": {
    "levels": [
      {
        "range": [0, 2],
        "label": "Minimal",
        "description": "Generic language; no deep expertise demonstrated",
        "requirements": ["Basic mentions only", "No specific examples", "Marketing-focused content"]
      },
      {
        "range": [3, 4],
        "label": "Basic",
        "description": "Some domain knowledge with limited depth",
        "requirements": ["Basic technical concepts", "Limited specific examples", "Some industry terminology"]
      },
      {
        "range": [5, 6],
        "label": "Moderate",
        "description": "Clear domain knowledge with practical insights",
        "requirements": ["Multiple specific examples", "Technical depth", "Practical applications"]
      },
      {
        "range": [7, 8],
        "label": "Strong",
        "description": "Clear expertise with specific examples and outcomes",
        "requirements": ["Specific examples", "Quantified results", "Technical depth", "Industry recognition"]
      },
      {
        "range": [9, 10],
        "label": "Exceptional", 
        "description": "Comprehensive expertise with multiple validated outcomes and innovation",
        "requirements": ["Multiple detailed examples", "Industry leadership", "Innovation demonstrated", "Recognized thought leadership"]
      }
    ],
    "evidence_requirements": {
      "min_words": 120,
      "word_increment": 80,
      "max_score_per_increment": 1,
      "specificity_weight": 0.4
    },
    "contextual_rules": [
      {
        "name": "off_topic_cap",
        "description": "Cap score when content is not directly related to the domain",
        "condition": "off_topic",
        "adjustment_type": "cap",
        "adjustment_value": 2
      },
      {
        "name": "marketing_heavy_penalty",
        "description": "Reduce score for content that is primarily marketing-focused",
        "condition": "marketing_heavy",
        "adjustment_type": "penalty",
        "adjustment_value": 3
      }
    ]
  },
  "metadata": {
    "domain": "any_domain",
    "priority": "high",
    "review_required": false,
    "expertise_type": "technical_and_business"
  }
}
```

---

## 🔧 Developer Setup

### 1. Environment Variables
```bash
# Add to .env
GENERIC_DIMENSIONS_ENABLED=true
OPENAI_MODEL_GENERIC_ANALYSIS="gpt-4.1-2025-04-14"
EVIDENCE_ANALYSIS_TIMEOUT=45
MAX_DIMENSIONS_PER_ANALYSIS=20  # Flexible limit
DYNAMIC_PROMPT_MAX_LENGTH=16000
```

### 2. Dependencies
```bash
# Backend requirements.txt additions
textstat==0.7.3  # Text readability analysis  
spacy>=3.4.0     # NLP for word counting
transformers     # For advanced text analysis
jsonschema       # For dynamic configuration validation
```

### 3. Database Setup
```bash
# Run migrations
python -m alembic upgrade head

# Initialize with client-specific dimensions (completely configurable)
python scripts/init_client_dimensions.py --client-id={any_client} --config-file={any_dimension_config.json}
```

## 🎯 Key Benefits of Generic Approach

### **Complete Flexibility**
- **Zero Hardcoded Logic**: System works with any dimension configuration
- **Dynamic Adaptation**: AI prompts, schemas, and processing adapt to any criteria
- **Unlimited Scalability**: Support any number of dimensions with any complexity

### **Client Agnostic**
- **Multi-Tenant Ready**: Each client can define completely different dimensions
- **Industry Agnostic**: Works for finance, healthcare, technology, or any domain
- **Use Case Flexible**: Supports any analysis framework or methodology

### **Future-Proof Architecture**
- **No Code Changes**: New dimensions added through configuration only
- **Extensible Metadata**: Unlimited custom fields and properties
- **API Stable**: Core APIs remain unchanged regardless of dimension complexity

### **Enhanced AI Context Benefits**
- **Better Analysis Quality**: AI understands the big picture before diving into details
- **Consistent Interpretation**: Clear guidance on analysis approach and mindset
- **Improved Accuracy**: Focused attention on the most relevant aspects
- **Context-Aware Scoring**: AI can apply appropriate standards for each dimension type
- **Reduced Ambiguity**: Clear purpose and scope eliminate confusion

## 🧠 AI Context Impact on Analysis Quality

### **Before AI Context (Traditional Approach)**
```
❌ AI receives only specific criteria without understanding the broader purpose
❌ May focus on wrong aspects or apply inappropriate standards  
❌ Inconsistent interpretation across different content types
❌ Difficulty understanding the "why" behind the scoring criteria
```

### **With AI Context (Enhanced Approach)**
```
✅ AI understands the fundamental purpose of each dimension
✅ Clear guidance on analysis approach and quality standards
✅ Consistent evaluation methodology across all content
✅ Context-aware scoring that adapts to the dimension's intent
✅ Better recognition of nuances and edge cases
```

This generic custom dimensions system provides unlimited flexibility for any content analysis framework while maintaining a clean, maintainable codebase with no embedded business logic, enhanced by comprehensive AI context for superior analysis quality.
