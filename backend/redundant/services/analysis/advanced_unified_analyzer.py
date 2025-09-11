"""
Advanced Unified Content Analyzer - Aligns all dimensions with the advanced framework
"""
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from uuid import UUID
import httpx
from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool


@dataclass
class GenericDimension:
    """Generic dimension structure that works for ANY analysis type"""
    dimension_id: str
    name: str
    description: str
    
    # AI context for overall understanding
    ai_context: Dict[str, Any] = None
    
    # Flexible criteria structure
    criteria: Dict[str, Any] = None
    
    # Configurable scoring framework
    scoring_framework: Dict[str, Any] = None
    
    # Client-specific metadata
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        # Default AI context
        if not self.ai_context:
            self.ai_context = {
                "general_description": self.description,
                "purpose": f"Evaluate content for {self.name}",
                "scope": "All content types",
                "key_focus_areas": [],
                "analysis_approach": "Standard analysis methodology"
            }
        
        # Default criteria
        if not self.criteria:
            self.criteria = {
                "what_counts": f"Evidence related to {self.name}",
                "positive_signals": [],
                "negative_signals": [],
                "exclusions": [],
                "additional_context": ""
            }
        
        # Default scoring framework
        if not self.scoring_framework:
            self.scoring_framework = {
                "levels": [
                    {"range": [0, 2], "label": "Low", "description": "Minimal evidence"},
                    {"range": [3, 7], "label": "Medium", "description": "Moderate evidence"},
                    {"range": [8, 10], "label": "High", "description": "Strong evidence"}
                ],
                "evidence_requirements": {
                    "min_words": 50,
                    "word_increment": 50,
                    "max_score_per_increment": 1,
                    "specificity_weight": 0.3
                },
                "contextual_rules": []
            }


