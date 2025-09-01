"""
Prompt Configuration Models for LLM Analysis
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class PromptSection(str, Enum):
    """Prompt section types"""
    SYSTEM = "system"
    PERSONAS = "personas"
    JTBD_PHASES = "jtbd_phases"
    CONTENT_CATEGORIES = "content_categories"
    ANALYSIS_REQUIREMENTS = "analysis_requirements"
    SCORING_CRITERIA = "scoring_criteria"
    OUTPUT_FORMAT = "output_format"
    CUSTOM_INSTRUCTIONS = "custom_instructions"


class PromptTemplate(BaseModel):
    """Individual prompt template"""
    id: Optional[UUID] = None
    name: str = Field(..., description="Template name")
    section: PromptSection = Field(..., description="Which section this template belongs to")
    template: str = Field(..., description="Template text with placeholders")
    variables: List[str] = Field(default_factory=list, description="Required variables for this template")
    description: Optional[str] = Field(None, description="Template description")
    is_active: bool = Field(True, description="Whether template is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PromptConfiguration(BaseModel):
    """Complete prompt configuration for a client"""
    id: Optional[UUID] = None
    client_id: str = Field(..., description="Client ID")
    name: str = Field(..., description="Configuration name")
    version: int = Field(1, description="Configuration version")
    
    # System prompt configuration
    system_prompt_template: str = Field(
        default="You are an expert B2B content analyst specializing in {specializations}. {additional_context}",
        description="System prompt template"
    )
    system_prompt_variables: Dict[str, str] = Field(
        default_factory=lambda: {
            "specializations": "buyer journey mapping, persona alignment, and Jobs to be Done framework",
            "additional_context": "Analyze content with deep understanding of B2B buying processes."
        }
    )
    
    # Section templates
    section_templates: Dict[PromptSection, str] = Field(
        default_factory=dict,
        description="Templates for each prompt section"
    )
    
    # Analysis requirements template
    analysis_requirements_template: str = Field(
        default="""## ANALYSIS REQUIREMENTS:

{requirements_list}

Provide deep, actionable insights focused on B2B buying behavior and decision-making processes.""",
        description="Template for analysis requirements section"
    )
    
    # Individual requirement templates
    requirement_templates: Dict[str, str] = Field(
        default_factory=lambda: {
            "summary": "**Summary**: {summary_instructions}",
            "persona_alignment": """**Persona Alignment**: 
   - {persona_identification_instructions}
   - {persona_scoring_instructions}
   - {persona_reasoning_instructions}""",
            "jtbd_identification": """**JTBD Phase Identification**:
   - {phase_identification_instructions}
   - {phase_scoring_instructions}
   - {phase_reasoning_instructions}""",
            "buyer_intent": "**Buyer Intent Signals**: {intent_instructions}",
            "classification": "**Content Classification**: {classification_instructions}",
            "topics": "**Key Topics**: {topics_instructions}",
            "sentiment": "**Sentiment**: {sentiment_instructions}"
        }
    )
    
    # Scoring criteria templates
    persona_scoring_criteria: List[str] = Field(
        default_factory=lambda: [
            "How well it addresses their goals",
            "How well it speaks to their pain points",
            "Match with their decision criteria",
            "Alignment with content preferences"
        ]
    )
    
    jtbd_scoring_criteria: List[str] = Field(
        default_factory=lambda: [
            "How well it answers the phase's key questions",
            "Match with buyer mindset",
            "Appropriateness of content type for the phase"
        ]
    )
    
    # Output format configuration
    output_format_instructions: str = Field(
        default="Provide comprehensive analysis with specific examples and actionable insights.",
        description="Instructions for output format"
    )
    
    # Advanced configuration
    temperature_override: Optional[float] = Field(None, description="Override default temperature")
    max_tokens_override: Optional[int] = Field(None, description="Override default max tokens")
    model_override: Optional[str] = Field(None, description="Override default model")
    
    # Experimental features
    enable_chain_of_thought: bool = Field(False, description="Enable chain-of-thought prompting")
    enable_self_critique: bool = Field(False, description="Enable self-critique step")
    custom_functions: Optional[List[Dict[str, Any]]] = Field(None, description="Custom function definitions")
    
    # Metadata
    is_active: bool = Field(True, description="Whether configuration is active")
    performance_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Performance metrics for this configuration"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


class PromptOptimizationRequest(BaseModel):
    """Request to optimize prompts based on performance data"""
    client_id: str
    optimization_goal: str = Field(..., description="What to optimize for (accuracy, speed, cost, etc.)")
    sample_size: int = Field(100, description="Number of analyses to consider")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Optimization constraints")


class PromptTestRequest(BaseModel):
    """Request to test a prompt configuration"""
    client_id: str
    configuration_id: Optional[UUID] = None
    test_configuration: Optional[PromptConfiguration] = None
    test_urls: List[str] = Field(..., description="URLs to test with")
    compare_with_current: bool = Field(True, description="Compare with current configuration")


class PromptTestResult(BaseModel):
    """Result of prompt configuration test"""
    configuration_id: Optional[UUID]
    test_id: UUID
    metrics: Dict[str, float] = Field(..., description="Performance metrics")
    sample_outputs: List[Dict[str, Any]] = Field(..., description="Sample analysis outputs")
    comparison_results: Optional[Dict[str, Any]] = None
    recommendations: List[str] = Field(default_factory=list)
    completed_at: datetime


class PromptVariable(BaseModel):
    """Definition of a prompt variable"""
    name: str = Field(..., description="Variable name")
    description: str = Field(..., description="What this variable controls")
    type: str = Field(..., description="Variable type (string, list, number, etc.)")
    default_value: Any = Field(..., description="Default value")
    allowed_values: Optional[List[Any]] = Field(None, description="Allowed values if constrained")
    examples: List[str] = Field(default_factory=list, description="Example values")


class PromptLibrary(BaseModel):
    """Library of reusable prompt components"""
    id: Optional[UUID] = None
    name: str = Field(..., description="Component name")
    category: str = Field(..., description="Component category")
    component_type: str = Field(..., description="Type of component")
    content: str = Field(..., description="Component content")
    variables: List[PromptVariable] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    usage_count: int = Field(0, description="How many times this has been used")
    performance_score: Optional[float] = Field(None, description="Average performance score")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None 