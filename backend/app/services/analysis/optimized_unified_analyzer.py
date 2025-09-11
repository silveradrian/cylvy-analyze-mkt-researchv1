"""
Optimized Unified Content Analyzer
Reduces verbosity while maintaining analysis quality
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from uuid import UUID
import json
import httpx
from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool
from app.models.generic_dimensions import GenericCustomDimension


class OptimizedUnifiedAnalyzer:
    """Optimized analyzer with reduced verbosity and improved efficiency"""
    
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
        """Analyze content with optimized output format"""
        try:
            # 1. Load all dimensions as generic
            dimensions = await self._load_all_dimensions_as_generic(project_id)
            if not dimensions:
                logger.warning("No dimensions configured for analysis")
                return {"error": "No analysis dimensions configured"}
            
            # 2. Extract company and competitor names for mention analysis
            company_info = await self._get_company_and_competitors(project_id)
            
            # 3. Build optimized prompt with more content and mention analysis
            prompt = self._build_optimized_prompt(content, title, dimensions, company_info)
            
            # 4. Call OpenAI with simplified schema including mentions
            ai_response = await self._call_openai_optimized(prompt, dimensions, include_mentions=True)
            
            # 5. Parse and enrich response
            result = self._parse_optimized_response(ai_response, dimensions)
            
            # 6. Select primary dimensions per group
            result = await self._select_primary_dimensions(result, project_id)
            
            # 7. Store optimized analysis
            await self._store_optimized_analysis(url, result, project_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Optimized analysis failed for {url}: {e}")
            raise
    
    async def _load_all_dimensions_as_generic(self, project_id: Optional[str] = None) -> List[GenericCustomDimension]:
        """Load all dimensions in generic format"""
        dimensions = []
        
        async with self.db.acquire() as conn:
            # Get project context
            if project_id:
                project = await conn.fetchrow("""
                    SELECT 
                        company_name, 
                        company_domain, 
                        description,
                        legal_name,
                        additional_domains,
                        competitors
                    FROM client_config
                    WHERE id = $1
                    LIMIT 1
                """, project_id)
                
                if project:
                    # Build company context from simplified fields
                    context_parts = [
                        f"Company: {project['company_name']}",
                        f"Legal Name: {project['legal_name']}" if project['legal_name'] else None,
                        f"Primary Domain: {project['company_domain']}",
                        f"Additional Domains: {', '.join(project['additional_domains'])}" if project['additional_domains'] else None,
                        f"Description: {project['description']}" if project['description'] else None
                    ]
                    if project['competitors']:
                        competitor_names = [c['name'] for c in project['competitors']]
                        context_parts.append(f"Competitors: {', '.join(competitor_names)}")
                    
                    self._current_company_context = ' | '.join(filter(None, context_parts))
                else:
                    self._current_company_context = "Analyzing B2B content"
            
            # Load personas, JTBD, and custom dimensions
            config = await conn.fetchrow("""
                SELECT personas, jtbd_phases, custom_dimensions
                FROM analysis_config
                LIMIT 1
            """)
            
            if config:
                # Convert personas to generic dimensions
                if config['personas']:
                    for persona in config['personas']:
                        dimensions.append(self._persona_to_generic(persona))
                
                # Convert JTBD phases to generic dimensions
                if config['jtbd_phases']:
                    for phase in config['jtbd_phases']:
                        dimensions.append(self._jtbd_to_generic(phase))
                
                # Add custom dimensions (already in generic format)
                if config['custom_dimensions']:
                    for dim in config['custom_dimensions']:
                        dimensions.append(GenericCustomDimension(**dim))
        
                return dimensions
    
    async def _get_company_and_competitors(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get company and competitor information for mention analysis"""
        if not project_id:
            return {"company_names": [], "competitor_names": []}
        
        async with self.db.acquire() as conn:
            project = await conn.fetchrow("""
                SELECT 
                    company_name, 
                    legal_name,
                    company_domain,
                    additional_domains,
                    competitors
                FROM client_config
                WHERE id = $1
                LIMIT 1
            """, project_id)
            
            if not project:
                return {"company_names": [], "competitor_names": []}
            
            # Build list of company names/variations
            company_names = [project['company_name']]
            if project['legal_name'] and project['legal_name'] != project['company_name']:
                company_names.append(project['legal_name'])
            
            # Add domain variations (without TLD)
            if project['company_domain']:
                domain_name = project['company_domain'].split('.')[0]
                if domain_name not in company_names:
                    company_names.append(domain_name)
            
            # Extract competitor names
            competitor_names = []
            if project['competitors']:
                for comp in project['competitors']:
                    if comp.get('name'):
                        competitor_names.append(comp['name'])
                    # Add competitor domain variations
                    if comp.get('domains'):
                        for domain in comp['domains']:
                            domain_name = domain.split('.')[0]
                            if domain_name not in competitor_names:
                                competitor_names.append(domain_name)
            
            return {
                "company_names": company_names,
                "competitor_names": competitor_names
            }
    
    def _build_optimized_prompt(self, content: str, title: str, dimensions: List[GenericCustomDimension], company_info: Dict[str, Any] = None) -> str:
        """Build optimized prompt with reduced verbosity requirements"""
        # Increase content window since we're reducing output
        content_preview = content[:10000]  # Increased from 4000
        
        dimension_instructions = []
        for dim in dimensions:
            instruction = f"""
**{dim.name}** ({dim.dimension_type}):
Focus: {dim.ai_context.get('key_focus_areas', [])[0] if dim.ai_context.get('key_focus_areas') else dim.description}
Look for: {', '.join(dim.criteria['positive_signals'][:3])}
"""
            dimension_instructions.append(instruction)
        
        company_context = getattr(self, '_current_company_context', '')
        
        # Add mention analysis section if company info provided
        mention_section = ""
        if company_info and (company_info.get('company_names') or company_info.get('competitor_names')):
            company_list = ', '.join(company_info.get('company_names', []))
            competitor_list = ', '.join(company_info.get('competitor_names', []))
            
            mention_section = f"""

BRAND & COMPETITOR MENTIONS:
Client Brand: {company_list}
Competitors: {competitor_list}

For each brand/competitor mention found, provide:
- entity: The exact name mentioned
- type: "brand" or "competitor"
- sentiment: "positive", "negative", or "neutral"
- confidence: 0-10 certainty of sentiment
- context: 50-100 character snippet around the mention
- position: Approximate character position in content

Consider the full context when assessing sentiment, not just keywords.

OTHER PROMINENT ENTITIES:
Also identify other prominent companies/brands mentioned (beyond client/competitors).
For each, provide ONLY:
- entity: The exact name mentioned
- type: "other"
- sentiment: "positive", "negative", or "neutral"
(No context/position needed for "other" entities to save tokens)

CONTENT ANALYSIS:
- overall_sentiment: The overall sentiment of the content ("positive", "negative", or "neutral")
- key_topics: List of 5 main topics/themes the content covers
"""

        return f"""
You are an expert content analyst. Analyze this B2B content concisely and effectively.

{company_context}

CONTENT:
Title: {title}
Text: {content_preview}
{mention_section}
DIMENSIONS TO ANALYZE:
{chr(10).join(dimension_instructions)}

For each dimension, provide ONLY:
- score: 0-10 rating
- confidence: 0-10 certainty
- key_evidence: 1-2 sentences of strongest evidence (be specific)
- primary_signals: Top 3 matched criteria (brief labels)
- score_factors: {{positive: [2-3 brief factors], negative: [1-2 limitations if any]}}

Be concise. Focus on actionable insights. No lengthy explanations needed.
"""
    
    async def _call_openai_optimized(self, prompt: str, dimensions: List[GenericCustomDimension], include_mentions: bool = False) -> Dict[str, Any]:
        """Call OpenAI with optimized schema"""
        # Build simplified schema
        dimension_properties = {}
        for dim in dimensions:
            dimension_properties[dim.dimension_id] = {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 10},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 10},
                    "key_evidence": {"type": "string", "maxLength": 200},
                    "primary_signals": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "maxItems": 3
                    },
                    "score_factors": {
                        "type": "object",
                        "properties": {
                            "positive": {"type": "array", "items": {"type": "string", "maxLength": 50}},
                            "negative": {"type": "array", "items": {"type": "string", "maxLength": 50}}
                        }
                    }
                },
                "required": ["score", "confidence", "key_evidence"]
            }
        
        # Build base schema
        schema_properties = {
            "dimensions": {
                "type": "object",
                "properties": dimension_properties
            },
            "overall_insights": {
                "type": "string",
                "maxLength": 300,
                "description": "2-3 sentences of key takeaways"
            }
        }
        
        # Add mentions if requested
        if include_mentions:
            schema_properties["mentions"] = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "entity": {"type": "string", "description": "The exact name mentioned"},
                        "type": {"type": "string", "enum": ["brand", "competitor", "other"]},
                        "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                        "confidence": {"type": "integer", "minimum": 0, "maximum": 10},
                        "context": {"type": "string", "maxLength": 100, "description": "Snippet around mention (brand/competitor only)"},
                        "position": {"type": "integer", "description": "Character position in content (brand/competitor only)"}
                    },
                    "required": ["entity", "type", "sentiment"]
                }
            }
            
            # Add overall sentiment and key topics
            schema_properties["overall_sentiment"] = {
                "type": "string",
                "enum": ["positive", "negative", "neutral"],
                "description": "Overall sentiment of the content"
            }
            
            schema_properties["key_topics"] = {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 5,
                "maxItems": 5,
                "description": "5 main topics/themes the content covers"
            }
        
        response_schema = {
            "type": "object",
            "properties": schema_properties
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a concise B2B content analyst. Provide brief, actionable insights."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "tools": [{
                        "type": "function",
                        "function": {
                            "name": "analyze_content",
                            "description": "Analyze content for B2B insights",
                            "parameters": response_schema
                        }
                    }],
                    "tool_choice": {"type": "function", "function": {"name": "analyze_content"}},
                    "temperature": 0.3,
                    "max_tokens": 800
                },
                timeout=60.0  # Reduced from 90s
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            result = response.json()
            # Extract result from the chat completions format
            if result.get('choices') and len(result['choices']) > 0:
                choice = result['choices'][0]
                if choice.get('message') and choice['message'].get('tool_calls'):
                    tool_call = choice['message']['tool_calls'][0]
                    if tool_call.get('function') and tool_call['function'].get('arguments'):
                        return json.loads(tool_call['function']['arguments'])
            raise Exception("No tool call in OpenAI response")
    
    def _parse_optimized_response(self, ai_response: Dict[str, Any], dimensions: List[GenericCustomDimension]) -> Dict[str, Any]:
        """Parse optimized AI response"""
        dimension_results = {}
        
        for dim in dimensions:
            if dim.dimension_id in ai_response.get('dimensions', {}):
                dim_result = ai_response['dimensions'][dim.dimension_id]
                
                # Ensure all required fields with defaults
                dimension_results[dim.dimension_id] = {
                    "dimension_name": dim.name,
                    "dimension_type": dim.dimension_type,
                    "score": dim_result.get("score", 0),
                    "confidence": dim_result.get("confidence", 0),
                    "key_evidence": dim_result.get("key_evidence", "No specific evidence found"),
                    "primary_signals": dim_result.get("primary_signals", []),
                    "score_factors": dim_result.get("score_factors", {"positive": [], "negative": []}),
                    "metadata": dim.metadata
                }
        
        result = {
            "dimensions": dimension_results,
            "overall_insights": ai_response.get("overall_insights", ""),
            "analyzed_at": datetime.utcnow().isoformat(),
            "analyzer_version": "optimized-1.0"
        }
        
        # Include mentions if present
        if 'mentions' in ai_response:
            result['mentions'] = ai_response['mentions']
        
        # Include overall sentiment and key topics if present
        if 'overall_sentiment' in ai_response:
            result['overall_sentiment'] = ai_response['overall_sentiment']
        
        if 'key_topics' in ai_response:
            result['key_topics'] = ai_response['key_topics']
        
        return result
    
    async def _select_primary_dimensions(self, result: Dict[str, Any], project_id: Optional[str]) -> Dict[str, Any]:
        """Select primary dimensions for each group"""
        if not project_id:
            return result
            
        async with self.db.acquire() as conn:
            # Get dimension groups
            groups = await conn.fetch("""
                SELECT DISTINCT dg.group_id, dg.selection_strategy
                FROM dimension_groups dg
                JOIN dimension_group_members dgm ON dg.id = dgm.group_id
                WHERE dg.project_id = $1 OR dg.project_id IS NULL
                AND dg.is_active = TRUE
            """, project_id)
            
            primary_dimensions = {}
            
            for group in groups:
                # Get dimensions in this group
                group_dims = await conn.fetch("""
                    SELECT dgm.dimension_id
                    FROM dimension_group_members dgm
                    JOIN dimension_groups dg ON dgm.group_id = dg.id
                    WHERE dg.group_id = $1
                    AND (dg.project_id = $2 OR dg.project_id IS NULL)
                """, group['group_id'], project_id)
                
                # Select primary based on strategy
                dim_ids = [d['dimension_id'] for d in group_dims]
                relevant_dims = {
                    dim_id: result['dimensions'][dim_id] 
                    for dim_id in dim_ids 
                    if dim_id in result['dimensions']
                }
                
                if relevant_dims:
                    if group['selection_strategy'] == 'highest_score':
                        primary = max(relevant_dims.items(), key=lambda x: x[1]['score'])[0]
                    elif group['selection_strategy'] == 'highest_confidence':
                        primary = max(relevant_dims.items(), key=lambda x: x[1]['confidence'])[0]
                    elif group['selection_strategy'] == 'most_evidence':
                        primary = max(relevant_dims.items(), key=lambda x: len(x[1]['primary_signals']))[0]
                    else:  # manual or default
                        primary = list(relevant_dims.keys())[0]
                    
                    primary_dimensions[group['group_id']] = primary
            
            result['primary_dimensions'] = primary_dimensions
        
        return result
    
    async def _store_optimized_analysis(self, url: str, result: Dict[str, Any], project_id: Optional[str]) -> None:
        """Store optimized analysis results"""
        async with self.db.acquire() as conn:
            async with conn.transaction():
                # Store main analysis
                analysis_id = await conn.fetchval("""
                    INSERT INTO optimized_content_analysis (
                        url, project_id, overall_insights, 
                        analyzer_version, analyzed_at, mentions,
                        overall_sentiment, key_topics
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, 
                    url, 
                    project_id,
                    result['overall_insights'],
                    result['analyzer_version'],
                    datetime.fromisoformat(result['analyzed_at']),
                    json.dumps(result.get('mentions', [])),
                    result.get('overall_sentiment'),
                    json.dumps(result.get('key_topics', []))
                )
                
                # Store dimension analyses
                for dim_id, dim_result in result['dimensions'].items():
                    await conn.execute("""
                        INSERT INTO optimized_dimension_analysis (
                            analysis_id, dimension_id, dimension_name, dimension_type,
                            score, confidence, key_evidence,
                            primary_signals, score_factors
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                        analysis_id,
                        dim_id,
                        dim_result['dimension_name'],
                        dim_result['dimension_type'],
                        dim_result['score'],
                        dim_result['confidence'],
                        dim_result['key_evidence'],
                        json.dumps(dim_result['primary_signals']),
                        json.dumps(dim_result['score_factors'])
                    )
                
                # Store primary dimensions
                if 'primary_dimensions' in result:
                    for group_id, primary_dim_id in result['primary_dimensions'].items():
                        await conn.execute("""
                            INSERT INTO analysis_primary_dimensions (
                                analysis_id, group_id, dimension_id, project_id
                            ) VALUES ($1, $2, $3, $4)
                        """, analysis_id, group_id, primary_dim_id, project_id)
    
    def _persona_to_generic(self, persona: Dict[str, Any]) -> GenericCustomDimension:
        """Convert persona to generic dimension format"""
        return GenericCustomDimension(
            dimension_id=f"persona_{persona['id']}",
            name=persona['name'],
            dimension_type="persona",
            description=persona.get('description', ''),
            ai_context={
                "purpose": f"Evaluate content relevance for {persona['name']} persona",
                "scope": "B2B buyer persona alignment",
                "key_focus_areas": [
                    f"Pain points: {', '.join(persona.get('pain_points', [])[:2])}",
                    f"Goals: {', '.join(persona.get('goals', [])[:2])}",
                    f"Role: {persona.get('role', 'Business decision maker')}"
                ]
            },
            criteria={
                "what_counts": f"Content addressing {persona['name']}'s specific needs and challenges",
                "positive_signals": persona.get('keywords', [])[:5],
                "negative_signals": ["Generic content", "Irrelevant to role"],
                "exclusions": ["Consumer-focused content"]
            },
            scoring_framework={
                "levels": [
                    {"range": [0, 3], "label": "Low", "description": "Minimal relevance"},
                    {"range": [4, 6], "label": "Medium", "description": "Some relevance"},
                    {"range": [7, 10], "label": "High", "description": "Highly relevant"}
                ],
                "evidence_requirements": {
                    "min_words": 20,
                    "word_increment": 50,
                    "max_score_per_increment": 1
                }
            },
            metadata={"original_type": "persona", "persona_id": persona['id']}
        )
    
    def _jtbd_to_generic(self, phase: Dict[str, Any]) -> GenericCustomDimension:
        """Convert JTBD phase to generic dimension format"""
        return GenericCustomDimension(
            dimension_id=f"jtbd_{phase['id']}",
            name=phase['name'],
            dimension_type="jtbd_phase",
            description=phase.get('description', ''),
            ai_context={
                "purpose": f"Assess content alignment with {phase['name']} phase",
                "scope": "B2B buying journey stage",
                "key_focus_areas": phase.get('focus_areas', [])
            },
            criteria={
                "what_counts": f"Content supporting buyers in {phase['name']}",
                "positive_signals": phase.get('content_themes', [])[:5],
                "negative_signals": ["Wrong stage content", "Premature selling"],
                "exclusions": ["Unrelated journey stages"]
            },
            scoring_framework={
                "levels": [
                    {"range": [0, 3], "label": "Poor", "description": "Misaligned with phase"},
                    {"range": [4, 6], "label": "Fair", "description": "Some alignment"},
                    {"range": [7, 10], "label": "Strong", "description": "Excellent phase alignment"}
                ],
                "evidence_requirements": {
                    "min_words": 30,
                    "word_increment": 75,
                    "max_score_per_increment": 1
                }
            },
            metadata={"original_type": "jtbd", "phase_id": phase['id']}
        )
