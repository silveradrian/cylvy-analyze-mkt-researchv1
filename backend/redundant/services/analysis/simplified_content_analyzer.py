"""
Simplified Content Analyzer - Unified AI Analysis Framework
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from uuid import UUID
import httpx
from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool


@dataclass
class PersonaContext:
    """Simplified persona for AI analysis"""
    name: str
    role: str
    primary_goals: List[str]
    pain_points: List[str]
    decision_factors: List[str]
    
    def to_prompt(self) -> str:
        """Convert to AI prompt format"""
        return f"""
{self.name} ({self.role}):
- Goals: {', '.join(self.primary_goals[:3])}
- Pain Points: {', '.join(self.pain_points[:3])}
- Decision Factors: {', '.join(self.decision_factors[:3])}
"""


@dataclass
class JTBDPhaseContext:
    """JTBD phase for AI analysis"""
    phase_number: int
    phase_name: str
    buyer_questions: List[str]
    content_indicators: List[str]
    
    def to_prompt(self) -> str:
        """Convert to AI prompt format"""
        return f"""
Phase {self.phase_number}: {self.phase_name}
- Buyer asks: {', '.join(self.buyer_questions[:3])}
- Look for: {', '.join(self.content_indicators[:3])}
"""


@dataclass
class DimensionContext:
    """Custom dimension for AI analysis"""
    name: str
    scoring_levels: Dict[int, str]
    evidence_types: List[str]
    
    def to_prompt(self) -> str:
        """Convert to AI prompt format"""
        levels = '\n'.join([f"  {score}: {desc}" for score, desc in self.scoring_levels.items()])
        return f"""
{self.name}:
{levels}
Look for: {', '.join(self.evidence_types)}
"""


@dataclass
class UnifiedAnalysisContext:
    """Everything AI needs to analyze content"""
    company_name: str
    company_domain: str
    personas: List[PersonaContext]
    jtbd_phases: List[JTBDPhaseContext]
    custom_dimensions: List[DimensionContext]


class SimplifiedContentAnalyzer:
    """Simplified content analyzer with unified context"""
    
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
        """Analyze content with unified context"""
        try:
            # 1. Load unified context
            context = await self._load_analysis_context(project_id)
            
            # 2. Build single comprehensive prompt
            prompt = self._build_analysis_prompt(context, content, title)
            
            # 3. Call AI once with all context
            ai_response = await self._call_openai(prompt)
            
            # 4. Parse structured response
            result = self._parse_ai_response(ai_response)
            
            # 5. Store in simplified schema
            await self._store_analysis(url, result, project_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed for {url}: {e}")
            raise
    
    async def _load_analysis_context(self, project_id: Optional[str] = None) -> UnifiedAnalysisContext:
        """Load all configuration into unified context"""
        async with self.db.acquire() as conn:
            # Get project info
            project = await conn.fetchrow("""
                SELECT company_name, company_domain, description
                FROM projects 
                WHERE id = $1 OR is_default = true
                ORDER BY is_default ASC
                LIMIT 1
            """, project_id)
            
            if not project:
                raise ValueError("No project found")
            
            # Get personas (mandatory)
            personas_data = await conn.fetch("""
                SELECT name, title, department, goals, challenges, decision_criteria
                FROM personas
                WHERE project_id = $1 OR project_id IS NULL
                ORDER BY created_at
            """, project_id)
            
            personas = []
            for p in personas_data:
                personas.append(PersonaContext(
                    name=p['name'],
                    role=f"{p['title']} in {p['department']}",
                    primary_goals=p['goals'][:3] if p['goals'] else [],
                    pain_points=p['challenges'][:3] if p['challenges'] else [],
                    decision_factors=p['decision_criteria'][:3] if p['decision_criteria'] else []
                ))
            
            # Use Gartner JTBD phases (pre-configured)
            jtbd_phases = self._get_gartner_jtbd_phases()
            
            # Get custom dimensions (optional)
            dimensions_data = await conn.fetch("""
                SELECT name, scoring_levels, evidence_config
                FROM generic_dimensions
                WHERE project_id = $1 OR project_id IS NULL
                ORDER BY created_at
            """, project_id)
            
            dimensions = []
            for d in dimensions_data:
                levels = {}
                if d['scoring_levels']:
                    for level in d['scoring_levels']:
                        levels[level['level']] = level['description']
                
                evidence_types = []
                if d['evidence_config'] and 'required_evidence_types' in d['evidence_config']:
                    evidence_types = d['evidence_config']['required_evidence_types']
                
                dimensions.append(DimensionContext(
                    name=d['name'],
                    scoring_levels=levels or {0: "Basic", 5: "Intermediate", 10: "Advanced"},
                    evidence_types=evidence_types or ["specific features", "case studies", "metrics"]
                ))
            
            return UnifiedAnalysisContext(
                company_name=project['company_name'],
                company_domain=project['company_domain'],
                personas=personas,
                jtbd_phases=jtbd_phases,
                custom_dimensions=dimensions
            )
    
    def _get_gartner_jtbd_phases(self) -> List[JTBDPhaseContext]:
        """Get pre-configured Gartner B2B buying journey phases"""
        return [
            JTBDPhaseContext(
                phase_number=1,
                phase_name="Problem Identification",
                buyer_questions=["What's wrong with our current approach?", "What are we missing out on?", "What risks are we facing?"],
                content_indicators=["challenges", "problems", "risks", "inefficiencies", "gaps"]
            ),
            JTBDPhaseContext(
                phase_number=2,
                phase_name="Solution Exploration",
                buyer_questions=["What types of solutions exist?", "What approaches can we take?", "What are the options?"],
                content_indicators=["solutions", "approaches", "methods", "strategies", "alternatives"]
            ),
            JTBDPhaseContext(
                phase_number=3,
                phase_name="Requirements Building",
                buyer_questions=["What do we need specifically?", "What are must-haves vs nice-to-haves?", "What's our criteria?"],
                content_indicators=["requirements", "criteria", "specifications", "features", "capabilities"]
            ),
            JTBDPhaseContext(
                phase_number=4,
                phase_name="Vendor Selection",
                buyer_questions=["Who are the vendors?", "How do they compare?", "What makes them different?"],
                content_indicators=["comparison", "vendor", "provider", "differentiation", "competitive"]
            ),
            JTBDPhaseContext(
                phase_number=5,
                phase_name="Validation & Consensus",
                buyer_questions=["Will this work for us?", "What do others say?", "Can we trust this vendor?"],
                content_indicators=["case study", "testimonial", "reference", "proof", "validation"]
            ),
            JTBDPhaseContext(
                phase_number=6,
                phase_name="Negotiation & Purchase",
                buyer_questions=["What's the pricing?", "What are the terms?", "How do we get started?"],
                content_indicators=["pricing", "contract", "terms", "implementation", "onboarding"]
            )
        ]
    
    def _build_analysis_prompt(self, context: UnifiedAnalysisContext, content: str, title: str) -> str:
        """Build unified analysis prompt"""
        # Format personas
        personas_text = "\n".join([p.to_prompt() for p in context.personas])
        
        # Format JTBD phases
        jtbd_text = "\n".join([j.to_prompt() for j in context.jtbd_phases])
        
        # Format dimensions
        dimensions_text = "\n".join([d.to_prompt() for d in context.custom_dimensions])
        dimensions_section = f"""
