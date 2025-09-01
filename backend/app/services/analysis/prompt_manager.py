"""
Prompt Configuration Management Service
"""
import json
from typing import Optional, Dict, List, Any
from uuid import UUID, uuid4
from datetime import datetime
import string

from loguru import logger

from app.models.prompt_config import (
    PromptConfiguration,
    PromptSection,
    PromptTemplate,
    PromptLibrary,
    PromptVariable
)
from app.core.database import DatabasePool


class PromptManager:
    """Service for managing LLM prompt configurations"""
    
    def __init__(self, db: DatabasePool):
        self.db = db
    
    async def get_or_create_default_config(self, client_id: str) -> PromptConfiguration:
        """Get client's prompt configuration or create default"""
        config = await self.get_active_config(client_id)
        if not config:
            config = await self.create_default_config(client_id)
        return config
    
    async def get_active_config(self, client_id: str) -> Optional[PromptConfiguration]:
        """Get active prompt configuration for client"""
        async with self.db.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT * FROM prompt_configurations
                WHERE client_id = $1 AND is_active = true
                ORDER BY version DESC
                LIMIT 1
                """,
                client_id
            )
            
            if result:
                row_dict = dict(result)
                # Ensure JSON fields are proper dicts (DB may store as text)
                json_fields = [
                    'system_prompt_variables', 'section_templates', 'requirement_templates',
                    'performance_metrics'
                ]
                for field in json_fields:
                    if field in row_dict and isinstance(row_dict[field], str):
                        try:
                            row_dict[field] = json.loads(row_dict[field])
                        except Exception:
                            row_dict[field] = {}
                return PromptConfiguration(**row_dict)
            return None
    
    async def create_default_config(self, client_id: str) -> PromptConfiguration:
        """Create default prompt configuration for client"""
        config = PromptConfiguration(
            id=uuid4(),
            client_id=client_id,
            name="Default Configuration",
            version=1,
            created_at=datetime.utcnow()
        )
        
        # Set default section templates
        config.section_templates = {
            PromptSection.PERSONAS: """## TARGET PERSONAS (analyze alignment with each):

{persona_text}""",
            PromptSection.JTBD_PHASES: """## JOBS TO BE DONE PHASES (identify primary phase):

{jtbd_text}""",
            PromptSection.CONTENT_CATEGORIES: """## CONTENT CATEGORIES (classify into one):

