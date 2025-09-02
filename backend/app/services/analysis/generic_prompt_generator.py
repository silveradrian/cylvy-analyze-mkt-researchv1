"""
Generic Dimension Prompt Generator

Dynamic prompt generation system that adapts to any dimension configuration.
Creates AI prompts dynamically based on dimension configuration without hardcoded logic.
"""

from typing import Dict, List, Any
from app.models.generic_dimensions import (
    GenericCustomDimension,
    AIContext,
    DimensionCriteria,
    ScoringFramework,
    ScoringLevel,
    EvidenceConfig,
    ContextualRule
)


class GenericPromptGenerator:
    """Dynamic prompt generator for generic custom dimensions."""
    
    def build_generic_dimension_prompt(
        self, 
        content: str, 
        dimensions: List[GenericCustomDimension],
        url: str,
        client_id: str
    ) -> Dict[str, str]:
        """
        Build a complete prompt for analyzing content with generic dimensions.
        
        Args:
            content: The content to analyze
            dimensions: List of dimension configurations
            url: URL of the content being analyzed
            client_id: Client identifier
            
        Returns:
            Dict with 'system' and 'user' prompts
        """
        
        # Build system prompt
        system_prompt = self._build_system_prompt(client_id)
        
        # Build user prompt with dimension sections
        user_prompt_sections = []
        
        # Header
        user_prompt_sections.append(f"Analyze this content from: {url}")
        
        # Add dimension analysis sections
        for dimension in dimensions:
            section = self._build_dimension_section(dimension)
            user_prompt_sections.append(section)
        
        # Add analysis requirements
        analysis_requirements = self._build_analysis_requirements(dimensions)
        user_prompt_sections.append(analysis_requirements)
        
        # Add output format
        output_format = self._build_output_format(dimensions)
        user_prompt_sections.append(output_format)
        
        # Add content
        user_prompt_sections.append(f"## CONTENT TO ANALYZE:\n\n{content}")
        
        user_prompt = "\n\n".join(user_prompt_sections)
        
        return {
            "system": system_prompt,
            "user": user_prompt
        }
    
    def _build_system_prompt(self, client_id: str) -> str:
        """Build system prompt for generic dimension analysis."""
        
        return f"""You are an expert content analyst specializing in evaluating digital content across multiple custom dimensions for client {client_id}.

Your role is to:
1. Analyze content against completely customizable dimension frameworks
2. Apply evidence-based scoring methodologies  
3. Provide transparent, rationale-driven assessments
4. Adapt your analysis approach based on dimension-specific AI context

Key principles:
- Follow each dimension's AI context to understand what it measures fundamentally
- Apply dimension-specific scoring frameworks accurately
- Base scores on evidence depth and quality thresholds
- Apply contextual rules for score adjustments
- Provide detailed reasoning for all assessments
- Be precise and consistent in your evaluations

You will analyze content against custom dimensions with flexible criteria, scoring levels, and evidence requirements. Each dimension may have completely different purposes, scopes, and evaluation approaches."""

    def _build_dimension_section(self, dimension: GenericCustomDimension) -> str:
        """Build a complete analysis section for a single dimension."""
        
        section_parts = []
        
        # Dimension header
        section_parts.append(f"## ANALYZE: {dimension.name} (Score 0-10)")
        
        # AI Context section (critical for understanding)
        ai_context_section = self._build_ai_context_section(dimension.ai_context)
        section_parts.append(ai_context_section)
        
        # Description
        if dimension.description:
            section_parts.append(f"**Description**: {dimension.description}")
        
        # Criteria sections
        criteria_section = self._build_criteria_section(dimension.criteria)
        section_parts.append(criteria_section)
        
        # Scoring framework
        scoring_section = self._build_scoring_framework_section(dimension.scoring_framework)
        section_parts.append(scoring_section)
        
        # Metadata instructions (if any)
        if dimension.metadata:
            metadata_section = self._build_metadata_instructions(dimension.metadata)
            section_parts.append(metadata_section)
        
        return "\n\n".join(section_parts)
    
    def _build_ai_context_section(self, ai_context: AIContext) -> str:
        """Build AI context section to provide overall understanding."""
        
        context_parts = [
            "**AI CONTEXT & OVERALL UNDERSTANDING**:",
            "",
            f"**General Description**: {ai_context.general_description}",
            "",
            f"**Purpose**: {ai_context.purpose}",
            "",
            f"**Scope**: {ai_context.scope}",
            ""
        ]
        
        # Key focus areas
        if ai_context.key_focus_areas:
            context_parts.append("**Key Focus Areas**:")
            for area in ai_context.key_focus_areas:
                context_parts.append(f"- {area}")
            context_parts.append("")
        
        # Analysis approach
        if ai_context.analysis_approach:
            context_parts.append(f"**Analysis Approach**: {ai_context.analysis_approach}")
            context_parts.append("")
        
        # Emphasis block
        context_parts.extend([
            "---",
            "**IMPORTANT**: Before analyzing the specific criteria below, consider this overall context to understand what this dimension is fundamentally measuring and how to approach the analysis.",
            "---"
        ])
        
        return "\n".join(context_parts)
    
    def _build_criteria_section(self, criteria: DimensionCriteria) -> str:
        """Build criteria section with what counts, signals, and exclusions."""
        
        criteria_parts = []
        
        # What counts
        criteria_parts.append(f"**What Counts**: {criteria.what_counts}")
        
        # Positive signals
        if criteria.positive_signals:
            criteria_parts.append("**Positive Signals**:")
            for signal in criteria.positive_signals:
                criteria_parts.append(f"- {signal}")
        
        # Negative signals  
        if criteria.negative_signals:
            criteria_parts.append("**Negative Signals**:")
            for signal in criteria.negative_signals:
                criteria_parts.append(f"- {signal}")
        
        # Exclusions
        if criteria.exclusions:
            criteria_parts.append("**Exclusions**:")
            for exclusion in criteria.exclusions:
                criteria_parts.append(f"- {exclusion}")
        
        # Additional context
        if criteria.additional_context:
            criteria_parts.append(f"**Additional Context**: {criteria.additional_context}")
        
        return "\n\n".join(criteria_parts)
    
    def _build_scoring_framework_section(self, framework: ScoringFramework) -> str:
        """Build scoring framework section with levels, evidence, and rules."""
        
        framework_parts = []
        
        # Scoring levels
        framework_parts.append("**Scoring Framework**:")
        for level in framework.levels:
            range_text = f"{level.range[0]}-{level.range[1]}"
            requirements = "; ".join(level.requirements) if level.requirements else "See general criteria"
            framework_parts.append(f"- **{range_text} ({level.label})**: {level.description} - {requirements}")
        
        # Evidence requirements
        evidence_section = self._build_evidence_requirements_section(framework.evidence_requirements)
        framework_parts.append("")
        framework_parts.append(evidence_section)
        
        # Contextual rules
        if framework.contextual_rules:
            rules_section = self._build_contextual_rules_section(framework.contextual_rules)
            framework_parts.append("")
            framework_parts.append(rules_section)
        
        return "\n".join(framework_parts)
    
    def _build_evidence_requirements_section(self, evidence_config: EvidenceConfig) -> str:
        """Build evidence requirements section."""
        
        requirements_parts = [
            "**Evidence Requirements**:",
            f"- Minimum {evidence_config.min_words} relevant words for meaningful analysis",
            f"- Each additional {evidence_config.word_increment} words can improve score by up to +{evidence_config.max_score_per_increment} point(s)"
        ]
        
        if evidence_config.specificity_weight is not None:
            requirements_parts.append(f"- Specificity weighting: {evidence_config.specificity_weight}")
        
        return "\n".join(requirements_parts)
    
    def _build_contextual_rules_section(self, rules: List[ContextualRule]) -> str:
        """Build contextual rules section."""
        
        rules_parts = ["**Contextual Rules**:"]
        
        for rule in rules:
            adjustment_desc = f"{rule.adjustment_type}: {rule.adjustment_value}"
            rules_parts.append(f"- **{rule.name}**: {rule.description} ({adjustment_desc})")
        
        return "\n".join(rules_parts)
    
    def _build_metadata_instructions(self, metadata: Dict[str, Any]) -> str:
        """Build metadata-specific instructions if relevant to analysis."""
        
        # Extract analysis-relevant metadata
        instructions = []
        
        if "priority" in metadata:
            instructions.append(f"**Priority Level**: {metadata['priority']} - Apply appropriate attention level")
        
        if "review_required" in metadata and metadata["review_required"]:
            instructions.append("**Review Required**: Provide extra detailed reasoning for review")
        
        if "domain" in metadata:
            instructions.append(f"**Domain Context**: Focus on {metadata['domain']}-specific indicators")
        
        if instructions:
            return "**Additional Instructions**:\n" + "\n".join(instructions)
        
        return ""
    
    def _build_analysis_requirements(self, dimensions: List[GenericCustomDimension]) -> str:
        """Build general analysis requirements section."""
        
        dimension_names = [dim.name for dim in dimensions]
        
        return f"""## ANALYSIS REQUIREMENTS:

For each dimension ({', '.join(dimension_names)}), you must provide:

1. **Final Score (0-10)**: Based on the scoring framework for that dimension
2. **Evidence Summary**: Brief summary of key evidence found
3. **Evidence Analysis**: 
   - Total relevant words counted
   - Whether evidence threshold was met
   - Specificity score (0-10)
   - Quality indicators as appropriate
4. **Scoring Breakdown**:
   - Base score before adjustments
   - Evidence-based adjustments applied
   - Contextual rule adjustments applied  
   - Scoring rationale explaining the logic
5. **Confidence Score (0-10)**: Your confidence in this analysis
6. **Detailed Reasoning**: Thorough explanation of your assessment
7. **Matched Criteria**: List of criteria that were found in the content
8. **Analysis Metadata**: Any relevant analysis metadata

**CRITICAL**: Apply each dimension's AI context to understand the fundamental purpose before analyzing specific criteria. Use the scoring framework and evidence requirements exactly as configured for each dimension."""
    
    def _build_output_format(self, dimensions: List[GenericCustomDimension]) -> str:
        """Build dynamic output format based on dimensions."""
        
        # Create the response structure
        example_dimensions = {}
        for dim in dimensions:
            example_dimensions[dim.dimension_id] = {
                "final_score": 7,
                "evidence_summary": "Summary of evidence for this dimension...",
                "evidence_analysis": {
                    "total_relevant_words": 245,
                    "evidence_threshold_met": True,
                    "specificity_score": 8,
                    "quality_indicators": {
                        "depth_score": 7,
                        "relevance_score": 8
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
                    "scoring_rationale": "Detailed scoring explanation..."
                },
                "confidence_score": 8,
                "detailed_reasoning": "Thorough reasoning for the assessment...",
                "matched_criteria": ["positive_signal_1", "evidence_requirement_2"],
                "analysis_metadata": {
                    "processing_time_ms": 1250,
                    "criteria_matches": 5
                }
            }
        
        return f"""## OUTPUT FORMAT:

Return your analysis as a JSON object with this EXACT structure:

```json
{{
  "generic_dimensions": {example_dimensions}
}}
```

**CRITICAL REQUIREMENTS**:
- Include ALL dimensions in the response
- Follow the exact field names and structure shown
- Provide numeric scores within the specified ranges
- Include detailed reasoning for each dimension
- Apply dimension-specific scoring frameworks accurately"""

    def build_generic_analysis_schema(self, dimensions: List[GenericCustomDimension]) -> Dict[str, Any]:
        """Build OpenAI function schema dynamically based on configured dimensions."""
        
        # Build properties for each dimension
        dimension_properties = {}
        for dimension in dimensions:
            dimension_properties[dimension.dimension_id] = {
                "type": "object",
                "properties": {
                    "final_score": {
                        "type": "integer", 
                        "minimum": 0, 
                        "maximum": 10,
                        "description": f"Final score for {dimension.name} (0-10)"
                    },
                    "evidence_summary": {
                        "type": "string",
                        "description": f"Summary of evidence found for {dimension.name}"
                    },
                    "evidence_analysis": {
                        "type": "object",
                        "properties": {
                            "total_relevant_words": {"type": "integer", "minimum": 0},
                            "evidence_threshold_met": {"type": "boolean"},
                            "specificity_score": {"type": "integer", "minimum": 0, "maximum": 10},
                            "quality_indicators": {
                                "type": "object",
                                "additionalProperties": {"type": "number", "minimum": 0, "maximum": 10}
                            }
                        },
                        "required": ["total_relevant_words", "evidence_threshold_met", "specificity_score"]
                    },
                    "scoring_breakdown": {
                        "type": "object",
                        "properties": {
                            "base_score": {"type": "integer", "minimum": 0, "maximum": 10},
                            "evidence_adjustments": {
                                "type": "object",
                                "additionalProperties": {"type": "number"}
                            },
                            "contextual_adjustments": {
                                "type": "object", 
                                "additionalProperties": {"type": "number"}
                            },
                            "scoring_rationale": {"type": "string"}
                        },
                        "required": ["base_score", "scoring_rationale"]
                    },
                    "confidence_score": {
                        "type": "integer", 
                        "minimum": 0, 
                        "maximum": 10,
                        "description": "Confidence in this analysis (0-10)"
                    },
                    "detailed_reasoning": {
                        "type": "string",
                        "description": "Detailed reasoning for the assessment"
                    },
                    "matched_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of criteria that were matched in the content"
                    },
                    "analysis_metadata": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Extensible analysis metadata"
                    }
                },
                "required": [
                    "final_score", 
                    "evidence_summary", 
                    "evidence_analysis",
                    "scoring_breakdown",
                    "confidence_score", 
                    "detailed_reasoning",
                    "matched_criteria"
                ]
            }
        
        # Base schema structure
        schema = {
            "type": "object",
            "properties": {
                "generic_dimensions": {
                    "type": "object",
                    "properties": dimension_properties,
                    "required": list(dimension_properties.keys()),
                    "description": "Analysis results for all configured dimensions"
                }
            },
            "required": ["generic_dimensions"]
        }
        
        return schema