3. CUSTOM DIMENSIONS
Score each dimension based on evidence level:
{dimensions_text}
""" if context.custom_dimensions else ""
        
        return f"""
You are analyzing B2B content for {context.company_name} ({context.company_domain}).

CONTENT TO ANALYZE:
Title: {title}
Content: {content[:3000]}...

ANALYSIS INSTRUCTIONS:

1. PERSONA ALIGNMENT (score each 0-10)
{personas_text}

For each persona, score based on:
- Does content address their specific goals?
- Does it acknowledge their pain points?
- Does it speak to their decision factors?

2. BUYER JOURNEY PHASE
{jtbd_text}

Identify which phase (1-6) this content best serves and score alignment (0-10).
{dimensions_section}
4. COMPETITIVE MENTIONS
Identify all company/product mentions with sentiment (positive/neutral/negative).

5. BUYER INTENT SIGNALS
List specific phrases that indicate buying intent.

RESPOND WITH THIS EXACT JSON FORMAT:
{{
    "primary_persona": "persona name that best fits",
    "persona_scores": {{"persona_name": score}},
    "persona_reasoning": "why this persona fits best",
    
    "primary_jtbd_phase": 1-6,
    "phase_alignment_score": 0-10,
    "phase_reasoning": "why this phase fits",
    
    "dimension_scores": {{"dimension_name": 0/5/10}},
    "dimension_evidence": {{"dimension_name": "specific evidence cited"}},
    
    "mentions": [
        {{
            "entity": "company/product name",
            "sentiment": "positive/neutral/negative",
            "context": "snippet showing the mention"
        }}
    ],
    
    "summary": "2-3 sentences summarizing the content's value and positioning",
    "buyer_intent_signals": ["specific phrase 1", "specific phrase 2"]
}}
"""
    
    async def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API with unified prompt"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4.1-2025-04-14",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert B2B content analyst. Analyze content objectively and provide scores based on evidence."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                    "response_format": {"type": "json_object"}
                },
                timeout=60.0
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            result = response.json()
            return json.loads(result['choices'][0]['message']['content'])
    
    def _parse_ai_response(self, ai_response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate AI response"""
        # Add timestamp and ensure all expected fields exist
        return {
            "analyzed_at": datetime.utcnow().isoformat(),
            "primary_persona": ai_response.get("primary_persona", "Unknown"),
            "persona_scores": ai_response.get("persona_scores", {}),
            "persona_reasoning": ai_response.get("persona_reasoning", ""),
            "primary_jtbd_phase": ai_response.get("primary_jtbd_phase", 1),
            "phase_alignment_score": ai_response.get("phase_alignment_score", 0),
            "phase_reasoning": ai_response.get("phase_reasoning", ""),
            "dimension_scores": ai_response.get("dimension_scores", {}),
            "dimension_evidence": ai_response.get("dimension_evidence", {}),
            "mentions": ai_response.get("mentions", []),
            "summary": ai_response.get("summary", ""),
            "buyer_intent_signals": ai_response.get("buyer_intent_signals", []),
            "raw_response": ai_response  # Keep full response for debugging
        }
    
    async def _store_analysis(self, url: str, result: Dict[str, Any], project_id: Optional[str] = None) -> None:
        """Store analysis in simplified schema"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO content_analysis (
                    id, url, project_id, analyzed_at,
                    primary_persona, persona_scores, persona_reasoning,
                    primary_jtbd_phase, phase_alignment_score, phase_reasoning,
                    dimension_scores, dimension_evidence,
                    mentions, summary, buyer_intent_signals,
                    ai_response
                ) VALUES (
                    gen_random_uuid(), $1, $2, $3,
                    $4, $5, $6,
                    $7, $8, $9,
                    $10, $11,
                    $12, $13, $14,
                    $15
                )
                ON CONFLICT (url, project_id) DO UPDATE SET
                    analyzed_at = EXCLUDED.analyzed_at,
                    primary_persona = EXCLUDED.primary_persona,
                    persona_scores = EXCLUDED.persona_scores,
                    persona_reasoning = EXCLUDED.persona_reasoning,
                    primary_jtbd_phase = EXCLUDED.primary_jtbd_phase,
                    phase_alignment_score = EXCLUDED.phase_alignment_score,
                    phase_reasoning = EXCLUDED.phase_reasoning,
                    dimension_scores = EXCLUDED.dimension_scores,
                    dimension_evidence = EXCLUDED.dimension_evidence,
                    mentions = EXCLUDED.mentions,
                    summary = EXCLUDED.summary,
                    buyer_intent_signals = EXCLUDED.buyer_intent_signals,
                    ai_response = EXCLUDED.ai_response
            """,
                url,
                project_id,
                result['analyzed_at'],
                result['primary_persona'],
                json.dumps(result['persona_scores']),
                result['persona_reasoning'],
                result['primary_jtbd_phase'],
                result['phase_alignment_score'],
                result['phase_reasoning'],
                json.dumps(result['dimension_scores']),
                json.dumps(result['dimension_evidence']),
                json.dumps(result['mentions']),
                result['summary'],
                result['buyer_intent_signals'],
                json.dumps(result['raw_response'])
            )
            
            logger.info(f"✅ Stored analysis for {url}")
