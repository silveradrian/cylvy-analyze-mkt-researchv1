# Simplified AI Analysis Framework

## Overview

The current implementation is overcomplicated. The AI analysis agent needs a clear, consistent framework to evaluate content based on the configured personas, JTBD phases, and custom dimensions.

## Current Issues

1. **Fragmented Configuration**: Personas, JTBD, and dimensions are configured separately without a unified scoring framework
2. **Inconsistent Context**: The AI doesn't receive structured context about how to score against these configurations
3. **Missing Integration**: Custom dimensions aren't properly integrated into the analysis prompt
4. **Overcomplicated Structure**: Too many abstraction layers between configuration and AI analysis

## Proposed Simplified Framework

### 1. Unified Analysis Context

All configuration should feed into a single, structured analysis context:

```python
class UnifiedAnalysisContext:
    """Everything the AI needs to analyze content"""
    
    # Company context
    company_name: str
    company_domain: str
    value_proposition: str
    
    # Target personas (mandatory)
    personas: List[PersonaContext]
    
    # JTBD phases (pre-configured)
    jtbd_phases: List[JTBDPhaseContext]
    
    # Custom dimensions (optional)
    custom_dimensions: List[DimensionContext]
    
    # Scoring framework
    scoring_criteria: ScoringFramework
```

### 2. Simplified Persona Context

```python
class PersonaContext:
    """What AI needs to know about each persona"""
    name: str
    role: str  # e.g., "Technical Decision Maker"
    
    # Key characteristics for scoring
    primary_goals: List[str]  # Max 3-5
    pain_points: List[str]    # Max 3-5
    decision_factors: List[str]  # Max 3-5
    
    # Scoring instruction
    scoring_prompt: str = """
    Score 0-10 based on:
    - Does content address {name}'s goals?
    - Does it acknowledge their pain points?
    - Does it provide evidence for their decision factors?
    """
```

### 3. JTBD Phase Context

```python
class JTBDPhaseContext:
    """Gartner buying journey phases"""
    phase_name: str  # e.g., "Problem Identification"
    phase_number: int  # 1-6
    
    # Key indicators for this phase
    buyer_questions: List[str]  # What buyers ask in this phase
    content_indicators: List[str]  # Words/phrases that indicate this phase
    
    # Scoring instruction
    scoring_prompt: str = """
    Score 0-10 based on:
    - Does content answer phase-specific questions?
    - Does it use appropriate language for this phase?
    - Is it structured for this stage of buying journey?
    """
```

### 4. Custom Dimension Context

```python
class DimensionContext:
    """Custom competitive dimensions"""
    name: str  # e.g., "Cloud Maturity"
    
    # Simple 3-level scoring
    levels: Dict[int, str] = {
        0: "Basic/Generic claims",
        5: "Specific features/capabilities", 
        10: "Proven outcomes with evidence"
    }
    
    # What to look for
    evidence_types: List[str]  # e.g., ["certifications", "case studies", "technical specs"]
    
    # Scoring instruction
    scoring_prompt: str = """
    Score 0/5/10 based on evidence level:
    {levels}
    Look for: {evidence_types}
    """
```

### 5. Unified AI Prompt Structure

```python
def build_analysis_prompt(context: UnifiedAnalysisContext, content: str) -> str:
    return f"""
You are analyzing B2B content for {context.company_name}.

CONTENT TO ANALYZE:
{content}

ANALYSIS FRAMEWORK:

1. PERSONA ALIGNMENT (mandatory)
{format_personas(context.personas)}
- Identify primary persona
- Score each persona 0-10
- Explain reasoning

2. BUYER JOURNEY PHASE (mandatory)
{format_jtbd_phases(context.jtbd_phases)}
- Identify primary phase (1-6)
- Score phase alignment 0-10
- Explain reasoning

3. CUSTOM DIMENSIONS (if configured)
{format_dimensions(context.custom_dimensions)}
- Score each dimension 0/5/10
- Cite specific evidence

4. COMPETITIVE MENTIONS
- List all company/product mentions
- Sentiment for each (positive/neutral/negative)
- Context snippet

OUTPUT FORMAT:
{
    "primary_persona": "name",
    "persona_scores": {"persona_name": score},
    "primary_jtbd_phase": 1-6,
    "phase_alignment_score": 0-10,
    "dimension_scores": {"dimension_name": 0/5/10},
    "mentions": [...],
    "summary": "2-3 sentences",
    "buyer_intent_signals": ["signal1", "signal2"]
}
"""
```

### 6. Simplified Database Schema

```sql
-- Single table for all analysis results
CREATE TABLE content_analysis (
    id UUID PRIMARY KEY,
    url TEXT NOT NULL,
    analyzed_at TIMESTAMP NOT NULL,
    
    -- Core results
    primary_persona TEXT,
    persona_scores JSONB,  -- {"Technical DM": 8, "Business DM": 3}
    
    primary_jtbd_phase INTEGER,
    phase_alignment_score INTEGER,
    
    dimension_scores JSONB,  -- {"Cloud Maturity": 5, "Security": 10}
    
    -- Mentions
    mentions JSONB,
    
    -- Summary
    summary TEXT,
    buyer_intent_signals TEXT[],
    
    -- Full AI response for debugging
    ai_response JSONB
);
```

## Implementation Steps

### Phase 1: Simplify Configuration Loading

```python
async def load_analysis_context(project_id: str) -> UnifiedAnalysisContext:
    """Load all configuration into unified context"""
    
    # Load from database
    project = await get_project(project_id)
    personas = await get_personas(project_id)
    dimensions = await get_dimensions(project_id)
    
    # Use Gartner JTBD phases (hardcoded or from settings)
    jtbd_phases = get_gartner_jtbd_phases()
    
    # Build unified context
    return UnifiedAnalysisContext(
        company_name=project.company_name,
        company_domain=project.company_domain,
        personas=[simplify_persona(p) for p in personas],
        jtbd_phases=jtbd_phases,
        custom_dimensions=[simplify_dimension(d) for d in dimensions]
    )
```

### Phase 2: Simplify Analysis Service

```python
class SimplifiedContentAnalyzer:
    async def analyze(self, url: str, content: str) -> AnalysisResult:
        # 1. Load context once
        context = await load_analysis_context(self.project_id)
        
        # 2. Build single prompt
        prompt = build_analysis_prompt(context, content)
        
        # 3. Call AI once
        ai_response = await self.call_openai(prompt)
        
        # 4. Parse and store
        result = parse_ai_response(ai_response)
        await self.store_analysis(url, result)
        
        return result
```

### Phase 3: Simplify Frontend Display

- Show scores as simple bars/numbers
- Group by persona/phase/dimension
- Make insights actionable

## Benefits

1. **Single Context**: AI gets all information in one structured prompt
2. **Consistent Scoring**: All elements use 0-10 scale with clear criteria
3. **Mandatory + Optional**: Personas and JTBD always included, dimensions optional
4. **Reduced Complexity**: Fewer abstraction layers, clearer data flow
5. **Better Results**: AI can see relationships between personas, phases, and dimensions

## Migration Path

1. Keep existing UI components
2. Create simplified backend services
3. Map existing data to new simplified structure
4. Test with subset of content
5. Migrate fully once validated