{category_text}""",
            PromptSection.CUSTOM_INSTRUCTIONS: """{custom_instructions}"""
        }
        
        await self.save_config(config)
        return config
    
    async def save_config(self, config: PromptConfiguration) -> PromptConfiguration:
        """Save prompt configuration"""
        config.updated_at = datetime.utcnow()
        
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO prompt_configurations (
                    id, client_id, name, version, system_prompt_template,
                    system_prompt_variables, section_templates, 
                    analysis_requirements_template, requirement_templates,
                    persona_scoring_criteria, jtbd_scoring_criteria,
                    output_format_instructions, temperature_override,
                    max_tokens_override, model_override, enable_chain_of_thought,
                    enable_self_critique, custom_functions, is_active,
                    performance_metrics, created_at, updated_at, created_by
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    system_prompt_template = EXCLUDED.system_prompt_template,
                    system_prompt_variables = EXCLUDED.system_prompt_variables,
                    section_templates = EXCLUDED.section_templates,
                    analysis_requirements_template = EXCLUDED.analysis_requirements_template,
                    requirement_templates = EXCLUDED.requirement_templates,
                    persona_scoring_criteria = EXCLUDED.persona_scoring_criteria,
                    jtbd_scoring_criteria = EXCLUDED.jtbd_scoring_criteria,
                    output_format_instructions = EXCLUDED.output_format_instructions,
                    temperature_override = EXCLUDED.temperature_override,
                    max_tokens_override = EXCLUDED.max_tokens_override,
                    model_override = EXCLUDED.model_override,
                    enable_chain_of_thought = EXCLUDED.enable_chain_of_thought,
                    enable_self_critique = EXCLUDED.enable_self_critique,
                    custom_functions = EXCLUDED.custom_functions,
                    performance_metrics = EXCLUDED.performance_metrics,
                    updated_at = EXCLUDED.updated_at
                """,
                config.id,
                config.client_id,
                config.name,
                config.version,
                config.system_prompt_template,
                json.dumps(config.system_prompt_variables),
                json.dumps({k.value: v for k, v in config.section_templates.items()}),
                config.analysis_requirements_template,
                json.dumps(config.requirement_templates),
                config.persona_scoring_criteria,
                config.jtbd_scoring_criteria,
                config.output_format_instructions,
                config.temperature_override,
                config.max_tokens_override,
                config.model_override,
                config.enable_chain_of_thought,
                config.enable_self_critique,
                json.dumps(config.custom_functions) if config.custom_functions else None,
                config.is_active,
                json.dumps(config.performance_metrics),
                config.created_at,
                config.updated_at,
                config.created_by
            )
        
        return config
    
    def build_prompt_from_config(
        self,
        config: PromptConfiguration,
        content: str,
        url: str,
        personas_text: str,
        jtbd_text: str,
        category_text: str,
        dimensions_text: str = "",
        custom_instructions: str = ""
    ) -> Dict[str, str]:
        """Build system and user prompts from configuration"""
        
        # Build system prompt
        system_prompt = self._format_template(
            config.system_prompt_template,
            config.system_prompt_variables
        )
        
        # Build analysis requirements
        requirements_list = []
        for req_key, req_template in config.requirement_templates.items():
            if req_key == "summary":
                req = self._format_template(req_template, {
                    "summary_instructions": "Provide a comprehensive 3-4 sentence summary capturing the main value proposition and key insights"
                })
            elif req_key == "persona_alignment":
                req = self._format_template(req_template, {
                    "persona_identification_instructions": "Identify the primary persona this content targets",
                    "persona_scoring_instructions": f"Score alignment (0-1) for EACH persona based on:\n      * " + "\n      * ".join(config.persona_scoring_criteria),
                    "persona_reasoning_instructions": "Explain WHY this content best fits the primary persona"
                })
            elif req_key == "jtbd_identification":
                req = self._format_template(req_template, {
                    "phase_identification_instructions": "Identify which JTBD phase this content best serves",
                    "phase_scoring_instructions": f"Score alignment (0-1) based on:\n      * " + "\n      * ".join(config.jtbd_scoring_criteria),
                    "phase_reasoning_instructions": "Explain WHY this content fits this phase"
                })
            elif req_key == "buyer_intent":
                req = self._format_template(req_template, {
                    "intent_instructions": "Identify specific phrases or sections that indicate buyer intent"
                })
            elif req_key == "classification":
                req = self._format_template(req_template, {
                    "classification_instructions": "Classify based on where it fits in the buyer journey"
                })
            elif req_key == "topics":
                req = self._format_template(req_template, {
                    "topics_instructions": "Extract 5-7 main topics or themes"
                })
            elif req_key == "sentiment":
                req = self._format_template(req_template, {
                    "sentiment_instructions": "Analyze overall tone and sentiment"
                })
            else:
                req = req_template
            
            requirements_list.append(f"{len(requirements_list) + 1}. {req}")
        
        analysis_requirements = self._format_template(
            config.analysis_requirements_template,
            {"requirements_list": "\n\n".join(requirements_list)}
        )
        
        # Build user prompt sections
        sections = []
        
        # Add URL
        sections.append(f"Analyze this B2B content from: {url}")
        
        # Add configured sections
        for section, template in config.section_templates.items():
            if section == PromptSection.PERSONAS and personas_text:
                sections.append(self._format_template(template, {"persona_text": personas_text}))
            elif section == PromptSection.JTBD_PHASES and jtbd_text:
                sections.append(self._format_template(template, {"jtbd_text": jtbd_text}))
            elif section == PromptSection.CONTENT_CATEGORIES and category_text:
                sections.append(self._format_template(template, {"category_text": category_text}))
            elif section == PromptSection.CUSTOM_INSTRUCTIONS and custom_instructions:
                sections.append(self._format_template(template, {"custom_instructions": custom_instructions}))
        
        # Add dimensions if present
        if dimensions_text:
            sections.append(dimensions_text)
        
        # Add analysis requirements
        sections.append(analysis_requirements)
        
        # Add output format instructions
        if config.output_format_instructions:
            sections.append(f"\n{config.output_format_instructions}")
        
        # Add content
        sections.append(f"\n## CONTENT TO ANALYZE:\n\n{content}")
        
        # Add chain of thought if enabled
        if config.enable_chain_of_thought:
            sections.append("\n## ANALYSIS APPROACH:\nFirst, think through your analysis step-by-step before providing the final structured output.")
        
        user_prompt = "\n\n".join(sections)
        
        return {
            "system": system_prompt,
            "user": user_prompt
        }
    
    def _format_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Format template with variables"""
        try:
            # Use safe substitute to avoid KeyError on missing variables
            from string import Template
            t = Template(template)
            # Convert dict keys to use $ prefix for Template
            template_vars = {k: v for k, v in variables.items()}
            # First try regular substitution
            try:
                return template.format(**template_vars)
            except KeyError:
                # Fallback to Template safe_substitute
                return t.safe_substitute(**template_vars)
        except Exception as e:
            logger.warning(f"Template formatting error: {e}")
            return template
    
    async def create_new_version(
        self,
        client_id: str,
        base_config_id: Optional[UUID] = None,
        changes: Dict[str, Any] = None
    ) -> PromptConfiguration:
        """Create new version of prompt configuration"""
        # Get base configuration
        if base_config_id:
            base_config = await self.get_config_by_id(base_config_id)
        else:
            base_config = await self.get_active_config(client_id)
        
        if not base_config:
            base_config = await self.create_default_config(client_id)
        
        # Create new version
        new_config = base_config.copy(deep=True)
        new_config.id = uuid4()
        new_config.version = base_config.version + 1
        new_config.created_at = datetime.utcnow()
        new_config.updated_at = datetime.utcnow()
        new_config.performance_metrics = {}  # Reset metrics for new version
        
        # Apply changes
        if changes:
            for key, value in changes.items():
                if hasattr(new_config, key):
                    setattr(new_config, key, value)
        
        # Deactivate old versions
        await self._deactivate_old_versions(client_id)
        
        # Save new version
        await self.save_config(new_config)
        
        return new_config
    
    async def _deactivate_old_versions(self, client_id: str):
        """Deactivate all old versions for a client"""
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE prompt_configurations
                SET is_active = false
                WHERE client_id = $1
                """,
                client_id
            )
    
    async def get_config_by_id(self, config_id: UUID) -> Optional[PromptConfiguration]:
        """Get prompt configuration by ID"""
        async with self.db.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM prompt_configurations WHERE id = $1",
                config_id
            )
            
            if result:
                row_dict = dict(result)
                # Ensure JSON fields are proper dicts (DB may store as text)
                json_fields = [
                    'system_prompt_variables', 'section_templates', 'requirement_templates',
                    'performance_metrics'
                ]
                for field in json_fields:
                    if field in row_dict and isinstance(row_dict[field], str):
                        try:
                            row_dict[field] = json.loads(row_dict[field])
                        except Exception:
                            row_dict[field] = {}
                return PromptConfiguration(**row_dict)
            return None
    
    async def get_library_components(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[PromptLibrary]:
        """Get prompt library components"""
        async with self.db.acquire() as conn:
            query = "SELECT * FROM prompt_library WHERE 1=1"
            params = []
            
            if category:
                params.append(category)
                query += f" AND category = ${len(params)}"
            
            if tags:
                params.append(tags)
                query += f" AND tags && ${len(params)}"
            
            query += " ORDER BY usage_count DESC, performance_score DESC"
            
            results = await conn.fetch(query, *params)
            
            return [PromptLibrary(**dict(row)) for row in results]
    
    async def save_library_component(self, component: PromptLibrary) -> PromptLibrary:
        """Save prompt library component"""
        if not component.id:
            component.id = uuid4()
        
        component.updated_at = datetime.utcnow()
        if not component.created_at:
            component.created_at = datetime.utcnow()
        
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO prompt_library (
                    id, name, category, component_type, content,
                    variables, tags, usage_count, performance_score,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    content = EXCLUDED.content,
                    variables = EXCLUDED.variables,
                    tags = EXCLUDED.tags,
                    usage_count = EXCLUDED.usage_count,
                    performance_score = EXCLUDED.performance_score,
                    updated_at = EXCLUDED.updated_at
                """,
                component.id,
                component.name,
                component.category,
                component.component_type,
                component.content,
                json.dumps([v.dict() for v in component.variables]),
                component.tags,
                component.usage_count,
                component.performance_score,
                component.created_at,
                component.updated_at
            )
        
        return component
    
    async def track_performance(
        self,
        config_id: UUID,
        metrics: Dict[str, float]
    ):
        """Track performance metrics for a configuration"""
        async with self.db.acquire() as conn:
            # Get current metrics
            result = await conn.fetchrow(
                "SELECT performance_metrics FROM prompt_configurations WHERE id = $1",
                config_id
            )
            
            if result:
                current_metrics = result['performance_metrics'] or {}
                
                # Update metrics (calculate rolling average)
                for key, value in metrics.items():
                    if key in current_metrics:
                        # Simple exponential moving average
                        current_metrics[key] = 0.7 * current_metrics[key] + 0.3 * value
                    else:
                        current_metrics[key] = value
                
                # Save updated metrics
                await conn.execute(
                    """
                    UPDATE prompt_configurations
                    SET performance_metrics = $2
                    WHERE id = $1
                    """,
                    config_id,
                    json.dumps(current_metrics)
                ) 