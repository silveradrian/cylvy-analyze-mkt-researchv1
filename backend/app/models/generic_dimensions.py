"""
Generic Custom Dimensions Models

Pydantic models for the advanced custom dimensions feature that supports
completely generic, criteria-based analysis dimensions with sophisticated
scoring methodologies.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator


class AIContext(BaseModel):
    """AI context providing overall understanding of dimension purpose and approach."""
    
    general_description: str = Field(
        ..., 
        description="High-level description of what this dimension measures"
    )
    purpose: str = Field(
        ..., 
        description="The specific purpose and goal of this dimension"
    )
    scope: str = Field(
        ..., 
        description="The scope and boundaries of what this dimension covers"
    )
    key_focus_areas: List[str] = Field(
        default_factory=list, 
        description="Specific areas the AI should focus on during analysis"
    )
    analysis_approach: Optional[str] = Field(
        None, 
        description="Specific guidance on how to approach the analysis"
    )


class DimensionCriteria(BaseModel):
    """Flexible criteria structure defining what counts, signals, and exclusions."""
    
    what_counts: str = Field(
        ..., 
        description="Definition of what evidence should be considered for this dimension"
    )
    positive_signals: List[str] = Field(
        default_factory=list, 
        description="Signals that indicate high score or presence"
    )
    negative_signals: List[str] = Field(
        default_factory=list, 
        description="Signals that indicate low score or absence"
    )
    exclusions: List[str] = Field(
        default_factory=list, 
        description="Content that should be excluded from analysis"
    )
    additional_context: Optional[str] = Field(
        None, 
        description="Any additional context for analysis"
    )


class ScoringLevel(BaseModel):
    """Definition of a scoring level with range, label, and requirements."""
    
    range: Tuple[int, int] = Field(
        ..., 
        description="Score range for this level (e.g., [0, 2])"
    )
    label: str = Field(
        ..., 
        description="Human-readable label for this scoring level"
    )
    description: str = Field(
        ..., 
        description="Description of what this scoring level represents"
    )
    requirements: List[str] = Field(
        default_factory=list, 
        description="Specific requirements for achieving this scoring level"
    )
    
    @validator('range')
    def validate_range(cls, v):
        if len(v) != 2 or v[0] > v[1] or v[0] < 0 or v[1] > 10:
            raise ValueError('Range must be [min, max] where 0 <= min <= max <= 10')
        return v


class EvidenceConfig(BaseModel):
    """Configuration for evidence-based scoring requirements."""
    
    min_words: int = Field(
        120, 
        ge=0, 
        description="Minimum number of relevant words for meaningful analysis"
    )
    word_increment: int = Field(
        80, 
        ge=1, 
        description="Word count increment for score improvements"
    )
    max_score_per_increment: float = Field(
        1.0, 
        ge=0, 
        description="Maximum score improvement per word increment"
    )
    specificity_weight: Optional[float] = Field(
        0.3, 
        ge=0, 
        le=1, 
        description="Weight for specificity in evidence analysis"
    )


class ContextualRule(BaseModel):
    """Contextual rule for dynamic scoring adjustments."""
    
    name: str = Field(
        ..., 
        description="Unique name for this rule"
    )
    description: str = Field(
        ..., 
        description="Human-readable description of the rule"
    )
    condition: str = Field(
        ..., 
        description="Condition that triggers this rule (e.g., 'off_topic', 'generic_language')"
    )
    adjustment_type: str = Field(
        ..., 
        description="Type of adjustment: 'cap', 'penalty', or 'bonus'"
    )
    adjustment_value: float = Field(
        ..., 
        description="Numeric value for the adjustment"
    )
    
    @validator('adjustment_type')
    def validate_adjustment_type(cls, v):
        if v not in ['cap', 'penalty', 'bonus']:
            raise ValueError('adjustment_type must be one of: cap, penalty, bonus')
        return v


class ScoringFramework(BaseModel):
    """Configurable scoring framework with levels, evidence requirements, and rules."""
    
    levels: List[ScoringLevel] = Field(
        ..., 
        description="Scoring levels with ranges and requirements"
    )
    evidence_requirements: EvidenceConfig = Field(
        default_factory=EvidenceConfig, 
        description="Requirements for evidence-based scoring"
    )
    contextual_rules: List[ContextualRule] = Field(
        default_factory=list, 
        description="Contextual rules for scoring adjustments"
    )
    
    @validator('levels')
    def validate_levels(cls, v):
        if not v:
            raise ValueError('At least one scoring level is required')
        
        # Check for overlapping ranges
        ranges = [level.range for level in v]
        for i, range1 in enumerate(ranges):
            for j, range2 in enumerate(ranges[i+1:], i+1):
                if (range1[0] <= range2[1] and range2[0] <= range1[1]):
                    raise ValueError(f'Scoring levels {i} and {j} have overlapping ranges')
        
        return v


class GenericCustomDimension(BaseModel):
    """Complete configuration for a generic custom dimension."""
    
    id: Optional[UUID] = None
    client_id: str = Field(..., max_length=100)
    dimension_id: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    
    # Core configuration components
    ai_context: AIContext = Field(
        ..., 
        description="AI context for overall understanding"
    )
    criteria: DimensionCriteria = Field(
        ..., 
        description="Flexible criteria structure"
    )
    scoring_framework: ScoringFramework = Field(
        ..., 
        description="Configurable scoring framework"
    )
    
    # Extensible metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Client-specific metadata"
    )
    
    # System metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = Field(None, max_length=100)
    is_active: bool = True
    
    class Config:
        """Pydantic configuration."""
        orm_mode = True
        use_enum_values = True
        validate_assignment = True


class EvidenceAnalysis(BaseModel):
    """Evidence analysis results for a dimension."""
    
    total_relevant_words: int = Field(
        0, 
        ge=0, 
        description="Total number of relevant words found"
    )
    evidence_threshold_met: bool = Field(
        False, 
        description="Whether the minimum evidence threshold was met"
    )
    specificity_score: int = Field(
        0, 
        ge=0, 
        le=10, 
        description="Score for content specificity (0-10)"
    )
    quality_indicators: Dict[str, float] = Field(
        default_factory=dict, 
        description="Flexible quality metrics"
    )


class ScoringBreakdown(BaseModel):
    """Dynamic scoring breakdown for transparent score calculation."""
    
    base_score: int = Field(
        0, 
        ge=0, 
        le=10, 
        description="Initial base score before adjustments"
    )
    evidence_adjustments: Dict[str, float] = Field(
        default_factory=dict, 
        description="Dynamic evidence-based adjustments"
    )
    contextual_adjustments: Dict[str, float] = Field(
        default_factory=dict, 
        description="Rule-based contextual adjustments"
    )
    scoring_rationale: str = Field(
        "", 
        description="Human-readable explanation of scoring logic"
    )


class GenericDimensionAnalysis(BaseModel):
    """Analysis result for a generic custom dimension."""
    
    id: Optional[UUID] = None
    content_analysis_id: UUID = Field(
        ..., 
        description="Reference to the content analysis"
    )
    dimension_id: str = Field(
        ..., 
        max_length=100, 
        description="ID of the dimension that was analyzed"
    )
    
    # Core analysis results
    final_score: int = Field(
        ..., 
        ge=0, 
        le=10, 
        description="Final score for this dimension (0-10)"
    )
    evidence_summary: Optional[str] = Field(
        None, 
        description="Summary of evidence found for this dimension"
    )
    
    # Flexible analysis components
    evidence_analysis: EvidenceAnalysis = Field(
        default_factory=EvidenceAnalysis, 
        description="Evidence analysis results"
    )
    scoring_breakdown: ScoringBreakdown = Field(
        default_factory=ScoringBreakdown, 
        description="Detailed scoring breakdown"
    )
    
    # AI outputs
    confidence_score: int = Field(
        0, 
        ge=0, 
        le=10, 
        description="AI confidence in the analysis (0-10)"
    )
    detailed_reasoning: Optional[str] = Field(
        None, 
        description="Detailed reasoning for the score"
    )
    matched_criteria: List[str] = Field(
        default_factory=list, 
        description="Criteria that were matched in the content"
    )
    
    # Extensible metadata
    analysis_metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Extensible analysis metadata"
    )
    
    # System metadata
    analyzed_at: Optional[datetime] = None
    model_used: Optional[str] = Field(None, max_length=100)
    analysis_version: str = Field(default="3.0", max_length=20)
    
    class Config:
        """Pydantic configuration."""
        orm_mode = True
        use_enum_values = True
        validate_assignment = True


class GenericDimensionRequest(BaseModel):
    """Request model for creating or updating a generic dimension."""
    
    dimension_id: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    ai_context: AIContext
    criteria: DimensionCriteria
    scoring_framework: ScoringFramework
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenericDimensionUpdate(BaseModel):
    """Request model for updating a generic dimension."""
    
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    ai_context: Optional[AIContext] = None
    criteria: Optional[DimensionCriteria] = None
    scoring_framework: Optional[ScoringFramework] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class GenericAnalysisRequest(BaseModel):
    """Request model for generic content analysis."""
    
    client_id: str = Field(..., max_length=100)
    url: str = Field(..., description="URL of content to analyze")
    analysis_type: str = Field(
        "generic_dimensions", 
        description="Type of analysis to perform"
    )
    dimension_filters: Optional[List[str]] = Field(
        None, 
        description="Optional list of dimension IDs to analyze"
    )


class GenericAnalysisResponse(BaseModel):
    """Response model for generic dimension analysis results."""
    
    analysis_id: UUID = Field(..., description="Unique analysis identifier")
    url: str = Field(..., description="URL that was analyzed")
    client_id: str = Field(..., description="Client ID")
    generic_dimensions: Dict[str, GenericDimensionAnalysis] = Field(
        default_factory=dict, 
        description="Analysis results keyed by dimension ID"
    )
    
    class Config:
        """Pydantic configuration."""
        orm_mode = True
