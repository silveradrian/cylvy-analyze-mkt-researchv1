"""
Optimized Unified Content Analyzer
Reduces verbosity while maintaining analysis quality
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from uuid import UUID
import json
import asyncio
import httpx
from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool
# from app.models.generic_dimensions import GenericCustomDimension


class OptimizedUnifiedAnalyzer:
    """Optimized analyzer with reduced verbosity and improved efficiency"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        self.openai_api_key = settings.OPENAI_API_KEY
        self.openai_project_id = settings.OPENAI_PROJECT_ID
        
    async def analyze_content(
        self, 
        url: str, 
        content: str,
        title: str = "",
        project_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze content with optimized output format"""
        try:
            # Validate inputs
            if not isinstance(content, str):
                logger.error(f"Content must be a string, got {type(content)} for {url}")
                return {"error": f"Invalid content type: {type(content)}"}
            
            if not content or not content.strip():
                logger.warning(f"Empty content for {url}")
                return {"error": "Empty content"}
            
            # 1. Load all dimensions as generic
            dimensions = await self._load_all_dimensions_as_generic(project_id)
            if not dimensions:
                logger.warning("No dimensions configured for analysis")
                return {"error": "No analysis dimensions configured"}
            
            # Validate dimensions are properly configured
            validation_result = await self._validate_dimensions(dimensions, project_id)
            if not validation_result['valid']:
                logger.warning(f"Dimension validation failed: {validation_result['message']}")
                return {"error": validation_result['message']}
            
            # 2. Extract company and competitor names for mention analysis
            company_info = await self._get_company_and_competitors(project_id)
            
            # 3. Build optimized prompt with more content and mention analysis
            #    Include optional metadata if provided (light touch to avoid failures)
            prompt = self._build_optimized_prompt(content, title, dimensions, company_info)
            if metadata:
                try:
                    prompt = f"{prompt}\n\nAdditional context (metadata): {json.dumps(metadata)[:1500]}"
                except Exception:
                    # Best-effort enrichment; never fail prompt composition on metadata issues
                    pass
            
            # 4. Call OpenAI with simplified schema including mentions
            try:
                ai_response = await self._call_openai_optimized(prompt, dimensions, include_mentions=True)
            except Exception as api_error:
                logger.error(f"OpenAI API call failed for {url}: {str(api_error)}", exc_info=True)
                # Return None to trigger the default analysis below
                ai_response = None
            
            # 5. Handle None response from OpenAI
            if ai_response is None:
                logger.warning(f"OpenAI API returned None for {url}, using default analysis")
                ai_response = {"dimensions": {}, "overall_insights": "Content could not be analyzed"}
            
            # 6. Parse and enrich response
            result = self._parse_optimized_response(ai_response, dimensions)
            
            # 7. Select primary dimensions per group
            result = await self._select_primary_dimensions(result, project_id)
            
            # 8. Store optimized analysis
            await self._store_optimized_analysis(url, result, project_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Optimized analysis failed for {url}: {str(e)}", exc_info=True)
            logger.error(f"Content type: {type(content)}, Title type: {type(title)}")
            if isinstance(content, str):
                logger.error(f"Content preview: {content[:100] if content else 'None'}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}
    
    async def _validate_dimensions(self, dimensions: List[Dict[str, Any]], project_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate dimensions configuration"""
        if not dimensions:
            return {"valid": False, "message": "No dimensions configured for analysis"}
        
        # Check for minimum dimension types
        dimension_types = set(dim.get('dimension_type') for dim in dimensions)
        
        # Count dimensions by type
        type_counts = {}
        for dim in dimensions:
            dim_type = dim.get('dimension_type', 'unknown')
            type_counts[dim_type] = type_counts.get(dim_type, 0) + 1
        
        # Check if we have at least JTBD or Page Types configured
        has_jtbd = 'jtbd_phase' in dimension_types
        has_page_types = 'page_classification' in dimension_types
        
        if not has_jtbd and not has_page_types:
            return {
                "valid": False, 
                "message": "At least one default dimension type (JTBD phases or Page Types) must be configured"
            }
        
        # If we have project_id, check dimension groups
        if project_id:
            async with self.db.acquire() as conn:
                # Check if dimension groups are configured
                groups = await conn.fetch("""
                    SELECT dg.id, dg.group_id, dg.name, COUNT(dgm.id) as member_count
                    FROM dimension_groups dg
                    LEFT JOIN dimension_group_members dgm ON dg.id = dgm.group_id
                    WHERE dg.is_active = TRUE
                    GROUP BY dg.id, dg.group_id, dg.name
                """)
                
                # Warn if groups exist but have no members
                empty_groups = [g for g in groups if g['member_count'] == 0]
                if empty_groups:
                    logger.warning(f"Found {len(empty_groups)} dimension groups with no members")
        
        # Validate each dimension has required fields
        for i, dim in enumerate(dimensions):
            if not dim.get('dimension_id'):
                return {"valid": False, "message": f"Dimension at index {i} missing dimension_id"}
            if not dim.get('name'):
                return {"valid": False, "message": f"Dimension {dim.get('dimension_id')} missing name"}
            if not dim.get('ai_context'):
                return {"valid": False, "message": f"Dimension {dim.get('dimension_id')} missing ai_context"}
        
        logger.info(f"Validated {len(dimensions)} dimensions: {', '.join(type_counts.keys())}")
        return {"valid": True, "message": "Dimensions validated successfully"}
    
    async def _load_all_dimensions_as_generic(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
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
                        f"Additional Domains: {', '.join(project['additional_domains'])}" if project['additional_domains'] and isinstance(project['additional_domains'], list) else None,
                        f"Description: {project['description']}" if project['description'] else None
                    ]
                    if project['competitors']:
                        # Handle competitors as either a list or a JSONB string
                        competitors_data = project['competitors']
                        if isinstance(competitors_data, str):
                            import json
                            try:
                                competitors_data = json.loads(competitors_data)
                            except:
                                competitors_data = []
                        if isinstance(competitors_data, list):
                            competitor_names = [c.get('name', '') for c in competitors_data if isinstance(c, dict)]
                            if competitor_names:
                                context_parts.append(f"Competitors: {', '.join(competitor_names)}")
                    
                    self._current_company_context = ' | '.join(filter(None, context_parts))
                else:
                    self._current_company_context = "Analyzing B2B content"
            
            # Load personas, JTBD, page types, and custom dimensions
            config = await conn.fetchrow("""
                SELECT personas, jtbd_phases, page_types, custom_dimensions
                FROM analysis_config
                LIMIT 1
            """)
            
            if config:
                # Convert personas to generic dimensions
                if config['personas']:
                    personas_data = config['personas']
                    # Handle JSONB as string
                    if isinstance(personas_data, str):
                        import json
                        try:
                            personas_data = json.loads(personas_data)
                        except:
                            personas_data = []
                    if isinstance(personas_data, list):
                        for persona in personas_data:
                            if isinstance(persona, dict):
                                dimensions.append(self._persona_to_generic(persona))
                
                # Convert JTBD phases to generic dimensions
                if config['jtbd_phases']:
                    jtbd_data = config['jtbd_phases']
                    # Handle JSONB as string
                    if isinstance(jtbd_data, str):
                        import json
                        try:
                            jtbd_data = json.loads(jtbd_data)
                        except:
                            jtbd_data = []
                    if isinstance(jtbd_data, list):
                        for phase in jtbd_data:
                            if isinstance(phase, dict):
                                dimensions.append(self._jtbd_to_generic(phase))
                
                # Convert page types to generic dimensions
                if config['page_types']:
                    page_types_data = config['page_types']
                    # Handle JSONB as string
                    if isinstance(page_types_data, str):
                        import json
                        try:
                            page_types_data = json.loads(page_types_data)
                        except:
                            page_types_data = []
                    if isinstance(page_types_data, list):
                        for page_type in page_types_data:
                            if isinstance(page_type, dict):
                                dimensions.append(self._page_type_to_generic(page_type))
                
                # Add custom dimensions (already in generic format)
                if config['custom_dimensions']:
                    # Handle both dict and list formats
                    custom_dims = config['custom_dimensions']
                    
                    # Handle JSONB as string
                    if isinstance(custom_dims, str):
                        import json
                        try:
                            custom_dims = json.loads(custom_dims)
                        except:
                            custom_dims = None
                    
                    if custom_dims:
                        if isinstance(custom_dims, dict):
                            # If it's a dict, check if it has actual dimension data
                            # Skip empty dicts {}
                            if custom_dims:
                                # Try to extract dimensions from dict values
                                for key, dim_data in custom_dims.items():
                                    if isinstance(dim_data, dict) and 'dimension_id' in dim_data:
                                        try:
                                            dimensions.append(dim_data)
                                        except Exception as e:
                                            logger.warning(f"Failed to parse custom dimension {key}: {e}")
                        elif isinstance(custom_dims, list):
                            # If it's a list, process normally
                            for dim in custom_dims:
                                if isinstance(dim, dict):
                                    try:
                                        dimensions.append(dim)
                                    except Exception as e:
                                        logger.warning(f"Failed to parse custom dimension: {e}")
        
            # CRITICAL FIX: Load Strategic Imperatives directly from generic_custom_dimensions table
            # This was missing and causing Strategic Imperatives to not be analyzed
            try:
                strategic_imperatives = await conn.fetch("""
                    SELECT dimension_id, name, description, ai_context, criteria, 
                           scoring_framework, metadata
                    FROM generic_custom_dimensions
                    WHERE (client_id = $1 OR client_id = 'default') AND is_active = true
                    ORDER BY created_at
                """, project_id or 'default')
                
                logger.info(f"Loading {len(strategic_imperatives)} Strategic Imperatives from generic_custom_dimensions")
                
                for si in strategic_imperatives:
                    if si['ai_context'] and si['criteria'] and si['scoring_framework']:
                        # Convert to generic dimension format
                        dimension = {
                            'dimension_id': si['dimension_id'],
                            'name': si['name'], 
                            'description': si['description'],
                            'ai_context': si['ai_context'],
                            'criteria': si['criteria'],
                            'scoring_framework': si['scoring_framework'],
                            'metadata': si['metadata'] or {},
                            'dimension_type': 'strategic_imperative'
                        }
                        dimensions.append(dimension)
                        logger.info(f"Added Strategic Imperative: {si['name']} ({si['dimension_id']})")
                    else:
                        logger.warning(f"Strategic Imperative {si['dimension_id']} missing required fields")
            except Exception as e:
                logger.error(f"Failed to load Strategic Imperatives from generic_custom_dimensions: {e}")
        
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
                # Handle competitors as either a list or a JSONB string
                competitors_data = project['competitors']
                if isinstance(competitors_data, str):
                    import json
                    try:
                        competitors_data = json.loads(competitors_data)
                    except:
                        competitors_data = []
                
                if isinstance(competitors_data, list):
                    for comp in competitors_data:
                        if isinstance(comp, dict):
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
    
    def _build_optimized_prompt(self, content: str, title: str, dimensions: List[Dict[str, Any]], company_info: Dict[str, Any] = None) -> str:
        """Build optimized prompt with reduced verbosity requirements"""
        # With GPT-4.1's 1M token window, we can analyze much more content
        # Approximately 4 chars = 1 token, so 200k chars ≈ 50k tokens (leaving room for prompt and response)
        content_preview = content[:200000]  # Increased from 10000 to leverage GPT-4.1's capabilities
        
        dimension_instructions = []
        for dim in dimensions:
            # Parse JSON strings if needed
            ai_context = dim.get('ai_context', {})
            if isinstance(ai_context, str):
                try:
                    ai_context = json.loads(ai_context)
                except (json.JSONDecodeError, TypeError):
                    ai_context = {}
            
            criteria = dim.get('criteria', {})
            if isinstance(criteria, str):
                try:
                    criteria = json.loads(criteria)
                except (json.JSONDecodeError, TypeError):
                    criteria = {}
            
            focus_areas = ai_context.get('key_focus_areas', []) if isinstance(ai_context, dict) else []
            focus = focus_areas[0] if focus_areas else dim.get('description', 'General analysis')
            positive_signals = criteria.get('positive_signals', [])[:3] if isinstance(criteria, dict) else []
            
            instruction = f"""
**{dim.get('name', 'Unknown')}** ({dim.get('dimension_type', 'custom')}):
Focus: {focus}
Look for: {', '.join(positive_signals) if positive_signals else 'Relevant signals'}
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
You are an expert B2B content analyst evaluating content relevance for specific business personas and buying journey stages.

{company_context}

CONTENT TO ANALYZE:
Title: {title}
Text: {content_preview}
{mention_section}
EVALUATION DIMENSIONS:
{chr(10).join(dimension_instructions)}

SCORING GUIDELINES:
- 0-2: No relevance - content doesn't address this dimension at all
- 3-4: Low relevance - minimal connection, mostly generic or tangential
- 5-6: Moderate relevance - some useful information but lacks depth or specificity
- 7-8: High relevance - directly addresses key concerns with specific solutions/evidence
- 9-10: Exceptional relevance - comprehensive coverage with unique insights/data

For each dimension, provide:
- score: 0-10 rating (be selective - reserve 7+ for truly relevant content)
- confidence: 0-10 certainty in your assessment
- key_evidence: Most compelling 1-2 sentences from content (quote or paraphrase specific details)
- primary_signals: Top 3 criteria met (use exact terms from positive signals when possible)
- score_factors: {{positive: [2-3 specific strengths], negative: [1-2 gaps or weaknesses]}}

Focus on SPECIFIC evidence from the content. Generic marketing language scores low. Detailed solutions, data, and outcomes score high.
"""
    
    async def _call_openai_optimized(self, prompt: str, dimensions: List[Dict[str, Any]], include_mentions: bool = False) -> Dict[str, Any]:
        """Call OpenAI with optimized schema"""
        # Build simplified schema
        dimension_properties = {}
        for i, dim in enumerate(dimensions):
            dimension_properties[dim.get('dimension_id', f'unknown_{i}')] = {
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
        
        # Retry logic for API timeouts
        max_retries = 3
        retry_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    headers = {
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    # Add project ID header if available
                    if self.openai_project_id:
                        headers["OpenAI-Project"] = self.openai_project_id
                    
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json={
                            "model": "gpt-4.1",  # Using GPT-4.1 with 1M token context window
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
                            "max_tokens": 2000  # Increased from 800 to allow for more comprehensive analysis
                        },
                        timeout=120.0  # Increased timeout for long content analysis
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
                    
                    break  # Success, exit retry loop
                    
            except httpx.ReadTimeout as e:
                if attempt < max_retries - 1:
                    logger.warning(f"OpenAI API timeout (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger.error(f"OpenAI API timeout after {max_retries} attempts")
                    raise Exception(f"OpenAI API timeout after {max_retries} attempts: {str(e)}")
            except Exception as e:
                # For non-timeout errors, don't retry
                logger.error(f"OpenAI API error: {str(e)}")
                raise
        
        # Process the response after successful API call
        try:
            result = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            logger.error(f"Raw response: {response.text[:500]}")
            raise
        
        # Log the response structure for debugging
        logger.debug(f"OpenAI response structure: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        
        # Extract result from the chat completions format
        if isinstance(result, dict) and result.get('choices') and len(result['choices']) > 0:
            choice = result['choices'][0]
            if isinstance(choice, dict) and choice.get('message') and isinstance(choice['message'], dict):
                message = choice['message']
                if message.get('tool_calls') and isinstance(message['tool_calls'], list) and len(message['tool_calls']) > 0:
                    tool_call = message['tool_calls'][0]
                    if isinstance(tool_call, dict) and tool_call.get('function') and isinstance(tool_call['function'], dict):
                        function = tool_call['function']
                        if function.get('arguments'):
                            try:
                                parsed_args = json.loads(function['arguments'])
                                return parsed_args
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse function arguments: {e}")
                                logger.error(f"Raw arguments: {function['arguments'][:500]}")
                                raise
        
        # If we get here, the response wasn't in the expected format
        logger.error(f"Unexpected OpenAI response format: {json.dumps(result)[:500] if isinstance(result, dict) else str(result)[:500]}")
        raise Exception("No tool call in OpenAI response")
    
    def _parse_optimized_response(self, ai_response: Dict[str, Any], dimensions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse optimized AI response"""
        dimension_results = {}
        
        # Handle None response from OpenAI API
        if ai_response is None:
            logger.warning("OpenAI API returned None response, using default values")
            ai_response = {"dimensions": {}}
        
        # Ensure ai_response is a dictionary
        if not isinstance(ai_response, dict):
            logger.warning(f"OpenAI API returned {type(ai_response)} instead of dict, using default values")
            ai_response = {"dimensions": {}}
        
        for dim in dimensions:
            if dim.get('dimension_id') in ai_response.get('dimensions', {}):
                dim_id = dim.get('dimension_id')
                dim_result = ai_response['dimensions'][dim_id]
                
                # Ensure all required fields with defaults
                dimension_results[dim_id] = {
                    "dimension_name": dim.get('name', 'Unknown'),
                    "dimension_type": dim.get('dimension_type', 'custom'),
                    "score": dim_result.get("score", 0),
                    "confidence": dim_result.get("confidence", 0),
                    "key_evidence": dim_result.get("key_evidence", "No specific evidence found"),
                    "primary_signals": dim_result.get("primary_signals", []),
                    "score_factors": dim_result.get("score_factors", {"positive": [], "negative": []}),
                    "metadata": dim.get('metadata', {})
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
        if not project_id or 'dimensions' not in result:
            return result
            
        async with self.db.acquire() as conn:
            # Get all active dimension groups
            groups = await conn.fetch("""
                SELECT DISTINCT 
                    dg.id,
                    dg.group_id,
                    dg.name,
                    dg.selection_strategy,
                    dg.max_primary_dimensions
                FROM dimension_groups dg
                WHERE dg.is_active = TRUE
                ORDER BY dg.display_order
            """)
            
            if not groups:
                # No groups defined, return as-is
                return result
            
            primary_dimensions = {}
            
            for group in groups:
                # Get dimensions in this group that were analyzed
                group_dimension_scores = await conn.fetch("""
                    SELECT 
                        dgm.dimension_id,
                        dgm.priority
                    FROM dimension_group_members dgm
                    WHERE dgm.group_id = $1
                    AND dgm.dimension_id = ANY($2)
                """, group['id'], list(result['dimensions'].keys()))
                
                if not group_dimension_scores:
                    continue
                
                # Get scored dimensions for this group
                scored_dims = []
                for dim_member in group_dimension_scores:
                    dim_id = dim_member['dimension_id']
                    if dim_id in result['dimensions']:
                        dim_data = result['dimensions'][dim_id]
                        scored_dims.append({
                            'dimension_id': dim_id,
                            'score': dim_data.get('score', 0),
                            'confidence': dim_data.get('confidence', 0),
                            'evidence_count': len(dim_data.get('primary_signals', [])),
                            'priority': dim_member['priority']
                        })
                
                if not scored_dims:
                    continue
                
                # Select primary dimension(s) based on strategy
                strategy = group['selection_strategy']
                max_primary = group['max_primary_dimensions'] or 1
                
                if strategy == 'highest_score':
                    scored_dims.sort(key=lambda x: x['score'], reverse=True)
                elif strategy == 'highest_confidence':
                    scored_dims.sort(key=lambda x: x['confidence'], reverse=True)
                elif strategy == 'most_evidence':
                    scored_dims.sort(key=lambda x: x['evidence_count'], reverse=True)
                elif strategy == 'manual':
                    scored_dims.sort(key=lambda x: x['priority'])
                else:  # Default to highest score
                    scored_dims.sort(key=lambda x: x['score'], reverse=True)
                
                # Select top dimension(s) based on max_primary_dimensions
                selected = scored_dims[:max_primary]
                
                # Store primary dimension(s) for this group
                if len(selected) == 1:
                    primary_dimensions[group['group_id']] = selected[0]['dimension_id']
                else:
                    primary_dimensions[group['group_id']] = [dim['dimension_id'] for dim in selected]
                
                # Mark dimensions as primary in the result
                for dim in selected:
                    if dim['dimension_id'] in result['dimensions']:
                        result['dimensions'][dim['dimension_id']]['is_primary'] = True
                        result['dimensions'][dim['dimension_id']]['group_id'] = group['group_id']
            
            result['primary_dimensions'] = primary_dimensions
            
        return result
    
    async def _store_optimized_analysis(self, url: str, result: Dict[str, Any], project_id: Optional[str]) -> None:
        """Store optimized analysis results"""
        async with self.db.acquire() as conn:
            async with conn.transaction():
                # Check if analysis already exists (for fresh analysis mode)
                existing_analysis = await conn.fetchval("""
                    SELECT id FROM optimized_content_analysis WHERE url = $1
                """, url)
                
                if existing_analysis:
                    # Update existing analysis
                    logger.debug(f"Updating existing analysis for {url}")
                    analysis_id = await conn.fetchval("""
                        UPDATE optimized_content_analysis 
                        SET overall_insights = $2, analyzer_version = $3, analyzed_at = $4,
                            mentions = $5, overall_sentiment = $6, key_topics = $7,
                            project_id = $8
                        WHERE url = $1
                        RETURNING id
                    """, 
                        url,
                        result['overall_insights'],
                        result['analyzer_version'],
                        datetime.fromisoformat(result['analyzed_at']),
                        json.dumps(result.get('mentions', [])),
                        result.get('overall_sentiment'),
                        json.dumps(result.get('key_topics', [])),
                        project_id
                    )
                    
                    # Clear existing dimension analyses for this content
                    await conn.execute("""
                        DELETE FROM optimized_dimension_analysis WHERE analysis_id = $1
                    """, analysis_id)
                    
                else:
                    # Insert new analysis
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
                    for group_id, primary_dim_ids in result['primary_dimensions'].items():
                        # Get the actual group UUID from group_id
                        group_uuid = await conn.fetchval("""
                            SELECT id FROM dimension_groups WHERE group_id = $1
                        """, group_id)
                        
                        if group_uuid:
                            # Handle both single dimension and list of dimensions
                            if isinstance(primary_dim_ids, list):
                                for dim_id in primary_dim_ids:
                                    dim_data = result['dimensions'].get(dim_id, {})
                                    await conn.execute("""
                                        INSERT INTO analysis_primary_dimensions (
                                            analysis_id, group_id, dimension_id, 
                                            selection_reason, selection_score, project_id
                                        ) VALUES ($1, $2, $3, $4, $5, $6)
                                        ON CONFLICT (analysis_id, group_id) DO UPDATE SET
                                            dimension_id = EXCLUDED.dimension_id,
                                            selection_reason = EXCLUDED.selection_reason,
                                            selection_score = EXCLUDED.selection_score
                                    """, analysis_id, group_uuid, dim_id, 
                                        f"Selected by {group_id} group strategy",
                                        dim_data.get('score', 0), project_id)
                            else:
                                dim_data = result['dimensions'].get(primary_dim_ids, {})
                                await conn.execute("""
                                    INSERT INTO analysis_primary_dimensions (
                                        analysis_id, group_id, dimension_id, 
                                        selection_reason, selection_score, project_id
                                    ) VALUES ($1, $2, $3, $4, $5, $6)
                                    ON CONFLICT (analysis_id, group_id) DO UPDATE SET
                                        dimension_id = EXCLUDED.dimension_id,
                                        selection_reason = EXCLUDED.selection_reason,
                                        selection_score = EXCLUDED.selection_score
                                """, analysis_id, group_uuid, primary_dim_ids, 
                                    f"Selected by {group_id} group strategy",
                                    dim_data.get('score', 0), project_id)
    
    def _persona_to_generic(self, persona: Dict[str, Any]) -> Dict[str, Any]:
        """Convert persona to generic dimension format"""
        # Generate ID from name if not present
        persona_id = persona.get('id', persona.get('name', 'unknown').lower().replace(' ', '_'))
        return {
            "dimension_id": f"persona_{persona_id}",
            "name": persona.get('name', 'Unknown Persona'),
            "dimension_type": "persona",
            "description": persona.get('description', ''),
            "ai_context": {
                "purpose": f"Evaluate content relevance for {persona.get('name', 'Unknown')} persona",
                "scope": "B2B buyer persona alignment",
                "key_focus_areas": [
                    f"Pain points: {', '.join(persona.get('pain_points', [])[:2])}",
                    f"Goals: {', '.join(persona.get('goals', [])[:2])}",
                    f"Role: {persona.get('role', 'Business decision maker')}"
                ]
            },
            "criteria": {
                "what_counts": f"Content addressing {persona.get('name', 'Unknown')}'s specific needs and challenges",
                "positive_signals": persona.get('keywords', [])[:5],
                "negative_signals": ["Generic content", "Irrelevant to role"],
                "exclusions": ["Consumer-focused content"]
            },
            "scoring_framework": {
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
            "metadata": {"original_type": "persona", "persona_id": persona_id}
        }
    
    def _jtbd_to_generic(self, phase: Dict[str, Any]) -> Dict[str, Any]:
        """Convert JTBD phase to generic dimension format"""
        # Generate ID from name if not present
        phase_id = phase.get('id', phase.get('name', 'unknown').lower().replace(' ', '_'))
        return {
            "dimension_id": f"jtbd_{phase_id}",
            "name": phase.get('name', 'Unknown Phase'),
            "dimension_type": "jtbd_phase",
            "description": phase.get('description', ''),
            "ai_context": {
                "purpose": f"Assess content alignment with {phase.get('name', 'Unknown')} phase",
                "scope": "B2B buying journey stage",
                "key_focus_areas": phase.get('focus_areas', [])
            },
            "criteria": {
                "what_counts": f"Content supporting buyers in {phase.get('name', 'Unknown')}",
                "positive_signals": phase.get('content_themes', [])[:5],
                "negative_signals": ["Wrong stage content", "Premature selling"],
                "exclusions": ["Unrelated journey stages"]
            },
            "scoring_framework": {
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
            "metadata": {"original_type": "jtbd", "phase_id": phase_id}
        }
    
    def _page_type_to_generic(self, page_type: Dict[str, Any]) -> Dict[str, Any]:
        """Convert page type to generic dimension format"""
        # Generate ID from name if not present
        page_type_id = page_type.get('id', page_type.get('name', 'unknown').lower().replace(' ', '_'))
        return {
            "dimension_id": f"page_type_{page_type_id}",
            "name": f"Page Type: {page_type.get('name', 'Unknown')}",
            "dimension_type": "page_classification",
            "description": page_type.get('description', ''),
            "ai_context": {
                "purpose": f"Identify if content matches {page_type.get('name', 'Unknown')} page type",
                "scope": "B2B website page classification",
                "key_focus_areas": [
                    "Page structure and layout patterns",
                    "Content purpose and conversion focus",
                    f"Category: {page_type.get('category', 'General')}",
                    f"Buyer stage: {page_type.get('buyer_journey_stage', 'Multiple')}"
                ]
            },
            "criteria": {
                "what_counts": f"Content matching {page_type.get('name', 'Unknown')} characteristics",
                "positive_signals": page_type.get('indicators', []),
                "negative_signals": ["Wrong page type indicators", "Misaligned purpose"],
                "exclusions": ["Non-B2B content", "Unrelated page types"]
            },
            "scoring_framework": {
                "levels": [
                    {"range": [0, 3], "label": "No Match", "description": "Not this page type"},
                    {"range": [4, 6], "label": "Partial", "description": "Some characteristics present"},
                    {"range": [7, 10], "label": "Strong Match", "description": "Clear page type match"}
                ],
                "evidence_requirements": {
                    "min_indicators": 2,
                    "structural_weight": 0.5,
                    "content_weight": 0.5
                }
            },
            "metadata": {
                "original_type": "page_type", 
                "page_id": page_type_id,
                "category": page_type.get('category', ''),
                "buyer_stage": page_type.get('buyer_journey_stage', '')
            }
        }