class AdvancedUnifiedAnalyzer:
    """Unified analyzer using advanced framework for ALL dimension types"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        self.openai_api_key = settings.OPENAI_API_KEY
    
    async def analyze_content(
        self, 
        url: str, 
        content: str,
        title: str = "",
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze content using advanced unified framework"""
        try:
            # Load all dimensions as generic dimensions
            dimensions = await self._load_all_dimensions_as_generic(project_id)
            
            # Build unified prompt with all dimensions
            prompt = self._build_advanced_unified_prompt(dimensions, content, title)
            
            # Call AI with structured response
            ai_response = await self._call_openai_advanced(prompt, dimensions)
            
            # Parse and structure results
            result = self._parse_advanced_response(ai_response, dimensions)
            
            # Store unified results
            await self._store_advanced_analysis(url, result, project_id)
            
            # Select primary dimensions for each group
            await self._select_primary_dimensions(url, result, project_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Advanced analysis failed for {url}: {e}")
            raise
    
    async def _load_all_dimensions_as_generic(self, project_id: Optional[str] = None) -> List[GenericDimension]:
        """Load all analysis dimensions (personas, JTBD, custom) as generic dimensions"""
        dimensions = []
        
        async with self.db.acquire() as conn:
            # Get project info with comprehensive profile
            project = await conn.fetchrow("""
                SELECT 
                    company_name, 
                    company_domain, 
                    description,
                    company_profile,
                    get_company_ai_context($1) as ai_context
                FROM client_config 
                WHERE id = $1
                LIMIT 1
            """, project_id)
            
            if not project:
                raise ValueError("No project found")
            
            # Store company context for use in prompts
            self._current_company_context = project['ai_context'] or f"Analyzing content for {project['company_name']} ({project['company_domain']})"
            
            # 1. Convert Personas to Generic Dimensions
            # Get personas from analysis_config
            config = await conn.fetchrow("""
                SELECT personas, jtbd_phases, custom_dimensions
                FROM analysis_config
                LIMIT 1
            """)
            
            personas_data = []
            if config and config['personas']:
                personas_data = json.loads(config['personas']) if isinstance(config['personas'], str) else config['personas']
            
            for p in personas_data:
                persona_dim = GenericDimension(
                    dimension_id=f"persona_{p.get('name', 'Unknown').lower().replace(' ', '_')}",
                    name=f"Persona Alignment: {p.get('name', 'Unknown')}",
                    description=f"Alignment with {p.get('name', 'Unknown')} ({p.get('title', 'Unknown Role')} in {p.get('department', 'Unknown')})",
                    ai_context={
                        "general_description": f"This dimension measures how well content aligns with the needs, goals, and decision-making criteria of the {p['name']} persona",
                        "purpose": f"Evaluate content relevance and value for {p['title']} professionals in {p['department']} departments",
                        "scope": "All content types that could influence or inform this persona's decision-making process",
                        "key_focus_areas": [
                            f"Addressing goals: {', '.join(p['goals'][:3]) if p['goals'] else 'Not specified'}",
                            f"Solving pain points: {', '.join(p['challenges'][:3]) if p['challenges'] else 'Not specified'}",
                            f"Supporting decision criteria: {', '.join(p['decision_criteria'][:3]) if p['decision_criteria'] else 'Not specified'}",
                            f"Role in buying journey: {p.get('buying_journey_involvement', 'Not specified')}",
                            f"Influence level: {p.get('influence_level', 'Not specified')}"
                        ],
                        "analysis_approach": "Evaluate how directly and effectively the content speaks to this persona's specific needs and concerns"
                    },
                    criteria={
                        "what_counts": f"Content that directly addresses {p['name']}'s goals, challenges, and decision criteria",
                        "positive_signals": [
                            f"Direct mention of {p['department']} challenges",
                            f"Solutions for: {', '.join(p['goals'][:2]) if p['goals'] else 'goals'}",
                            f"Addresses pain points: {', '.join(p['challenges'][:2]) if p['challenges'] else 'challenges'}",
                            f"Aligns with decision criteria: {', '.join(p['decision_criteria'][:2]) if p['decision_criteria'] else 'criteria'}",
                            "Language appropriate for this seniority level",
                            "Examples relevant to this department"
                        ],
                        "negative_signals": [
                            "Content for different departments or roles",
                            "Technical level mismatch for this persona",
                            "Irrelevant examples or use cases",
                            "Wrong stage of buying journey"
                        ],
                        "exclusions": [
                            "Generic marketing content without persona focus",
                            "Content explicitly for other personas"
                        ],
                        "additional_context": f"Consider {p['name']}'s influence level ({p.get('influence_level', 'Unknown')}) and role in buying journey"
                    },
                    scoring_framework={
                        "levels": [
                            {"range": [0, 2], "label": "Poor Fit", "description": "Content not relevant to this persona", 
                             "requirements": ["No alignment with goals", "Wrong audience"]},
                            {"range": [3, 4], "label": "Weak Alignment", "description": "Some relevance but not targeted",
                             "requirements": ["Tangential relevance", "Generic content"]},
                            {"range": [5, 6], "label": "Moderate Alignment", "description": "Addresses some persona needs",
                             "requirements": ["Addresses 1-2 goals or pain points", "Appropriate level"]},
                            {"range": [7, 8], "label": "Strong Alignment", "description": "Well-targeted to persona",
                             "requirements": ["Addresses multiple goals", "Solves key pain points", "Right language"]},
                            {"range": [9, 10], "label": "Perfect Fit", "description": "Exceptionally well-suited",
                             "requirements": ["Comprehensive goal alignment", "All decision criteria met", "Compelling examples"]}
                        ],
                        "evidence_requirements": {
                            "min_words": 80,
                            "word_increment": 60,
                            "max_score_per_increment": 1,
                            "specificity_weight": 0.4
                        },
                        "contextual_rules": [
                            {
                                "name": "wrong_persona_penalty",
                                "description": "Reduce score if content targets different persona",
                                "condition": "wrong_persona",
                                "adjustment_type": "cap",
                                "adjustment_value": 3
                            }
                        ]
                    },
                    metadata={
                        "persona_type": "buyer_persona",
                        "department": p['department'],
                        "seniority": p.get('title', ''),
                        "influence_level": p.get('influence_level', 'Unknown')
                    }
                )
                dimensions.append(persona_dim)
            
            # 2. Convert JTBD Phases to Generic Dimensions
            jtbd_phases = self._get_gartner_jtbd_as_dimensions()
            dimensions.extend(jtbd_phases)
            
            # 3. Load existing custom dimensions (check if they follow advanced format)
            custom_dims = await conn.fetch("""
                SELECT dimension_id, name, description, ai_context, criteria, 
                       scoring_framework, metadata
                FROM generic_custom_dimensions
                WHERE (project_id = $1 OR project_id IS NULL) AND is_active = true
                ORDER BY created_at
            """, project_id)
            
            for cd in custom_dims:
                # If dimension already follows advanced format, use it directly
                if cd['ai_context'] and cd['criteria'] and cd['scoring_framework']:
                    dimensions.append(GenericDimension(
                        dimension_id=cd['dimension_id'],
                        name=cd['name'],
                        description=cd['description'],
                        ai_context=cd['ai_context'],
                        criteria=cd['criteria'],
                        scoring_framework=cd['scoring_framework'],
                        metadata=cd['metadata'] or {}
                    ))
                else:
                    # Convert legacy format to advanced format
                    logger.warning(f"Converting legacy dimension {cd['name']} to advanced format")
                    dimensions.append(self._convert_legacy_dimension(cd))
            
            return dimensions
    
    def _get_gartner_jtbd_as_dimensions(self) -> List[GenericDimension]:
        """Convert Gartner JTBD phases to generic dimension format"""
        jtbd_phases = [
            {
                "phase": 1,
                "name": "Problem Identification",
                "description": "Recognition of business problem or opportunity",
                "questions": ["What's wrong with our current approach?", "What are we missing out on?", "What risks are we facing?"],
                "indicators": ["challenges", "problems", "risks", "inefficiencies", "gaps", "pain points", "issues"]
            },
            {
                "phase": 2,
                "name": "Solution Exploration",
                "description": "Research and discovery of potential solutions",
                "questions": ["What types of solutions exist?", "What approaches can we take?", "What are the options?"],
                "indicators": ["solutions", "approaches", "methods", "strategies", "alternatives", "options", "possibilities"]
            },
            {
                "phase": 3,
                "name": "Requirements Building",
                "description": "Definition of specific needs and criteria",
                "questions": ["What do we need specifically?", "What are must-haves vs nice-to-haves?", "What's our criteria?"],
                "indicators": ["requirements", "criteria", "specifications", "features", "capabilities", "needs", "must-haves"]
            },
            {
                "phase": 4,
                "name": "Vendor Selection",
                "description": "Evaluation and comparison of vendors",
                "questions": ["Who are the vendors?", "How do they compare?", "What makes them different?"],
                "indicators": ["comparison", "vendor", "provider", "differentiation", "competitive", "evaluation", "selection"]
            },
            {
                "phase": 5,
                "name": "Validation & Consensus",
                "description": "Building internal agreement and validation",
                "questions": ["Will this work for us?", "What do others say?", "Can we trust this vendor?"],
                "indicators": ["case study", "testimonial", "reference", "proof", "validation", "success story", "results"]
            },
            {
                "phase": 6,
                "name": "Negotiation & Purchase",
                "description": "Final negotiations and purchase decision",
                "questions": ["What's the pricing?", "What are the terms?", "How do we get started?"],
                "indicators": ["pricing", "contract", "terms", "implementation", "onboarding", "purchase", "deployment"]
            }
        ]
        
        dimensions = []
        for phase in jtbd_phases:
            dim = GenericDimension(
                dimension_id=f"jtbd_phase_{phase['phase']}",
                name=f"JTBD Phase {phase['phase']}: {phase['name']}",
                description=phase['description'],
                ai_context={
                    "general_description": f"This dimension evaluates how well content aligns with the '{phase['name']}' phase of the B2B buying journey",
                    "purpose": f"Determine if content effectively serves buyers in the {phase['name']} phase",
                    "scope": "All content types that could influence buyers during this phase",
                    "key_focus_areas": [
                        f"Answering buyer questions: {', '.join(phase['questions'])}",
                        f"Using appropriate language and indicators for this phase",
                        f"Providing value specific to this stage of the journey",
                        "Guiding buyers to the next phase"
                    ],
                    "analysis_approach": "Look for content that directly addresses the concerns and questions buyers have in this specific phase"
                },
                criteria={
                    "what_counts": f"Content that addresses {phase['name']} phase concerns and questions",
                    "positive_signals": phase['indicators'] + [
                        f"Answers: {q}" for q in phase['questions']
                    ],
                    "negative_signals": [
                        "Content for different buying phases",
                        "Premature selling or pricing discussion" if phase['phase'] < 4 else "",
                        "Too technical for early phases" if phase['phase'] < 3 else "",
                        "Missing key phase elements"
                    ],
                    "exclusions": [
                        "Generic content without phase focus",
                        "Pure product features without context"
                    ],
                    "additional_context": f"Phase {phase['phase']} of 6 in the Gartner B2B buying journey"
                },
                scoring_framework={
                    "levels": [
                        {"range": [0, 2], "label": "Wrong Phase", "description": "Content for different phase",
                         "requirements": ["No phase alignment", "Wrong buyer questions"]},
                        {"range": [3, 4], "label": "Weak Match", "description": "Some phase relevance",
                         "requirements": ["Minimal phase indicators", "Tangential relevance"]},
                        {"range": [5, 6], "label": "Moderate Match", "description": "Addresses phase needs",
                         "requirements": ["Some phase questions answered", "Appropriate indicators"]},
                        {"range": [7, 8], "label": "Strong Match", "description": "Well-aligned to phase",
                         "requirements": ["Multiple questions answered", "Clear phase indicators"]},
                        {"range": [9, 10], "label": "Perfect Match", "description": "Ideal for this phase",
                         "requirements": ["All key questions addressed", "Guides to next phase", "Comprehensive coverage"]}
                    ],
                    "evidence_requirements": {
                        "min_words": 100,
                        "word_increment": 75,
                        "max_score_per_increment": 1,
                        "specificity_weight": 0.35
                    },
                    "contextual_rules": [
                        {
                            "name": "wrong_phase_cap",
                            "description": "Cap score if content is for wrong phase",
                            "condition": "wrong_phase",
                            "adjustment_type": "cap",
                            "adjustment_value": 2
                        }
                    ]
                },
                metadata={
                    "dimension_type": "jtbd_phase",
                    "phase_number": phase['phase'],
                    "phase_name": phase['name'],
                    "gartner_framework": True
                }
            )
            dimensions.append(dim)
        
        return dimensions
    
    def _convert_legacy_dimension(self, legacy_dim: Dict) -> GenericDimension:
        """Convert legacy dimension format to advanced format"""
        return GenericDimension(
            dimension_id=legacy_dim.get('dimension_id', legacy_dim['name'].lower().replace(' ', '_')),
            name=legacy_dim['name'],
            description=legacy_dim.get('description', f"Custom dimension: {legacy_dim['name']}"),
            ai_context={
                "general_description": legacy_dim.get('description', f"Evaluate content for {legacy_dim['name']}"),
                "purpose": f"Assess {legacy_dim['name']} in content",
                "scope": "All relevant content types",
                "key_focus_areas": legacy_dim.get('evidence_types', []),
                "analysis_approach": "Standard evaluation methodology"
            },
            criteria={
                "what_counts": f"Evidence of {legacy_dim['name']}",
                "positive_signals": legacy_dim.get('positive_indicators', []),
                "negative_signals": legacy_dim.get('negative_indicators', []),
                "exclusions": [],
                "additional_context": ""
            },
            scoring_framework={
                "levels": self._convert_legacy_scoring_levels(legacy_dim.get('scoring_levels', [])),
                "evidence_requirements": {
                    "min_words": 80,
                    "word_increment": 60,
                    "max_score_per_increment": 1,
                    "specificity_weight": 0.3
                },
                "contextual_rules": []
            },
            metadata={
                "converted_from_legacy": True,
                "original_format": "simple_dimension"
            }
        )
    
    def _convert_legacy_scoring_levels(self, legacy_levels: List) -> List[Dict]:
        """Convert legacy scoring levels to advanced format"""
        if not legacy_levels:
            return [
                {"range": [0, 3], "label": "Low", "description": "Minimal evidence", "requirements": []},
                {"range": [4, 7], "label": "Medium", "description": "Moderate evidence", "requirements": []},
                {"range": [8, 10], "label": "High", "description": "Strong evidence", "requirements": []}
            ]
        
        # Convert legacy format
        converted = []
        for level in legacy_levels:
            if isinstance(level, dict):
                converted.append({
                    "range": [level.get('min', 0), level.get('max', 10)],
                    "label": level.get('label', 'Level'),
                    "description": level.get('description', ''),
                    "requirements": level.get('requirements', [])
                })
        return converted
    
    def _build_advanced_unified_prompt(self, dimensions: List[GenericDimension], content: str, title: str) -> str:
        """Build unified prompt using advanced framework for all dimensions"""
        dimension_sections = []
        
        for dim in dimensions:
            section = f"""
## ANALYZE: {dim.name} (Score 0-10)

**AI Context & Overall Understanding**:
**General Description**: {dim.ai_context['general_description']}
**Purpose**: {dim.ai_context['purpose']}
**Scope**: {dim.ai_context['scope']}
**Key Focus Areas**:
{chr(10).join([f"- {area}" for area in dim.ai_context['key_focus_areas']])}
**Analysis Approach**: {dim.ai_context.get('analysis_approach', 'Apply standard analysis methodology')}

---
**IMPORTANT**: Before analyzing the specific criteria below, consider this overall context to understand what this dimension is fundamentally measuring and how to approach the analysis.
---

**What Counts**: {dim.criteria['what_counts']}

**Positive Signals**: {', '.join(dim.criteria['positive_signals'])}

**Negative Signals**: {', '.join(dim.criteria['negative_signals'])}

**Exclusions**: {', '.join(dim.criteria['exclusions'])}

{f"**Additional Context**: {dim.criteria['additional_context']}" if dim.criteria.get('additional_context') else ''}

**Scoring Framework**:
{self._format_scoring_levels(dim.scoring_framework['levels'])}

**Evidence Requirements**:
- Minimum {dim.scoring_framework['evidence_requirements']['min_words']} relevant words for meaningful analysis
- Each additional {dim.scoring_framework['evidence_requirements']['word_increment']} words can improve score by up to +{dim.scoring_framework['evidence_requirements']['max_score_per_increment']} point(s)
- Specificity weighting: {dim.scoring_framework['evidence_requirements'].get('specificity_weight', 0.3)}

{self._format_contextual_rules(dim.scoring_framework.get('contextual_rules', []))}

Provide structured analysis with:
1. final_score (0-10)
2. evidence_summary
3. evidence_analysis (word count, specificity, quality indicators)
4. scoring_breakdown (base score, adjustments, rationale)
5. confidence_score (0-10)
6. detailed_reasoning
7. matched_criteria (list of matched positive signals)
"""
            dimension_sections.append(section)
        
        # Get company context from the stored project data
        company_context = getattr(self, '_current_company_context', '')
        
        return f"""
You are an expert content analyst evaluating B2B content using an advanced multi-dimensional framework.

{company_context}

CONTENT TO ANALYZE:
Title: {title}
Content: {content[:4000]}...

ANALYSIS INSTRUCTIONS:
Consider the company context above when evaluating content. Assess relevance, competitive positioning, 
and strategic alignment based on the company's business model, target audience, and market position.

{chr(10).join(dimension_sections)}

RESPOND WITH A COMPREHENSIVE JSON STRUCTURE containing analysis for ALL dimensions.
Each dimension should include all required fields as specified above.
"""
    
    def _format_scoring_levels(self, levels: List[Dict]) -> str:
        """Format scoring levels for prompt"""
        formatted = []
        for level in levels:
            range_str = f"{level['range'][0]}-{level['range'][1]}"
            reqs = '; '.join(level.get('requirements', []))
            formatted.append(f"- **{range_str} ({level['label']})**: {level['description']} - Requirements: {reqs}")
        return '\n'.join(formatted)
    
    def _format_contextual_rules(self, rules: List[Dict]) -> str:
        """Format contextual rules for prompt"""
        if not rules:
            return ""
        
        formatted = ["**Contextual Rules**:"]
        for rule in rules:
            formatted.append(f"- **{rule['name']}**: {rule['description']} ({rule['adjustment_type']}: {rule['adjustment_value']})")
        return '\n'.join(formatted)
    
    async def _call_openai_advanced(self, prompt: str, dimensions: List[GenericDimension]) -> Dict[str, Any]:
        """Call OpenAI with advanced structured response"""
        # Build dynamic schema based on dimensions
        dimension_properties = {}
        for dim in dimensions:
            dimension_properties[dim.dimension_id] = {
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
                            "quality_indicators": {"type": "object"}
                        }
                    },
                    "scoring_breakdown": {
                        "type": "object",
                        "properties": {
                            "base_score": {"type": "integer"},
                            "evidence_adjustments": {"type": "object"},
                            "contextual_adjustments": {"type": "object"},
                            "scoring_rationale": {"type": "string"}
                        }
                    },
                    "confidence_score": {"type": "integer", "minimum": 0, "maximum": 10},
                    "detailed_reasoning": {"type": "string"},
                    "matched_criteria": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["final_score", "evidence_summary", "confidence_score", "detailed_reasoning"]
            }
        
        response_schema = {
            "type": "object",
            "properties": {
                "dimensions": {
                    "type": "object",
                    "properties": dimension_properties
                },
                "overall_summary": {"type": "string"},
                "key_insights": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["dimensions", "overall_summary"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4.1-2025-04-14",  # Latest GPT-4.1 model
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert B2B content analyst using an advanced multi-dimensional analysis framework. Provide thorough, evidence-based analysis."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000,
                    "response_format": {"type": "json_object"},
                    "function_call": {"name": "analyze_content"},
                    "functions": [{
                        "name": "analyze_content",
                        "parameters": response_schema
                    }]
                },
                timeout=90.0
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            result = response.json()
            return json.loads(result['choices'][0]['message']['function_call']['arguments'])
    
    def _parse_advanced_response(self, ai_response: Dict[str, Any], dimensions: List[GenericDimension]) -> Dict[str, Any]:
        """Parse and validate advanced AI response"""
        parsed = {
            "analyzed_at": datetime.utcnow().isoformat(),
            "dimensions": {},
            "overall_summary": ai_response.get("overall_summary", ""),
            "key_insights": ai_response.get("key_insights", []),
            "metadata": {
                "total_dimensions_analyzed": len(dimensions),
                "framework_version": "advanced_v1.0"
            }
        }
        
        # Process each dimension result
        for dim in dimensions:
            if dim.dimension_id in ai_response.get("dimensions", {}):
                dim_result = ai_response["dimensions"][dim.dimension_id]
                parsed["dimensions"][dim.dimension_id] = {
                    "dimension_name": dim.name,
                    "dimension_type": dim.metadata.get("dimension_type", "custom"),
                    "final_score": dim_result.get("final_score", 0),
                    "evidence_summary": dim_result.get("evidence_summary", ""),
                    "evidence_analysis": dim_result.get("evidence_analysis", {}),
                    "scoring_breakdown": dim_result.get("scoring_breakdown", {}),
                    "confidence_score": dim_result.get("confidence_score", 0),
                    "detailed_reasoning": dim_result.get("detailed_reasoning", ""),
                    "matched_criteria": dim_result.get("matched_criteria", []),
                    "metadata": dim.metadata
                }
        
        return parsed
    
    async def _store_advanced_analysis(self, url: str, result: Dict[str, Any], project_id: Optional[str] = None) -> None:
        """Store advanced analysis results"""
        async with self.db.acquire() as conn:
            # Store main analysis record
            analysis_id = await conn.fetchval("""
                INSERT INTO advanced_content_analysis (
                    id, url, project_id, analyzed_at,
                    overall_summary, key_insights, metadata
                ) VALUES (
                    gen_random_uuid(), $1, $2, $3, $4, $5, $6
                )
                ON CONFLICT (url, project_id) DO UPDATE SET
                    analyzed_at = EXCLUDED.analyzed_at,
                    overall_summary = EXCLUDED.overall_summary,
                    key_insights = EXCLUDED.key_insights,
                    metadata = EXCLUDED.metadata
                RETURNING id
            """,
                url,
                project_id,
                result['analyzed_at'],
                result['overall_summary'],
                result['key_insights'],
                json.dumps(result['metadata'])
            )
            
            # Store individual dimension results
            for dim_id, dim_result in result['dimensions'].items():
                await conn.execute("""
                    INSERT INTO advanced_dimension_analysis (
                        analysis_id, dimension_id, dimension_name, dimension_type,
                        final_score, evidence_summary, evidence_analysis,
                        scoring_breakdown, confidence_score, detailed_reasoning,
                        matched_criteria, analysis_metadata
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                    )
                    ON CONFLICT (analysis_id, dimension_id) DO UPDATE SET
                        final_score = EXCLUDED.final_score,
                        evidence_summary = EXCLUDED.evidence_summary,
                        evidence_analysis = EXCLUDED.evidence_analysis,
                        scoring_breakdown = EXCLUDED.scoring_breakdown,
                        confidence_score = EXCLUDED.confidence_score,
                        detailed_reasoning = EXCLUDED.detailed_reasoning,
                        matched_criteria = EXCLUDED.matched_criteria,
                        analysis_metadata = EXCLUDED.analysis_metadata
                """,
                    analysis_id,
                    dim_id,
                    dim_result['dimension_name'],
                    dim_result['dimension_type'],
                    dim_result['final_score'],
                    dim_result['evidence_summary'],
                    json.dumps(dim_result['evidence_analysis']),
                    json.dumps(dim_result['scoring_breakdown']),
                    dim_result['confidence_score'],
                    dim_result['detailed_reasoning'],
                    dim_result['matched_criteria'],
                    json.dumps(dim_result.get('metadata', {}))
                )
            
            logger.info(f"✅ Stored advanced analysis for {url} with {len(result['dimensions'])} dimensions")
    
    async def _select_primary_dimensions(self, url: str, result: Dict[str, Any], project_id: Optional[str] = None) -> None:
        """Select primary dimensions for each dimension group based on analysis results"""
        async with self.db.acquire() as conn:
            # Get the analysis ID
            analysis_id = await conn.fetchval("""
                SELECT id FROM advanced_content_analysis 
                WHERE url = $1 AND project_id = $2
                ORDER BY analyzed_at DESC
                LIMIT 1
            """, url, project_id)
            
            if not analysis_id:
                logger.warning(f"No analysis found for {url}")
                return
            
            # Get all active dimension groups for this project
            groups = await conn.fetch("""
                SELECT id, group_id, name, selection_strategy, max_primary_dimensions
                FROM dimension_groups
                WHERE (project_id = $1 OR project_id IS NULL) AND is_active = true
                ORDER BY display_order
            """, project_id)
            
            for group in groups:
                # Get dimensions in this group that were analyzed
                group_dimensions = await conn.fetch("""
                    SELECT DISTINCT dgm.dimension_id
                    FROM dimension_group_members dgm
                    WHERE dgm.group_id = $1
                        AND dgm.dimension_id = ANY($2)
                """, group['id'], list(result['dimensions'].keys()))
                
                if not group_dimensions:
                    continue
                
                # Select primary dimension(s) based on strategy
                primary_dims = self._select_by_strategy(
                    group,
                    [d['dimension_id'] for d in group_dimensions],
                    result['dimensions']
                )
                
                # Store primary dimension selections
                for primary_dim in primary_dims[:group['max_primary_dimensions']]:
                    dim_result = result['dimensions'][primary_dim['dimension_id']]
                    
                    await conn.execute("""
                        INSERT INTO analysis_primary_dimensions (
                            analysis_id, group_id, dimension_id,
                            selection_reason, selection_score, selection_metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (analysis_id, group_id) DO UPDATE SET
                            dimension_id = EXCLUDED.dimension_id,
                            selection_reason = EXCLUDED.selection_reason,
                            selection_score = EXCLUDED.selection_score,
                            selection_metadata = EXCLUDED.selection_metadata,
                            selected_at = NOW()
                    """,
                        analysis_id,
                        group['id'],
                        primary_dim['dimension_id'],
                        primary_dim['reason'],
                        primary_dim['score'],
                        json.dumps(primary_dim.get('metadata', {}))
                    )
                    
                    logger.info(f"Selected {primary_dim['dimension_id']} as primary for group {group['name']} (score: {primary_dim['score']})")
    
    def _select_by_strategy(self, group: Dict, dimension_ids: List[str], dimension_results: Dict) -> List[Dict]:
        """Select primary dimensions based on group strategy"""
        candidates = []
        
        for dim_id in dimension_ids:
            if dim_id not in dimension_results:
                continue
                
            dim_result = dimension_results[dim_id]
            
            if group['selection_strategy'] == 'highest_score':
                score = dim_result.get('final_score', 0)
                reason = f"Highest score ({score}/10) in {group['name']} group"
                
            elif group['selection_strategy'] == 'highest_confidence':
                score = dim_result.get('confidence_score', 0)
                reason = f"Highest confidence ({score}/10) in {group['name']} group"
                
            elif group['selection_strategy'] == 'most_evidence':
                evidence_count = len(dim_result.get('matched_criteria', []))
                word_count = dim_result.get('evidence_analysis', {}).get('total_relevant_words', 0)
                score = evidence_count + (word_count / 100)  # Weighted score
                reason = f"Most evidence ({evidence_count} criteria, {word_count} words) in {group['name']} group"
                
            else:  # manual or default
                score = dim_result.get('final_score', 0)
                reason = f"Selected for {group['name']} group"
            
            candidates.append({
                'dimension_id': dim_id,
                'score': score,
                'reason': reason,
                'metadata': {
                    'final_score': dim_result.get('final_score', 0),
                    'confidence_score': dim_result.get('confidence_score', 0),
                    'evidence_count': len(dim_result.get('matched_criteria', [])),
                    'strategy_used': group['selection_strategy']
                }
            })
        
        # Sort by score descending
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        return candidates
