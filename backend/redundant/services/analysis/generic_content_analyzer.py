"""
Generic Content Analyzer

Enhanced content analysis service that supports completely generic custom dimensions
with evidence-based scoring methodologies and flexible criteria frameworks.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import openai
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.generic_dimensions import (
    GenericCustomDimension,
    GenericDimensionAnalysis,
    EvidenceAnalysis,
    ScoringBreakdown,
)
from app.services.analysis.generic_prompt_generator import GenericPromptGenerator
from app.services.analysis.ai_service import AIService
from loguru import logger


class GenericContentAnalyzer:
    """Enhanced content analyzer for generic custom dimensions."""
    
    def __init__(self):
        self.prompt_generator = GenericPromptGenerator()
        self.ai_service = AIService()
        self.openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def analyze_content_with_generic_dimensions(
        self,
        content: str,
        url: str,
        client_id: str,
        dimensions: List[GenericCustomDimension],
        content_analysis_id: UUID,
        db: Session
    ) -> Dict[str, GenericDimensionAnalysis]:
        """
        Analyze content against generic custom dimensions.
        
        Args:
            content: The content to analyze
            url: URL of the content
            client_id: Client identifier
            dimensions: List of dimension configurations
            content_analysis_id: ID of the parent content analysis
            db: Database session
            
        Returns:
            Dictionary of dimension analysis results keyed by dimension_id
        """
        
        try:
            logger.info(f"Starting generic dimension analysis for {len(dimensions)} dimensions")
            
            # Generate dynamic prompts
            prompts = self.prompt_generator.build_generic_dimension_prompt(
                content=content,
                dimensions=dimensions,
                url=url,
                client_id=client_id
            )
            
            # Generate dynamic schema
            function_schema = self.prompt_generator.build_generic_analysis_schema(dimensions)
            
            # Call OpenAI with dynamic prompts and schema
            response = await self._call_openai_analysis(
                prompts=prompts,
                function_schema=function_schema
            )
            
            # Process and store results
            analysis_results = await self._process_analysis_response(
                response=response,
                dimensions=dimensions,
                content_analysis_id=content_analysis_id,
                content=content,
                db=db
            )
            
            logger.info(f"Completed generic dimension analysis with {len(analysis_results)} results")
            return analysis_results
            
        except Exception as e:
            logger.error(f"Error in generic dimension analysis: {e}")
            raise
    
    async def _call_openai_analysis(
        self,
        prompts: Dict[str, str],
        function_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call OpenAI API with dynamic prompts and schema."""
        
        try:
            messages = [
                {"role": "system", "content": prompts["system"]},
                {"role": "user", "content": prompts["user"]}
            ]
            
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL_GENERIC_ANALYSIS,
                messages=messages,
                functions=[{
                    "name": "analyze_generic_dimensions",
                    "description": "Analyze content against generic custom dimensions",
                    "parameters": function_schema
                }],
                function_call={"name": "analyze_generic_dimensions"},
                temperature=0.1,
                max_tokens=32768  # GPT-4.1 max output tokens
            )
            
            if response.choices[0].message.function_call:
                function_args = response.choices[0].message.function_call.arguments
                return json.loads(function_args)
            else:
                raise ValueError("No function call in OpenAI response")
                
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    async def _process_analysis_response(
        self,
        response: Dict[str, Any],
        dimensions: List[GenericCustomDimension],
        content_analysis_id: UUID,
        content: str,
        db: Session
    ) -> Dict[str, GenericDimensionAnalysis]:
        """Process OpenAI response and create analysis results."""
        
        analysis_results = {}
        generic_dimensions_data = response.get("generic_dimensions", {})
        
        for dimension in dimensions:
            dimension_id = dimension.dimension_id
            
            if dimension_id not in generic_dimensions_data:
                logger.warning(f"Missing analysis for dimension: {dimension_id}")
                continue
            
            dimension_data = generic_dimensions_data[dimension_id]
            
            try:
                # Create analysis result
                analysis = await self._create_dimension_analysis(
                    dimension=dimension,
                    dimension_data=dimension_data,
                    content_analysis_id=content_analysis_id,
                    content=content
                )
                
                # Store in database
                await self._store_dimension_analysis(analysis, db)
                
                analysis_results[dimension_id] = analysis
                
            except Exception as e:
                logger.error(f"Error processing dimension {dimension_id}: {e}")
                continue
        
        return analysis_results
    
    async def _create_dimension_analysis(
        self,
        dimension: GenericCustomDimension,
        dimension_data: Dict[str, Any],
        content_analysis_id: UUID,
        content: str
    ) -> GenericDimensionAnalysis:
        """Create a GenericDimensionAnalysis object from response data."""
        
        # Extract evidence analysis
        evidence_data = dimension_data.get("evidence_analysis", {})
        evidence_analysis = EvidenceAnalysis(
            total_relevant_words=evidence_data.get("total_relevant_words", 0),
            evidence_threshold_met=evidence_data.get("evidence_threshold_met", False),
            specificity_score=evidence_data.get("specificity_score", 0),
            quality_indicators=evidence_data.get("quality_indicators", {})
        )
        
        # Extract scoring breakdown
        scoring_data = dimension_data.get("scoring_breakdown", {})
        scoring_breakdown = ScoringBreakdown(
            base_score=scoring_data.get("base_score", 0),
            evidence_adjustments=scoring_data.get("evidence_adjustments", {}),
            contextual_adjustments=scoring_data.get("contextual_adjustments", {}),
            scoring_rationale=scoring_data.get("scoring_rationale", "")
        )
        
        # Apply post-processing validations and adjustments
        final_score = await self._apply_scoring_validations(
            dimension=dimension,
            raw_score=dimension_data.get("final_score", 0),
            evidence_analysis=evidence_analysis,
            scoring_breakdown=scoring_breakdown
        )
        
        # Create the analysis object
        analysis = GenericDimensionAnalysis(
            content_analysis_id=content_analysis_id,
            dimension_id=dimension.dimension_id,
            final_score=final_score,
            evidence_summary=dimension_data.get("evidence_summary", ""),
            evidence_analysis=evidence_analysis,
            scoring_breakdown=scoring_breakdown,
            confidence_score=dimension_data.get("confidence_score", 0),
            detailed_reasoning=dimension_data.get("detailed_reasoning", ""),
            matched_criteria=dimension_data.get("matched_criteria", []),
            analysis_metadata={
                "processing_time_ms": dimension_data.get("analysis_metadata", {}).get("processing_time_ms", 0),
                "criteria_matches": len(dimension_data.get("matched_criteria", [])),
                "word_count": len(content.split()),
                "analysis_version": "3.0"
            },
            analyzed_at=datetime.utcnow(),
            model_used=settings.OPENAI_MODEL_GENERIC_ANALYSIS,
            analysis_version="3.0"
        )
        
        return analysis
    
    async def _apply_scoring_validations(
        self,
        dimension: GenericCustomDimension,
        raw_score: int,
        evidence_analysis: EvidenceAnalysis,
        scoring_breakdown: ScoringBreakdown
    ) -> int:
        """Apply validation and adjustment rules to the final score."""
        
        final_score = raw_score
        
        # Apply evidence threshold rules
        evidence_config = dimension.scoring_framework.evidence_requirements
        if evidence_analysis.total_relevant_words < evidence_config.min_words:
            # Penalize scores when evidence is insufficient
            max_allowed_score = 4  # Cap at 4 when evidence is insufficient
            if final_score > max_allowed_score:
                final_score = max_allowed_score
                logger.debug(f"Score capped at {max_allowed_score} due to insufficient evidence")
        
        # Apply contextual rules
        for rule in dimension.scoring_framework.contextual_rules:
            rule_name = rule.name.lower()
            
            # Check if rule should be applied (simplified condition matching)
            should_apply = False
            
            if "off_topic" in rule_name and evidence_analysis.specificity_score < 3:
                should_apply = True
            elif "generic" in rule_name and evidence_analysis.specificity_score < 5:
                should_apply = True
            elif "marketing" in rule_name and "marketing" in scoring_breakdown.scoring_rationale.lower():
                should_apply = True
            
            if should_apply:
                if rule.adjustment_type == "cap":
                    final_score = min(final_score, int(rule.adjustment_value))
                elif rule.adjustment_type == "penalty":
                    final_score = max(0, final_score - int(rule.adjustment_value))
                elif rule.adjustment_type == "bonus":
                    final_score = min(10, final_score + int(rule.adjustment_value))
                
                logger.debug(f"Applied rule '{rule.name}': {rule.adjustment_type} {rule.adjustment_value}")
        
        # Ensure score is within bounds
        final_score = max(0, min(10, final_score))
        
        return final_score
    
    async def _store_dimension_analysis(
        self,
        analysis: GenericDimensionAnalysis,
        db: Session
    ) -> None:
        """Store dimension analysis in the database."""
        
        try:
            db.execute(
                text("""
                    INSERT INTO generic_dimension_analysis (
                        id, content_analysis_id, dimension_id, final_score, evidence_summary,
                        evidence_analysis, scoring_breakdown, confidence_score, detailed_reasoning,
                        matched_criteria, analysis_metadata, analyzed_at, model_used, analysis_version
                    ) VALUES (
                        gen_random_uuid(), :content_analysis_id, :dimension_id, :final_score, :evidence_summary,
                        :evidence_analysis, :scoring_breakdown, :confidence_score, :detailed_reasoning,
                        :matched_criteria, :analysis_metadata, :analyzed_at, :model_used, :analysis_version
                    )
                """),
                {
                    "content_analysis_id": analysis.content_analysis_id,
                    "dimension_id": analysis.dimension_id,
                    "final_score": analysis.final_score,
                    "evidence_summary": analysis.evidence_summary,
                    "evidence_analysis": analysis.evidence_analysis.dict(),
                    "scoring_breakdown": analysis.scoring_breakdown.dict(),
                    "confidence_score": analysis.confidence_score,
                    "detailed_reasoning": analysis.detailed_reasoning,
                    "matched_criteria": json.dumps(analysis.matched_criteria),
                    "analysis_metadata": analysis.analysis_metadata,
                    "analyzed_at": analysis.analyzed_at,
                    "model_used": analysis.model_used,
                    "analysis_version": analysis.analysis_version
                }
            )
            
            logger.debug(f"Stored analysis for dimension: {analysis.dimension_id}")
            
        except Exception as e:
            logger.error(f"Failed to store dimension analysis: {e}")
            raise
    
    async def get_client_dimensions(
        self,
        client_id: str,
        dimension_filters: Optional[List[str]],
        db: Session
    ) -> List[GenericCustomDimension]:
        """Get active generic dimensions for a client."""
        
        try:
            query = """
                SELECT * FROM generic_custom_dimensions 
                WHERE client_id = :client_id AND is_active = true
            """
            params = {"client_id": client_id}
            
            if dimension_filters:
                placeholders = ",".join([f":dim_{i}" for i in range(len(dimension_filters))])
                query += f" AND dimension_id IN ({placeholders})"
                for i, dim_id in enumerate(dimension_filters):
                    params[f"dim_{i}"] = dim_id
            
            query += " ORDER BY created_at ASC"
            
            results = db.execute(text(query), params).fetchall()
            
            dimensions = []
            for row in results:
                from app.models.generic_dimensions import (
                    AIContext, DimensionCriteria, ScoringFramework
                )
                
                dimension = GenericCustomDimension(
                    id=row.id,
                    client_id=row.client_id,
                    dimension_id=row.dimension_id,
                    name=row.name,
                    description=row.description,
                    ai_context=AIContext(**row.ai_context),
                    criteria=DimensionCriteria(**row.criteria),
                    scoring_framework=ScoringFramework(**row.scoring_framework),
                    metadata=row.metadata or {},
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    created_by=row.created_by,
                    is_active=row.is_active
                )
                dimensions.append(dimension)
            
            return dimensions
            
        except Exception as e:
            logger.error(f"Error getting client dimensions: {e}")
            raise
    
    def calculate_evidence_metrics(self, content: str, criteria: dict) -> Dict[str, Any]:
        """Calculate evidence metrics for content analysis."""
        
        words = content.split()
        total_words = len(words)
        
        # Count relevant words based on positive signals
        relevant_words = 0
        positive_signals = criteria.get("positive_signals", [])
        
        for signal in positive_signals:
            # Simple keyword matching - could be enhanced with NLP
            signal_words = signal.lower().split()
            for word in signal_words:
                relevant_words += content.lower().count(word)
        
        # Calculate specificity score based on technical terms and specific examples
        technical_patterns = [
            r'\b\d+%\b',  # Percentages
            r'\b\d+\.\d+\b',  # Numbers with decimals
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'\b\w+[Tt]ech\w*\b',  # Technical terms
            r'\b[Ii]mplementation\b',  # Implementation
            r'\b[Pp]rocess\b',  # Process
            r'\b[Ss]olution\b',  # Solution
        ]
        
        specificity_indicators = 0
        for pattern in technical_patterns:
            specificity_indicators += len(re.findall(pattern, content))
        
        # Normalize specificity score (0-10)
        specificity_score = min(10, max(0, int(specificity_indicators / max(1, total_words / 100) * 10)))
        
        return {
            "total_relevant_words": relevant_words,
            "evidence_threshold_met": relevant_words >= 120,  # Default threshold
            "specificity_score": specificity_score,
            "quality_indicators": {
                "depth_score": min(10, relevant_words // 20),
                "relevance_score": min(10, relevant_words // 15),
                "specificity_score": specificity_score
            }
        }
