"""
Enhanced Content Analyzer Service - AI-powered content analysis using GPT-4
Addresses critical requirements:
1. AI-powered mention sentiment analysis (not just keyword matching)
2. Full JTBD phase context in analysis
3. Comprehensive persona context
4. AI-based source company identification
5. Proper competitor tracking and analysis
"""
import json
import hashlib
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID, uuid4

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.core.database import DatabasePool
from app.models.content_analysis import (
    ContentAnalysisRequest,
    BatchAnalysisRequest,
    ContentAnalysisResult,
    AnalysisConfig,
    ClientAnalysisConfig,
    AnalysisJob,
    Mention,
    Sentiment,
    ContentClassification,
    SourceType,
    Persona,
    JTBDPhase
)
from app.services.scraping.web_scraper import WebScraper
from app.services.enrichment.company_enricher import CompanyEnricher
from app.services.analysis.prompt_manager import PromptManager


class ContentAnalyzer:
    """AI-powered content analysis service"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        self.openai_api_key = settings.openai_api_key
        
        # Initialize dependencies
        self.web_scraper = WebScraper(settings=settings, db=db)
        self.company_enricher = CompanyEnricher(settings=settings, db=db)
        self.prompt_manager = PromptManager(db=db)
        
        # OpenAI API configuration
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        # Rate limiting
        self._semaphore = asyncio.Semaphore(settings.content_analyzer_concurrent_limit or 5)
    
    async def analyze_content(
        self,
        request: ContentAnalysisRequest
    ) -> Optional[ContentAnalysisResult]:
        """Analyze a single piece of content"""
        async with self._semaphore:
            try:
                # Check if already analyzed
                if not request.force_reanalyze:
                    existing = await self._get_existing_analysis(
                        request.client_id, request.url
                    )
                    if existing:
                        logger.info(f"Returning cached analysis for {request.url}")
                        return existing
                
                # Get content if not provided
                content = request.content
                title = ""  # Default title
                
                if not content:
                    logger.info(f"Scraping content from {request.url}")
                    
                    # Determine if we need to force ScrapingBee for protected sites
                    from urllib.parse import urlparse
                    parsed = urlparse(request.url)
                    domain = parsed.netloc.lower()
                    protected_domains = ['openai.com', 'linkedin.com', 'facebook.com', 'twitter.com']
                    force_scrapingbee = any(d in domain for d in protected_domains)
                    
                    scrape_result = await self.web_scraper.scrape(
                        request.url,
                        use_javascript=True,
                        force_scrapingbee=force_scrapingbee
                    )
                    if not scrape_result.get('success'):
                        raise Exception(f"Failed to scrape: {scrape_result.get('error')}")
                    content = scrape_result.get('content', '')
                    title = scrape_result.get("title", "")
                
                if not content:
                    raise Exception("No content to analyze")
                
                # Get enhanced client configuration with competitor info
                config = await self._get_enhanced_client_config(request.client_id)
                if request.custom_config:
                    # Merge custom config
                    config = self._merge_configs(config, request.custom_config)
                
                # Generate content asset ID
                content_asset_id = self._generate_content_id(request.url, content)
                
                # Store scraped content in database
                async with self.db.acquire() as conn:
                    from urllib.parse import urlparse
                    domain = urlparse(request.url).netloc
                    
                    await conn.execute(
                        """
                        INSERT INTO scraped_content (
                            content_asset_id, url, domain, title, 
                            content, word_count, scraped_at, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (content_asset_id) DO UPDATE SET
                            content = EXCLUDED.content,
                            word_count = EXCLUDED.word_count,
                            scraped_at = EXCLUDED.scraped_at,
                            status = EXCLUDED.status
                        """,
                        str(content_asset_id),  # Convert UUID to string
                        request.url,
                        domain,
                        title,
                        content,
                        len(content.split()),
                        datetime.utcnow(),
                        'completed'
                    )
                
                # Get prompt configuration
                prompt_config = await self.prompt_manager.get_or_create_default_config(request.client_id)
                
                # Phase 1: Analyze with GPT-4 (main analysis with enhanced context)
                analysis = await self._analyze_with_gpt4_enhanced(
                    content=content[:config.max_content_length],
                    config=config,
                    url=request.url,
                    prompt_config=prompt_config
                )
                
                # Phase 2: AI-powered source identification (not pattern matching)
                source_info = await self._identify_source_with_ai(
                    url=request.url,
                    content=content[:2000],  # First 2000 chars for source ID
                    client_id=request.client_id
                )
                
                # Phase 3: Extract and analyze mentions with AI
                brand_mentions = []
                competitor_mentions = []
                
                if config.enable_mention_extraction:
                    client_domains = await self._get_client_domains(request.client_id)
                    
                    # Extract mentions first
                    brand_mention_contexts = self._extract_mention_contexts(content, client_domains)
                    competitor_mention_contexts = self._extract_mention_contexts(content, config.competitor_domains)
                    
                    # Analyze mentions with AI for sentiment and context
                    if brand_mention_contexts:
                        brand_mentions = await self._analyze_mentions_with_ai(
                            brand_mention_contexts, 
                            is_brand=True
                        )
                    
                    if competitor_mention_contexts:
                        competitor_mentions = await self._analyze_mentions_with_ai(
                            competitor_mention_contexts,
                            is_brand=False
                        )
                
                # Create result with all enhanced data
                # Ensure we have persona scores - use fallback if not provided
                persona_scores = analysis.get('persona_scores', {})
                if not persona_scores and config.personas:
                    # Fallback: Create default scores based on primary persona
                    primary_persona = analysis.get('primary_persona', '')
                    persona_scores = {}
                    for persona in config.personas:
                        if persona.name == primary_persona:
                            persona_scores[persona.name] = 0.8  # High score for primary
                        else:
                            persona_scores[persona.name] = 0.2  # Low score for others
                    logger.warning(f"AI did not return persona_scores, using fallback scores: {persona_scores}")
                
                result = ContentAnalysisResult(
                    id=uuid4(),
                    client_id=request.client_id,
                    content_asset_id=content_asset_id,
                    url=request.url,
                    summary=analysis.get('summary', ''),
                    content_classification=ContentClassification(
                        analysis.get('content_classification', 'OTHER')
                    ),
                    primary_persona=analysis.get('primary_persona', ''),
                    persona_alignment_scores=persona_scores,
                    jtbd_phase=analysis.get('jtbd_phase', ''),
                    jtbd_alignment_score=analysis.get('jtbd_alignment_score', 0.0),
                    custom_dimensions=analysis.get('custom_dimensions', {}),
                    key_topics=analysis.get('key_topics', []),
                    sentiment=Sentiment(analysis.get('sentiment', 'neutral')),
                    confidence_scores=analysis.get('confidence_scores', {}),
                    brand_mentions=brand_mentions,
                    competitor_mentions=competitor_mentions,
                    source_type=SourceType(source_info.get('type', 'other')),
                    source_company_id=source_info.get('company_id'),
                    source_company_name=source_info.get('company_name'),
                    source_company_industry=source_info.get('industry'),
                    source_company_description=source_info.get('description'),
                    source_identification_reasoning=source_info.get('reasoning'),
                    analyzed_at=datetime.utcnow(),
                    analysis_version="2.0",  # Enhanced version
                    model_used=prompt_config.model_override if prompt_config and prompt_config.model_override else "gpt-4.1-2025-04-14"
                )
                
                # Store result
                await self._store_analysis(result)
                
                return result
                
            except Exception as e:
                logger.error(f"Analysis failed for {request.url}: {str(e)}")
                raise
    
    async def analyze_batch(
        self,
        request: BatchAnalysisRequest
    ) -> AnalysisJob:
        """Analyze multiple URLs in batch"""
        # Create job
        job = AnalysisJob(
            id=uuid4(),
            client_id=request.client_id,
            status='processing',
            total_urls=len(request.urls),
            processed=0,
            successful=0,
            failed=0,
            error_details=[],
            started_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        
        # Store job
        await self._store_job(job)
        
        # Process in background
        asyncio.create_task(self._process_batch_analysis(job, request))
        
        return job
    
    async def _process_batch_analysis(
        self,
        job: AnalysisJob,
        request: BatchAnalysisRequest
    ):
        """Process batch analysis in background"""
        try:
            for url in request.urls:
                try:
                    # Analyze single URL
                    single_request = ContentAnalysisRequest(
                        client_id=request.client_id,
                        url=url,
                        force_reanalyze=request.force_reanalyze,
                        custom_config=request.custom_config
                    )
                    
                    await self.analyze_content(single_request)
                    job.successful += 1
                    
                except Exception as e:
                    logger.error(f"Failed to analyze {url}: {str(e)}")
                    job.failed += 1
                    job.error_details.append({
                        'url': url,
                        'error': str(e)
                    })
                
                job.processed += 1
                await self._update_job(job)
            
            # Mark complete
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            await self._update_job(job)
            
        except Exception as e:
            logger.error(f"Batch analysis failed: {str(e)}")
            job.status = 'failed'
            job.completed_at = datetime.utcnow()
            await self._update_job(job)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _analyze_with_gpt4_enhanced(
        self,
        content: str,
        config: AnalysisConfig,
        url: str,
        prompt_config = None
    ) -> Dict[str, Any]:
        """Analyze content using GPT-4 with enhanced context"""
        
        # Use prompt configuration if provided, otherwise fall back to built-in
        if prompt_config:
            prompts = await self._build_prompt_from_config(
                content, config, url, prompt_config
            )
            system_prompt = prompts["system"]
            user_prompt = prompts["user"]
        else:
            # Fall back to built-in prompt builder
            user_prompt = self._build_enhanced_analysis_prompt(content, config, url)
            system_prompt = "You are an expert B2B content analyst specializing in buyer journey mapping, persona alignment, and Jobs to be Done framework. Analyze content with deep understanding of B2B buying processes."
        
        # Define the enhanced function schema
        function_schema = {
            "name": "analyze_content",
            "description": "Analyze B2B content with deep persona and JTBD insights",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Comprehensive summary of the content (3-4 sentences)"
                    },
                    "content_classification": {
                        "type": "string",
                        "description": "Content category based on buyer journey stage",
                        "enum": ["ATTRACT", "LEARN", "CONVERT/TRY", "BUY", "OTHER"]
                    },
                    "primary_persona": {
                        "type": "string",
                        "description": "Primary target persona name from the configured list"
                    },
                    "persona_scores": {
                        "type": "object",
                        "description": "Score for each persona (0.0 to 1.0). REQUIRED: Include a score for ALL three personas",
                        "properties": {
                            "C-Suite Executive": {"type": "number", "minimum": 0, "maximum": 1, "description": "Relevance score for C-Suite Executive (0.0-1.0)"},
                            "IT Leader": {"type": "number", "minimum": 0, "maximum": 1, "description": "Relevance score for IT Leader (0.0-1.0)"},
                            "Banking Operations Leader": {"type": "number", "minimum": 0, "maximum": 1, "description": "Relevance score for Banking Operations Leader (0.0-1.0)"}
                        },
                        "required": ["C-Suite Executive", "IT Leader", "Banking Operations Leader"]
                    },
                    "jtbd_phase": {
                        "type": "string",
                        "description": "Primary Jobs to be Done phase name - must be the exact phase name from the list provided",
                        "enum": ["Problem Identification", "Solution Exploration", "Requirements Building", "Supplier Selection", "Validation", "Consensus Creation"]
                    },
                    "jtbd_alignment_score": {
                        "type": "number",
                        "description": "JTBD phase alignment score (0-1)",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "custom_dimensions": {
                        "type": "object",
                        "description": "Values for custom dimensions",
                        "additionalProperties": {"type": "string"}
                    },
                    "key_topics": {
                        "type": "array",
                        "description": "Key topics covered (5-7 topics)",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 7
                    },
                    "sentiment": {
                        "type": "string",
                        "description": "Overall content sentiment",
                        "enum": ["positive", "negative", "neutral"]
                    },

                    "confidence_scores": {
                        "type": "object",
                        "description": "Confidence levels (0-10) for each analysis dimension",
                        "properties": {
                            "persona_scores": {
                                "type": "object",
                                "description": "Confidence score for each persona (0-10)",
                                "additionalProperties": {"type": "number", "minimum": 0, "maximum": 10}
                            },
                            "jtbd_phase": {
                                "type": "number",
                                "description": "Confidence in JTBD phase classification (0-10)",
                                "minimum": 0,
                                "maximum": 10
                            },
                            "source_classification": {
                                "type": "number",
                                "description": "Confidence in source type classification (0-10)",
                                "minimum": 0,
                                "maximum": 10
                            },
                            "sentiment": {
                                "type": "number",
                                "description": "Confidence in sentiment analysis (0-10)",
                                "minimum": 0,
                                "maximum": 10
                            },
                            "custom_dimensions": {
                                "type": "object",
                                "description": "Confidence scores for custom dimension values (0-10)",
                                "additionalProperties": {"type": "number", "minimum": 0, "maximum": 10}
                            },
                            "overall": {
                                "type": "number",
                                "description": "Overall confidence in the analysis (0-10)",
                                "minimum": 0,
                                "maximum": 10
                            }
                        },
                        "required": ["persona_scores", "jtbd_phase", "source_classification", "sentiment", "custom_dimensions", "overall"]
                    }
                },
                "required": [
                    "summary", "content_classification", "primary_persona",
                    "persona_scores", "jtbd_phase", 
                    "jtbd_alignment_score", "key_topics", "sentiment",
                    "confidence_scores"
                ]
            }
        }
        
        # Prepare request payload
        request_payload = {
            "model": prompt_config.model_override if prompt_config and prompt_config.model_override else "gpt-4.1-2025-04-14",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": user_prompt
                }
            ],
            "tools": [{
                "type": "function",
                "function": function_schema
            }],
            "tool_choice": {"type": "function", "function": {"name": "analyze_content"}},
            "temperature": prompt_config.temperature_override if prompt_config and prompt_config.temperature_override else config.temperature,
            "max_tokens": prompt_config.max_tokens_override if prompt_config and prompt_config.max_tokens_override else 4000
        }
        
        # Log the full request for debugging
        logger.info(f"OpenAI Request Payload: {json.dumps(request_payload, indent=2)}")
        
        # Make API call
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=request_payload
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            result = response.json()
            
            # Log the full response for debugging
            logger.info(f"Full OpenAI response: {json.dumps(result, indent=2)}")
            
            # Extract tool call arguments (new format)
            tool_calls = result["choices"][0]["message"].get("tool_calls")
            if not tool_calls or len(tool_calls) == 0:
                # Fallback to old function_call format
                function_call = result["choices"][0]["message"].get("function_call")
                if not function_call:
                    raise Exception("No tool call or function call in response")
                analysis = json.loads(function_call["arguments"])
            else:
                # Use new tool_calls format
                analysis = json.loads(tool_calls[0]["function"]["arguments"])
            
            # Debug logging for persona scores
            logger.info(f"AI Response - persona_scores: {analysis.get('persona_scores', 'NOT FOUND')}")
            logger.info(f"AI Response - all keys: {list(analysis.keys())}")
            
            return analysis
    
    def _build_enhanced_analysis_prompt(
        self,
        content: str,
        config: AnalysisConfig,
        url: str
    ) -> str:
        """Build enhanced analysis prompt with full context"""
        
        # Format personas with full context
        logger.info(f"Loading personas: {[p.name for p in config.personas]}")
        persona_text = "\n\n".join([
            f"**{p.name}**\n"
            f"- Description: {p.description}\n"
            f"- Title/Role: {p.title or 'N/A'}\n"
            f"- Goals: {', '.join(p.goals) if p.goals else 'N/A'}\n"
            f"- Pain Points: {', '.join(p.pain_points) if p.pain_points else 'N/A'}\n"
            f"- Decision Criteria: {', '.join(p.decision_criteria) if p.decision_criteria else 'N/A'}\n"
            f"- Content Preferences: {', '.join(p.content_preferences) if p.content_preferences else 'N/A'}"
            for p in config.personas
        ])
        
        # Format JTBD phases with full context
        jtbd_text = ""
        if config.jtbd_phases:
            if isinstance(config.jtbd_phases[0], JTBDPhase):
                # Rich JTBDPhase objects
                jtbd_text = "\n\n".join([
                    f"**{phase.name}**\n"
                    f"- Description: {phase.description}\n"
                    f"- Buyer Mindset: {phase.buyer_mindset}\n"
                    f"- Key Questions: {', '.join(phase.key_questions) if phase.key_questions else 'N/A'}\n"
                    f"- Effective Content Types: {', '.join(phase.content_types) if phase.content_types else 'N/A'}"
                    for phase in config.jtbd_phases
                ])
            elif isinstance(config.jtbd_phases[0], dict):
                # Dictionary format from database with name and description
                jtbd_text = "\n\n".join([
                    f"**{phase['name']}**\n"
                    f"- Description: {phase['description']}"
                    for phase in config.jtbd_phases
                ])
            else:
                # Legacy string format - just list names
                jtbd_text = "\n".join([f"- {phase}" for phase in config.jtbd_phases])
        
        # Format content categories
        category_text = "\n".join([
            f"- **{key}**: {value}"
            for key, value in config.content_categories.items()
        ])
        
        # Format custom dimensions
        dimensions_text = ""
        if config.custom_dimensions:
            dimensions_text = "\n\n## CUSTOM DIMENSIONS TO EVALUATE:\n" + "\n".join([
                f"- **{key}**: Choose from: {', '.join(values)}"
                for key, values in config.custom_dimensions.items()
            ])
        
        # Custom instructions are now used as buyer context at the beginning
        
        # Build buyer context from config
        buyer_context = ""
        if config.custom_prompt_instructions:
            buyer_context = f"""## BUYER CONTEXT:
{config.custom_prompt_instructions}

"""
        
        prompt = f"""Analyze this B2B content from: {url}

## CRITICAL INSTRUCTION: NEUTRAL ANALYSIS
This is a digital landscape analysis to understand ALL content influencing buyers in this solution space.
- Score ALL content based on relevance to buyers, regardless of source
- Competitor content addressing the same buyer needs should score HIGH (0.6-1.0)
- This analysis maps the ENTIRE competitive landscape - not biased toward any vendor
- The goal is to understand digital share of influence across ALL companies

## CRITICAL: You MUST include persona_scores in your response
The persona_scores field is REQUIRED. It must be an object with a score (0.0-1.0) for EACH persona.
Example: "persona_scores": {{"CTO/IT Security Leader": 0.7, "Banking Operations Leader": 0.4, "C-Suite Executive": 0.3}}

{buyer_context}## TARGET PERSONAS:
{persona_text}

**IMPORTANT**: Provide a score (0.0-1.0) for EACH persona: {', '.join([p.name for p in config.personas])}

## JOBS TO BE DONE PHASES (identify primary phase):

{jtbd_text}

## CONTENT CATEGORIES (classify into one):

{category_text}
{dimensions_text}

## ANALYSIS REQUIREMENTS:

1. **Summary**: Provide a comprehensive 3-4 sentence summary capturing the main value proposition and key insights.

2. **Persona Scores** (REQUIRED - MUST include in your response): 
   Score how relevant this content is for EACH persona (0.0 to 1.0).
   You MUST return a score for ALL personas listed above.
   Format EXACTLY as: {"CTO/IT Security Leader": 0.7, "Banking Operations Leader": 0.4, ...}
   DO NOT SKIP THIS FIELD!
   
   **SCORING GUIDE:**
   - **0.0-0.2**: NOT for these personas
     * Wrong audience (employees, consumers, etc.)
     * Different industry focus
     * Irrelevant role or concerns
   - **0.2-0.4**: WEAKLY aligned
     * Same general role, different context
     * Tangentially related concerns
   - **0.4-0.6**: MODERATELY aligned
     * Addresses relevant pain points for this persona
     * Right role, relevant to their evaluation criteria
   - **0.6-0.8**: HIGHLY aligned
     * Clearly targets these specific buyer types
     * Directly addresses their solution evaluation needs
     * Competitor content targeting same personas (SCORE HIGH!)
   - **0.8-1.0**: PERFECT match
     * Exactly what this persona needs for evaluation
     * Direct solution information from ANY vendor
   
   **IMPORTANT: Content from competitors targeting same personas should score HIGH**

3. **JTBD Phase Identification (Score based on BUYER JOURNEY relevance)**:
   ⚠️ **CRITICAL: Score based on relevance to buyers evaluating solutions in this space**
   
   - Ask: "Would someone evaluating solutions in this category find this valuable?"
   - Score ALL relevant content fairly - whether from client, competitors, or third parties
   - This is about understanding the ENTIRE digital landscape influencing buyers
   
   **NEUTRAL SCORING RUBRIC:**
   - **0.0-0.2**: IRRELEVANT to this solution category
     * HR/benefits/employee topics (unless about operational efficiency) 
     * General news unrelated to this solution space
     * Content about unrelated industries/solutions
   - **0.2-0.4**: WEAKLY relevant
     * Tangentially related to the solution category
     * General industry trends without specific relevance
   - **0.4-0.6**: MODERATELY relevant
     * Addresses buyer concerns in this solution space
     * Helps understand problems these solutions solve
   - **0.6-0.8**: HIGHLY relevant
     * Directly addresses buyer needs for this type of solution
     * Product comparisons, implementation guides, use cases
     * Competitor solutions addressing same buyer needs (SCORE HIGH!)
   - **0.8-1.0**: PERFECT match
     * Exactly what buyers need when evaluating these solutions
     * Direct product information from ANY vendor in this space
     * Comparative analyses, selection criteria
   
   **IMPORTANT: Competitor content about similar solutions should score HIGH (0.6-1.0)**

4. **Buyer Intent Signals**: Identify specific phrases or sections that indicate buyer intent

5. **Content Classification**: Classify based on where it fits in the buyer journey

6. **Key Topics**: Extract 5-7 main topics or themes

7. **Sentiment**: Analyze overall tone and sentiment
   - Consider the full context, not just keywords
   - Positive: Solution-focused, success stories, benefits emphasized
   - Negative: Problem-focused, challenges, criticisms, limitations
   - Neutral: Factual, balanced, educational without bias
   - DO NOT rely on simple keyword matching

8. **Confidence Scores (0-10)**: For each analysis dimension, provide confidence scores:
   - **persona_scores**: Rate confidence for each persona score (0-10)
     * 9-10: Clear, explicit persona targeting with multiple strong indicators
     * 7-8: Good evidence with some clear persona markers
     * 5-6: Moderate evidence, some ambiguity
     * 3-4: Limited evidence, mostly inferential
     * 0-2: Very little evidence, highly uncertain
   - **JTBD Phase**: Rate confidence in phase classification (0-10)
     * 9-10: Content explicitly matches phase characteristics
     * 7-8: Strong alignment with phase indicators
     * 5-6: Moderate fit, could apply to adjacent phases
     * 3-4: Weak indicators, significant ambiguity
     * 0-2: Very unclear phase alignment
   - **Source Classification**: Rate confidence in source type (0-10)
   - **Sentiment**: Rate confidence in sentiment analysis (0-10)
   - **Custom Dimensions**: Rate confidence for each dimension value (0-10)
   - **Overall**: Provide an overall confidence score for the entire analysis (0-10)

## CONTENT TO ANALYZE:

{content}

Provide deep, actionable insights focused on B2B buying behavior and decision-making processes."""
        
        return prompt
    
    async def _build_prompt_from_config(
        self,
        content: str,
        config: AnalysisConfig,
        url: str,
        prompt_config
    ) -> Dict[str, str]:
        """Build prompts using prompt configuration"""
        
        # Format personas text
        personas_text = "\n\n".join([
            f"**{p.name}**\n"
            f"- Description: {p.description}\n"
            f"- Title/Role: {p.title or 'N/A'}\n"
            f"- Goals: {', '.join(p.goals) if p.goals else 'N/A'}\n"
            f"- Pain Points: {', '.join(p.pain_points) if p.pain_points else 'N/A'}\n"
            f"- Decision Criteria: {', '.join(p.decision_criteria) if p.decision_criteria else 'N/A'}\n"
            f"- Content Preferences: {', '.join(p.content_preferences) if p.content_preferences else 'N/A'}"
            for p in config.personas
        ])
        
        # Format JTBD phases text
        jtbd_text = ""
        if config.jtbd_phases:
            if isinstance(config.jtbd_phases[0], JTBDPhase):
                jtbd_text = "\n\n".join([
                    f"**{phase.name}**\n"
                    f"- Description: {phase.description}\n"
                    f"- Buyer Mindset: {phase.buyer_mindset}\n"
                    f"- Key Questions: {', '.join(phase.key_questions) if phase.key_questions else 'N/A'}\n"
                    f"- Effective Content Types: {', '.join(phase.content_types) if phase.content_types else 'N/A'}"
                    for phase in config.jtbd_phases
                ])
            elif isinstance(config.jtbd_phases[0], dict):
                # Dictionary format from database with name and description
                jtbd_text = "\n\n".join([
                    f"**{phase['name']}**\n"
                    f"- Description: {phase['description']}"
                    for phase in config.jtbd_phases
                ])
            else:
                # Legacy string format
                jtbd_text = "\n".join([f"- {phase}" for phase in config.jtbd_phases])
        
        # Format content categories
        category_text = "\n".join([
            f"- **{key}**: {value}"
            for key, value in config.content_categories.items()
        ])
        
        # Format custom dimensions
        dimensions_text = ""
        if config.custom_dimensions:
            dimensions_text = "\n\n## CUSTOM DIMENSIONS TO EVALUATE:\n" + "\n".join([
                f"- **{key}**: Choose from: {', '.join(values)}"
                for key, values in config.custom_dimensions.items()
            ])
        
        # Get custom instructions
        custom_instructions = ""
        if config.custom_prompt_instructions:
            custom_instructions = f"\n\n## ADDITIONAL ANALYSIS INSTRUCTIONS:\n{config.custom_prompt_instructions}"
        
        # Use prompt manager to build prompts
        return self.prompt_manager.build_prompt_from_config(
            prompt_config,
            content,
            url,
            personas_text,
            jtbd_text,
            category_text,
            dimensions_text,
            custom_instructions
        )
    
    def _extract_mention_contexts(
        self,
        content: str,
        entities: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extract mention contexts for AI analysis"""
        mention_contexts = {}
        content_lower = content.lower()
        
        for entity in entities:
            contexts = []
            
            # Create variations to search for
            variations = [
                entity,
                entity.replace('.com', ''),
                entity.replace('.io', ''),
                entity.split('.')[0]  # Company name only
            ]
            
            for variation in variations:
                if not variation:
                    continue
                
                # Find all occurrences
                pattern = re.compile(r'\b' + re.escape(variation.lower()) + r'\b')
                for match in pattern.finditer(content_lower):
                    pos = match.start()
                    
                    # Extract larger context (300 chars before and after)
                    context_start = max(0, pos - 300)
                    context_end = min(len(content), pos + len(variation) + 300)
                    context = content[context_start:context_end].strip()
                    
                    contexts.append({
                        'entity': entity,
                        'variation': variation,
                        'context': context,
                        'position': pos
                    })
            
            if contexts:
                mention_contexts[entity] = contexts
        
        return mention_contexts
    
    async def _analyze_mentions_with_ai(
        self,
        mention_contexts: Dict[str, List[Dict[str, Any]]],
        is_brand: bool
    ) -> List[Mention]:
        """Analyze mentions using AI for sentiment and context"""
        mentions = []
        
        for entity, contexts in mention_contexts.items():
            # Prepare contexts for AI analysis
            context_texts = [c['context'] for c in contexts[:5]]  # Max 5 contexts
            
            prompt = f"""Analyze the sentiment and context of these mentions of {'our brand' if is_brand else 'a competitor'} "{entity}":

{chr(10).join([f'Context {i+1}: "{ctx}"' for i, ctx in enumerate(context_texts)])}

Analyze:
1. Overall sentiment (positive, negative, neutral)
2. Specific sentiment reasoning
3. Context of mentions (comparison, recommendation, criticism, etc.)
4. Key themes in how the entity is discussed"""
            
            function_schema = {
                "name": "analyze_mentions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "negative", "neutral"]
                        },
                        "sentiment_reasoning": {
                            "type": "string",
                            "description": "Detailed reasoning for sentiment classification"
                        },
                        "context_analysis": {
                            "type": "string",
                            "description": "Analysis of how the entity is discussed"
                        },
                        "key_themes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key themes in mentions"
                        }
                    },
                    "required": ["sentiment", "sentiment_reasoning", "context_analysis"]
                }
            }
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self.headers,
                        json={
                            "model": "gpt-4.1",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are an expert at analyzing brand mentions and sentiment in B2B content."
                                },
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            "tools": [{
                                "type": "function",
                                "function": function_schema
                            }],
                            "tool_choice": {"type": "function", "function": {"name": "analyze_mentions"}},
                            "temperature": 0.3,
                            "max_tokens": 500
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        # Extract tool call arguments (new format)
                        tool_calls = result["choices"][0]["message"].get("tool_calls")
                        if tool_calls and len(tool_calls) > 0:
                            analysis = json.loads(tool_calls[0]["function"]["arguments"])
                        else:
                            # Fallback to old function_call format
                            function_call = result["choices"][0]["message"].get("function_call")
                            if function_call:
                                analysis = json.loads(function_call["arguments"])
                            else:
                                analysis = None
                        
                        if analysis:
                            # Create mention object with AI analysis
                            mentions.append(Mention(
                                entity=entity,
                                count=len(contexts),
                                snippets=[c['context'][:200] + '...' for c in contexts[:3]],
                                sentiment=Sentiment(analysis['sentiment']),
                                sentiment_reasoning=analysis['sentiment_reasoning'],
                                positions=[c['position'] for c in contexts],
                                context_analysis=analysis['context_analysis']
                            ))
                            
            except Exception as e:
                logger.error(f"AI mention analysis failed for {entity}: {str(e)}")
                # Fallback to basic mention
                mentions.append(Mention(
                    entity=entity,
                    count=len(contexts),
                    snippets=[c['context'][:200] + '...' for c in contexts[:3]],
                    sentiment=Sentiment.NEUTRAL,
                    positions=[c['position'] for c in contexts]
                ))
        
        return mentions
    
    def _extract_mentions(
        self,
        content: str,
        domains: List[str]
    ) -> List[Mention]:
        """Extract mentions of domains from content"""
        mentions = []
        content_lower = content.lower()
        
        for domain in domains:
            # Create variations to search for
            variations = [
                domain,
                domain.replace('.com', ''),
                domain.replace('.io', ''),
                domain.replace('.co', ''),
                domain.split('.')[0]  # Company name only
            ]
            
            entity_mentions = {
                'entity': domain,
                'count': 0,
                'snippets': [],
                'positions': []
            }
            
            for variation in variations:
                if not variation:
                    continue
                    
                # Find all occurrences
                pattern = re.compile(r'\b' + re.escape(variation.lower()) + r'\b')
                for match in pattern.finditer(content_lower):
                    pos = match.start()
                    
                    # Extract context (150 chars before and after)
                    context_start = max(0, pos - 150)
                    context_end = min(len(content), pos + len(variation) + 150)
                    snippet = content[context_start:context_end].strip()
                    
                    # Clean up snippet
                    if context_start > 0:
                        snippet = "..." + snippet
                    if context_end < len(content):
                        snippet = snippet + "..."
                    
                    entity_mentions['count'] += 1
                    entity_mentions['positions'].append(pos)
                    
                    # Add snippet if not duplicate
                    if len(entity_mentions['snippets']) < 3:  # Max 3 snippets
                        entity_mentions['snippets'].append(snippet)
            
            if entity_mentions['count'] > 0:
                # Analyze sentiment of mentions
                sentiment = self._analyze_mention_sentiment(
                    entity_mentions['snippets']
                )
                
                mentions.append(Mention(
                    entity=domain,
                    count=entity_mentions['count'],
                    snippets=entity_mentions['snippets'],
                    sentiment=sentiment,
                    positions=entity_mentions['positions']
                ))
        
        return mentions
    
    def _analyze_mention_sentiment(
        self,
        snippets: List[str]
    ) -> Sentiment:
        """Analyze sentiment of mention snippets"""
        # Default to neutral - actual sentiment is analyzed by AI in _analyze_mentions_with_ai
        # This is a fallback method that should not be used for production
        return Sentiment.NEUTRAL
    
    async def _identify_source_with_ai(
        self,
        url: str,
        content: str,
        client_id: str = None,
        video_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Use AI and Cognism data to identify the source company and type"""
        
        # Extract domain
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        
        # Special handling for YouTube videos
        if 'youtube.com' in domain or 'youtu.be' in domain:
            # Check for temp video data if not provided
            if not video_data and hasattr(self, '_temp_video_data'):
                video_data = self._temp_video_data
            
            if video_data:
                # Use AI to identify company from video data
                video_company = await self.identify_video_company(video_data)
                
                # Try to get company data from identified domain
                company_data = None
                if video_company.get('inferred_domain'):
                    company_data = await self._get_company_by_domain(
                        video_company['inferred_domain']
                    )
                
                # If no company data found, create a placeholder
                if not company_data:
                    company_data = {
                        'company_name': video_company['company_name'],
                        'domain': video_company.get('inferred_domain', f"youtube.com/c/{video_company['company_name'].replace(' ', '')}"),
                        'industry': 'Media/Content',
                        'company_type': video_company['channel_type'],
                        'description': f"YouTube Channel: {video_company['company_name']}"
                    }
                
                # Override domain for further processing
                domain = company_data.get('domain', domain)
            else:
                # No video data available, use YouTube as company
                company_data = {
                    'company_name': 'YouTube',
                    'domain': 'youtube.com',
                    'industry': 'Technology',
                    'company_type': 'platform'
                }
        else:
            # Regular website - check if we have enriched company data from Cognism
            company_data = await self._get_company_by_domain(domain)
        
        # Get client configuration to check owned/competitor status
        config = None
        if client_id:
            config = await self._get_enhanced_client_config(client_id)
        
        is_client_domain = False
        is_competitor = False
        
        if config:
            # Check if it's the client's domain
            primary_domain = getattr(config, 'primary_domain', '')
            if primary_domain:
                is_client_domain = domain == primary_domain.lower().replace('www.', '')
            
            # Check if it's a competitor domain
            competitor_domains = getattr(config, 'competitor_domains', [])
            is_competitor = any(domain == comp.lower().replace('www.', '') for comp in competitor_domains)
        
        # Build context for AI including Cognism data
        cognism_context = ""
        if company_data:
            cognism_context = f"""

Enriched Company Data from Cognism:
- Company Name: {company_data.get('company_name', 'Unknown')}
- Industry: {company_data.get('industry', 'Unknown')}
- Sub-Industry: {company_data.get('sub_industry', 'Unknown')}
- Company Type: {company_data.get('company_type', 'Unknown')}
- Description: {company_data.get('description', 'No description available')}
- Revenue: {company_data.get('revenue_amount', 'Unknown')}
- Employees: {company_data.get('headcount', 'Unknown')}
- Founded: {company_data.get('founded_year', 'Unknown')}
"""
        
        # Build the source classification prompt with clear dimensions
        source_dimensions = """
## SOURCE CLASSIFICATION DIMENSIONS

1. **OWNED** - Content published by the client company itself

2. **COMPETITOR** - Content published by a named client competitor (must be in competitor list)

3. **PREMIUM_PUBLISHER** - High-authority media and research publishers
   - Examples: Forbes, Wall Street Journal, Financial Times, TechTarget, Gartner, Forrester, IDC, Harvard Business Review, MIT Sloan Review, McKinsey Insights

4. **TECHNOLOGY** - Technology companies and tech-focused businesses
   - Examples: Microsoft, Google, AWS, Salesforce, Oracle, SAP, IBM, tech startups
   - NOT professional services firms even if they have tech practices

5. **FINANCE** - Banks, Building Societies, and Financial Institutions
   - Examples: JP Morgan, Bank of America, HSBC, Barclays, credit unions, investment banks
   - NOT accounting/consulting firms (those go in OTHER)

6. **PROFESSIONAL_BODY** - Regulatory bodies, chartered institutes, and professional associations
   - Examples: Chartered Institute of Bankers, IEEE, ACCA, Bar Association, Medical Councils, CPA boards
   - NOT professional services firms like PwC, Deloitte, EY, KPMG (those go in OTHER)

7. **SOCIAL_MEDIA** - Social media and community platforms
   - Examples: LinkedIn, Facebook, Twitter/X, Reddit, Wikipedia, YouTube (platform content), forums

8. **EDUCATION** - Educational institutions and academic sources
   - Examples: Universities (.edu), colleges, business schools, academic journals, research institutions

9. **NON_PROFIT** - Charities and not-for-profit organizations
   - Examples: Red Cross, United Way, foundations, NGOs, charitable organizations
   - Typically .org domains with charitable/social missions

10. **GOVERNMENT** - Government sources and public sector
    - Examples: .gov domains, regulatory agencies, central banks, government departments, public sector bodies

11. **OTHER** - Professional services firms and anything not fitting above categories
    - Examples: PwC, Deloitte, EY, KPMG, Accenture, consulting firms, law firms, agencies
    - Any company that doesn't clearly fit the specific categories above
"""

        # Build context for the AI
        prompt = f"""Analyze this source and classify it into one of the defined categories.

URL: {url}
Domain: {domain}

Is this the client's domain? {is_client_domain}
Is this a competitor domain? {is_competitor}
{cognism_context}

{source_dimensions}

CLASSIFICATION INSTRUCTIONS:
- Use the Cognism company data (type, description) as the primary indicator
- Industry data has been disabled due to inaccuracy
- Only classify as OWNED if is_client_domain is True
- Only classify as COMPETITOR if is_competitor is True  
- For ambiguous cases, choose the most specific applicable category
- Default to OTHER only if no other category clearly fits

Analyze the source and provide your classification with reasoning."""
        
        function_schema = {
            "name": "identify_source",
            "description": "Identify content source and company",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Company name if identifiable"
                    },
                    "industry": {
                        "type": "string",
                        "description": "Industry or sector"
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief company/source description"
                    },
                    "source_type": {
                        "type": "string",
                        "enum": ["OWNED", "COMPETITOR", "PREMIUM_PUBLISHER", "TECHNOLOGY", 
                                "FINANCE", "PROFESSIONAL_BODY", "SOCIAL_MEDIA", "EDUCATION", 
                                "NON_PROFIT", "GOVERNMENT", "OTHER"]
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Reasoning for the classification"
                    }
                },
                "required": ["source_type", "reasoning"]
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert at identifying companies and content sources from web content."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "tools": [{
                            "type": "function",
                            "function": function_schema
                        }],
                        "tool_choice": {"type": "function", "function": {"name": "identify_source"}},
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"OpenAI API error: {response.status_code}")
                
                result = response.json()
                # Extract tool call arguments (new format)
                tool_calls = result["choices"][0]["message"].get("tool_calls")
                if tool_calls and len(tool_calls) > 0:
                    source_info = json.loads(tool_calls[0]["function"]["arguments"])
                else:
                    # Fallback to old function_call format
                    function_call = result["choices"][0]["message"].get("function_call")
                    if function_call:
                        source_info = json.loads(function_call["arguments"])
                    else:
                        source_info = None
                
                if source_info:
                    # Try to match with existing company
                    company_id = None
                    if source_info.get('company_name'):
                        company = await self._get_company_by_name_or_domain(
                            source_info['company_name'], 
                            domain
                        )
                        if company:
                            company_id = company['id']
                    
                    return {
                        'type': source_info.get('source_type', 'OTHER').lower(),
                        'company_id': company_id,
                        'company_name': source_info.get('company_name'),
                        'industry': source_info.get('industry'),
                        'description': source_info.get('description'),
                        'reasoning': source_info.get('reasoning')
                    }
                    
        except Exception as e:
            logger.error(f"AI source identification failed: {str(e)}")
        
        # Fallback to basic classification
        return {'type': 'other', 'reasoning': 'Could not identify source'}
    

    
    def _generate_content_id(self, url: str, content: str) -> UUID:
        """Generate a unique content ID based on URL and content hash"""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        unique_string = f"{url}:{content_hash}"
        return UUID(hashlib.md5(unique_string.encode()).hexdigest())
    
    async def _get_enhanced_client_config(self, client_id: str) -> AnalysisConfig:
        """Get enhanced client configuration with competitor info"""
        async with self.db.acquire() as conn:
            # Get base config
            result = await conn.fetchrow(
                """
                SELECT personas, jtbd_phases, custom_dimensions, content_categories,
                       max_content_length, temperature, enable_mention_extraction,
                       enable_sentiment_analysis, custom_prompt_instructions,
                       competitor_domains
                FROM client_analysis_config
                WHERE client_id = $1
                """,
                client_id
            )
            
            if result:
                # Parse personas with full context
                personas = []
                if result['personas']:
                    # Parse JSON string if necessary
                    personas_data = result['personas']
                    if isinstance(personas_data, str):
                        personas_data = json.loads(personas_data)
                    for p in personas_data:
                        # Map 'role' to 'description' if needed
                        persona_dict = dict(p)
                        if 'role' in persona_dict and 'description' not in persona_dict:
                            persona_dict['description'] = persona_dict.pop('role')
                        # Ensure content_preferences exists
                        if 'content_preferences' not in persona_dict:
                            persona_dict['content_preferences'] = []
                        personas.append(Persona(**persona_dict))
                
                # Parse JTBD phases with full context
                jtbd_phases = []
                if result['jtbd_phases']:
                    # Parse JSON string if necessary
                    jtbd_data = result['jtbd_phases']
                    logger.info(f"JTBD phases raw type: {type(jtbd_data)}, value: {jtbd_data}")
                    if isinstance(jtbd_data, str):
                        try:
                            jtbd_data = json.loads(jtbd_data)
                            logger.info(f"JTBD phases after JSON parse: {jtbd_data}")
                        except Exception as e:
                            logger.error(f"Failed to parse JTBD phases JSON: {e}, raw data: {jtbd_data}")
                            # If JSON parsing fails, ignore the data
                            jtbd_data = []
                    
                    # Only process if it's a list
                    if isinstance(jtbd_data, list):
                        for phase in jtbd_data:
                            if isinstance(phase, dict):
                                # Add buyer_mindset if not present
                                if 'buyer_mindset' not in phase:
                                    phase['buyer_mindset'] = phase.get('description', f"Buyers in {phase.get('name', 'this')} phase")
                                jtbd_phases.append(JTBDPhase(**phase))
                            elif isinstance(phase, str) and phase.strip():
                                # Legacy string format - create default phase
                                jtbd_phases.append(JTBDPhase(
                                    name=phase,
                                    description=f"Phase: {phase}",
                                    buyer_mindset=f"Buyers in {phase} phase",
                                    key_questions=[],
                                    content_types=[]
                                ))
                
                # Parse custom_dimensions if it's a JSON string
                custom_dimensions = result.get('custom_dimensions', {})
                if isinstance(custom_dimensions, str):
                    custom_dimensions = json.loads(custom_dimensions)
                
                # Parse content_categories if it's a JSON string
                content_categories = result.get('content_categories', AnalysisConfig().content_categories)
                if isinstance(content_categories, str):
                    content_categories = json.loads(content_categories)
                
                return AnalysisConfig(
                    personas=personas,
                    jtbd_phases=jtbd_phases,
                    competitor_domains=result.get('competitor_domains', []),
                    custom_dimensions=custom_dimensions,
                    content_categories=content_categories,
                    max_content_length=result.get('max_content_length', 8000),
                    temperature=float(result.get('temperature', 0.3)),
                    enable_mention_extraction=result.get('enable_mention_extraction', True),
                    enable_sentiment_analysis=result.get('enable_sentiment_analysis', True),
                    custom_prompt_instructions=result.get('custom_prompt_instructions')
                )
            
            # Return default config with sample data
            return self._get_default_enhanced_config()
    
    def _get_default_enhanced_config(self) -> AnalysisConfig:
        """Get default enhanced configuration with examples"""
        return AnalysisConfig(
            personas=[
                Persona(
                    name="Technical Decision Maker",
                    description="CTO/VP Engineering evaluating technical solutions",
                    title="CTO / VP Engineering",
                    goals=["Scalable architecture", "Developer productivity", "Technical innovation"],
                    pain_points=["Legacy system limitations", "Integration complexity", "Technical debt"],
                    decision_criteria=["Performance", "Scalability", "Developer experience", "Security"],
                    content_preferences=["Technical deep-dives", "Architecture guides", "Performance benchmarks"]
                ),
                Persona(
                    name="Business Decision Maker",
                    description="CFO/VP Finance focused on ROI and business impact",
                    title="CFO / VP Finance",
                    goals=["Cost reduction", "Revenue growth", "Operational efficiency"],
                    pain_points=["Budget constraints", "ROI justification", "Hidden costs"],
                    decision_criteria=["ROI", "Total cost of ownership", "Time to value", "Risk"],
                    content_preferences=["ROI calculators", "Case studies", "Business impact analysis"]
                )
            ],
            jtbd_phases=[
                JTBDPhase(
                    name="Problem Identification",
                    description="Buyers recognize a problem or opportunity that requires a solution",
                    buyer_mindset="We need to address this challenge",
                    key_questions=["What's the impact of this problem?", "What opportunities are we missing?"],
                    content_types=["Industry trends", "Research reports", "Problem analysis"]
                ),
                JTBDPhase(
                    name="Solution Exploration",
                    description="Buyers research potential solutions and evaluate different options",
                    buyer_mindset="What solutions are available?",
                    key_questions=["What approaches exist?", "What are the pros and cons?", "What's possible?"],
                    content_types=["Solution guides", "Option comparisons", "Capability overviews"]
                ),
                JTBDPhase(
                    name="Requirements Building",
                    description="Buyers define the specific requirements and specifications for the desired solution",
                    buyer_mindset="What exactly do we need?",
                    key_questions=["What are our must-haves?", "What constraints exist?", "What's our criteria?"],
                    content_types=["Requirements guides", "Specification templates", "Evaluation criteria"]
                ),
                JTBDPhase(
                    name="Supplier Selection",
                    description="Buyers evaluate potential suppliers and make a decision on which one to partner with",
                    buyer_mindset="Which vendor is the best fit?",
                    key_questions=["Who can deliver?", "Who do we trust?", "Who offers best value?"],
                    content_types=["Vendor comparisons", "Customer reviews", "Analyst reports"]
                ),
                JTBDPhase(
                    name="Validation",
                    description="Buyers assess the chosen supplier's capabilities and ensure they can meet the defined requirements",
                    buyer_mindset="Can they really deliver?",
                    key_questions=["Does it work as promised?", "What's the real ROI?", "What are the risks?"],
                    content_types=["Proof of concepts", "Case studies", "Reference checks"]
                ),
                JTBDPhase(
                    name="Consensus Creation",
                    description="Buyers build internal agreement and support for the purchase decision",
                    buyer_mindset="How do we get everyone aligned?",
                    key_questions=["How to get buy-in?", "Who needs convincing?", "What are the objections?"],
                    content_types=["Business cases", "Executive summaries", "Change management plans"]
                )
            ],
            competitor_domains=[]  # Will be populated from client config
        )
    
    async def _get_client_config(self, client_id: str) -> AnalysisConfig:
        """Get client analysis configuration"""
        async with self.db.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT personas, jtbd_phases, custom_dimensions, content_categories,
                       max_content_length, temperature, enable_mention_extraction,
                       enable_sentiment_analysis, custom_prompt_instructions
                FROM client_analysis_config
                WHERE client_id = $1
                """,
                client_id
            )
            
            if result:
                # Parse personas
                personas = [
                    Persona(**p) for p in result['personas']
                ] if result['personas'] else []
                
                # Parse JTBD phases - can be JSONB (dicts) or text array (strings)
                jtbd_phases = result['jtbd_phases'] or []
                if jtbd_phases and isinstance(jtbd_phases, str):
                    jtbd_phases = json.loads(jtbd_phases)
                
                return AnalysisConfig(
                    personas=personas,
                    jtbd_phases=jtbd_phases or AnalysisConfig().jtbd_phases,
                    custom_dimensions=result['custom_dimensions'] or {},
                    content_categories=result['content_categories'] or AnalysisConfig().content_categories,
                    max_content_length=result['max_content_length'],
                    temperature=float(result['temperature']),
                    enable_mention_extraction=result['enable_mention_extraction'],
                    enable_sentiment_analysis=result['enable_sentiment_analysis'],
                    custom_prompt_instructions=result['custom_prompt_instructions']
                )
            
            # Return default config
            return AnalysisConfig()
    
    def _merge_configs(
        self,
        base_config: AnalysisConfig,
        custom_config: Dict[str, Any]
    ) -> AnalysisConfig:
        """Merge custom configuration with base config"""
        config_dict = base_config.dict()
        config_dict.update(custom_config)
        return AnalysisConfig(**config_dict)
    
    async def _get_existing_analysis(
        self,
        client_id: str,
        url: str
    ) -> Optional[ContentAnalysisResult]:
        """Get existing analysis for URL"""
        try:
            async with self.db.acquire() as conn:
                # Check for existing analysis for this client and URL
                result = await conn.fetchrow(
                    """
                    SELECT 
                        ca.id, ca.client_id, ca.content_asset_id, ca.url, ca.summary,
                        ca.content_classification, ca.primary_persona, ca.persona_alignment_scores,
                        ca.jtbd_phase, ca.jtbd_alignment_score, ca.custom_dimensions, ca.key_topics,
                        ca.sentiment, ca.confidence_scores, ca.brand_mentions, ca.competitor_mentions,
                        ca.source_type, ca.source_company_id, ca.source_company_name, 
                        ca.source_company_industry, ca.source_company_description,
                        ca.source_identification_reasoning, ca.analyzed_at, ca.analysis_version, ca.model_used
                    FROM content_analysis ca
                    WHERE ca.client_id = $1 AND ca.url = $2
                    ORDER BY ca.analyzed_at DESC
                    LIMIT 1
                    """,
                    client_id, url
                )
                
                if result:
                    logger.info(f"Cache hit for content analysis: {url}")
                    
                    # Convert database result to ContentAnalysisResult
                    from app.models.content_analysis import ContentAnalysisResult, ContentClassification, Sentiment
                    import json
                    import uuid
                    
                    return ContentAnalysisResult(
                        id=result['id'] if isinstance(result['id'], uuid.UUID) else uuid.UUID(str(result['id'])),
                        client_id=result['client_id'],
                        content_asset_id=result['content_asset_id'] if isinstance(result['content_asset_id'], uuid.UUID) else uuid.UUID(str(result['content_asset_id'])),
                        url=result['url'],
                        summary=result['summary'],
                        content_classification=ContentClassification(result['content_classification']),
                        primary_persona=result['primary_persona'],
                        persona_alignment_scores=json.loads(result['persona_alignment_scores'] or '{}'),
                        jtbd_phase=result['jtbd_phase'],
                        jtbd_alignment_score=result['jtbd_alignment_score'],
                        custom_dimensions=json.loads(result['custom_dimensions'] or '{}'),
                        key_topics=result['key_topics'],
                        sentiment=Sentiment(result['sentiment']),
                        confidence_scores=json.loads(result['confidence_scores'] or '{}') if result['confidence_scores'] else {},
                        brand_mentions=json.loads(result['brand_mentions'] or '[]'),
                        competitor_mentions=json.loads(result['competitor_mentions'] or '[]'),
                        source_type=result['source_type'],
                        source_company_id=result['source_company_id'],
                        source_company_name=result['source_company_name'],
                        source_company_industry=result['source_company_industry'],
                        source_company_description=result['source_company_description'],
                        source_identification_reasoning=result['source_identification_reasoning'],
                        analyzed_at=result['analyzed_at'],
                        analysis_version=result['analysis_version'],
                        model_used=result['model_used']
                    )
                else:
                    logger.debug(f"No cached analysis found for: {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error checking for existing analysis for {url}: {e}")
            return None
    
    async def _get_client_domains(self, client_id: str) -> List[str]:
        """Get client domains"""
        async with self.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT domain FROM companies WHERE client_id = $1",
                client_id
            )
            return [company['domain']] if company else []
    
    async def _get_competitor_domains(self, client_id: str) -> List[str]:
        """Get competitor domains"""
        # Would fetch from client configuration
        # Simplified for now
        return []
    
    async def _get_company_by_name_or_domain(
        self,
        name: str,
        domain: str
    ) -> Optional[Dict[str, Any]]:
        """Get company by name or domain"""
        async with self.db.acquire() as conn:
            # Try by domain first
            result = await conn.fetchrow(
                "SELECT id, company_name, domain FROM company_profiles WHERE domain = $1",
                domain
            )
            if result:
                return dict(result)
            
            # Try by name (fuzzy match)
            result = await conn.fetchrow(
                """
                SELECT id, company_name, domain FROM company_profiles 
                WHERE LOWER(company_name) LIKE $1 
                LIMIT 1
                """,
                f"%{name.lower()}%"
            )
            return dict(result) if result else None
    
    async def _get_company_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get company by domain"""
        async with self.db.acquire() as conn:
            # Prioritize English records and get full company data
            result = await conn.fetchrow(
                """
                SELECT * FROM company_profiles
                WHERE domain = $1
                ORDER BY
                    CASE
                        WHEN headquarters_location::text ILIKE '%united states%' THEN 1
                        WHEN headquarters_location::text ILIKE '%USA%' THEN 1
                        WHEN headquarters_location::text ILIKE '%UK%' THEN 2
                        WHEN headquarters_location::text ILIKE '%united kingdom%' THEN 2
                        WHEN description ILIKE '%global%' THEN 3
                        WHEN description IS NOT NULL AND description != '' THEN 4
                        ELSE 5
                    END,
                    headcount DESC NULLS LAST
                LIMIT 1
                """,
                domain
            )
            return dict(result) if result else None
    
    async def _is_client_domain(self, domain: str) -> bool:
        """Check if domain belongs to a client"""
        async with self.db.acquire() as conn:
            result = await conn.fetchval(
                "SELECT 1 FROM companies WHERE domain = $1",
                domain
            )
            return result is not None
    
    async def _is_competitor_domain(self, domain: str) -> bool:
        """Check if domain is a known competitor"""
        # Would check against competitor configuration
        # Simplified for now
        return False
    
    async def _store_analysis(self, result: ContentAnalysisResult):
        """Store analysis result in database"""
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO content_analysis (
                    id, client_id, content_asset_id, analysis_date, url, summary,
                    content_classification, primary_persona, persona_alignment_scores,
                    jtbd_phase, jtbd_alignment_score, custom_dimensions, key_topics,
                    sentiment, confidence_scores, brand_mentions, competitor_mentions, source_type,
                    source_company_id, source_company_name, source_company_industry,
                    source_company_description, source_identification_reasoning,
                    analyzed_at, analysis_version, model_used
                ) VALUES ($1, $2, $3, CURRENT_DATE, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)
                ON CONFLICT (client_id, content_asset_id) DO UPDATE SET
                    summary = EXCLUDED.summary,
                    content_classification = EXCLUDED.content_classification,
                    analysis_date = CURRENT_DATE,
                    analyzed_at = EXCLUDED.analyzed_at
                """,
                str(result.id),
                result.client_id,
                str(result.content_asset_id),
                result.url,
                result.summary,
                result.content_classification.value,
                result.primary_persona,
                json.dumps(result.persona_alignment_scores),
                result.jtbd_phase,
                result.jtbd_alignment_score,
                json.dumps(result.custom_dimensions),
                result.key_topics,
                result.sentiment.value,
                json.dumps(result.confidence_scores) if result.confidence_scores else None,
                json.dumps([m.dict() for m in result.brand_mentions]),
                json.dumps([m.dict() for m in result.competitor_mentions]),
                result.source_type.value if result.source_type else None,
                result.source_company_id,
                result.source_company_name,
                result.source_company_industry,
                result.source_company_description,
                result.source_identification_reasoning,
                result.analyzed_at,
                result.analysis_version,
                result.model_used
            )
    
    async def _store_job(self, job: AnalysisJob):
        """Store analysis job"""
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO content_analysis_jobs (
                    id, client_id, status, total_urls, processed,
                    successful, failed, error_details, started_at, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                job.id,
                job.client_id,
                job.status,
                job.total_urls,
                job.processed,
                job.successful,
                job.failed,
                json.dumps(job.error_details),
                job.started_at,
                job.created_at
            )
    
    async def _update_job(self, job: AnalysisJob):
        """Update analysis job"""
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE content_analysis_jobs
                SET status = $2, processed = $3, successful = $4,
                    failed = $5, error_details = $6, completed_at = $7
                WHERE id = $1
                """,
                job.id,
                job.status,
                job.processed,
                job.successful,
                job.failed,
                json.dumps(job.error_details),
                job.completed_at
            )
    
    async def get_job_status(self, job_id: UUID) -> Optional[AnalysisJob]:
        """Get job status"""
        async with self.db.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT id, client_id, status, total_urls, processed,
                       successful, failed, error_details, started_at,
                       completed_at, created_at
                FROM content_analysis_jobs
                WHERE id = $1
                """,
                job_id
            )
            
            if result:
                return AnalysisJob(
                    id=result['id'],
                    client_id=result['client_id'],
                    status=result['status'],
                    total_urls=result['total_urls'],
                    processed=result['processed'],
                    successful=result['successful'],
                    failed=result['failed'],
                    error_details=result['error_details'],
                    started_at=result['started_at'],
                    completed_at=result['completed_at'],
                    created_at=result['created_at']
                )
            
            return None
    
    async def identify_video_company(
        self,
        video_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Identify company from YouTube video/channel data using AI"""
        
        # Extract relevant data
        channel_title = video_data.get('channel_title', '')
        channel_id = video_data.get('channel_id', '')
        video_title = video_data.get('title', '')
        video_description = video_data.get('description', '')[:1000]  # First 1000 chars
        channel_description = video_data.get('channel_description', '')  # Channel about section
        
        # Check cache first
        cached_mapping = await self._get_cached_channel_company(channel_id)
        if cached_mapping and cached_mapping.get('confidence_score', 0) >= 0.7:
            logger.info(f"Using cached channel-company mapping for {channel_id}")
            return cached_mapping
        
        # Build prompt for AI
        prompt = f"""Analyze this YouTube video/channel information to identify the company or organization behind it.

CHANNEL INFORMATION:
- Channel Name: {channel_title}
- Channel ID: {channel_id}
- Channel Description/About: {channel_description[:500] if channel_description else 'Not available'}
- Video Title: {video_title}
- Video Description (excerpt): {video_description}

TASK:
1. Identify if this channel belongs to a company/organization
2. Extract or infer the company's primary domain (e.g., microsoft.com)
3. Determine the channel type

INSTRUCTIONS:
- FIRST: Check the channel description/about section for company info and website links
- Look for company names in the channel title (e.g., "Microsoft" → microsoft.com)
- Check video description for website links or company mentions
- Look for patterns like "Official channel of [Company]" in descriptions
- Common patterns:
  * "IBM Cloud" → ibm.com
  * "Google Developers" → google.com
  * "Salesforce" → salesforce.com
- If it's a news organization, identify it (e.g., "CNN Business" → cnn.com)
- If it's an individual creator or unclear, mark as "unknown"

Return a JSON object with:
{{
    "is_company": true/false,
    "company_name": "extracted company name or channel name",
    "inferred_domain": "domain.com or null",
    "channel_type": "corporate|news|individual|unknown",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

        try:
            # Use GPT-4 for company identification
            data = {
                "model": "gpt-4-0125-preview",
                "messages": [
                    {"role": "system", "content": "You are an expert at identifying companies from YouTube channel information."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=data
                )
                response.raise_for_status()
                response_data = response.json()
                    
            result = json.loads(response_data['choices'][0]['message']['content'])
            
            # Add fallback values
            if not result.get('company_name'):
                result['company_name'] = channel_title
            
            logger.info(f"Video company identification: {result}")
            
            # Cache successful identification with high confidence
            if result.get('confidence', 0) >= 0.7 and result.get('inferred_domain'):
                await self._cache_channel_company(channel_id, channel_title, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error identifying video company: {str(e)}, Type: {type(e).__name__}")
            # Return fallback
            return {
                "is_company": False,
                "company_name": channel_title,
                "inferred_domain": None,
                "channel_type": "unknown",
                "confidence": 0.0,
                "reasoning": f"Failed to identify: {str(e)}"
            }
    
    async def _get_cached_channel_company(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get cached channel-company mapping"""
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT company_name, company_domain, channel_type, 
                           confidence_score, reasoning
                    FROM youtube_channel_companies
                    WHERE channel_id = $1
                    """,
                    channel_id
                )
                
                if result:
                    return {
                        "is_company": bool(result['company_domain']),
                        "company_name": result['company_name'],
                        "inferred_domain": result['company_domain'],
                        "channel_type": result['channel_type'],
                        "confidence": result['confidence_score'],
                        "reasoning": result['reasoning']
                    }
        except Exception as e:
            logger.error(f"Error fetching cached channel mapping: {e}")
        
        return None
    
    async def _cache_channel_company(
        self, 
        channel_id: str, 
        channel_name: str, 
        mapping: Dict[str, Any]
    ):
        """Cache channel-company mapping"""
        try:
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO youtube_channel_companies (
                        channel_id, channel_name, company_name, company_domain,
                        channel_type, confidence_score, identification_method, 
                        reasoning, last_verified_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ON CONFLICT (channel_id) DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        company_domain = EXCLUDED.company_domain,
                        channel_type = EXCLUDED.channel_type,
                        confidence_score = EXCLUDED.confidence_score,
                        reasoning = EXCLUDED.reasoning,
                        last_verified_at = NOW(),
                        updated_at = NOW()
                    """,
                    channel_id,
                    channel_name,
                    mapping.get('company_name'),
                    mapping.get('inferred_domain'),
                    mapping.get('channel_type', 'unknown'),
                    mapping.get('confidence', 0.0),
                    'ai_identified',
                    mapping.get('reasoning', '')
                )
                logger.info(f"Cached channel-company mapping for {channel_id}")
        except Exception as e:
            logger.error(f"Error caching channel mapping: {e}")