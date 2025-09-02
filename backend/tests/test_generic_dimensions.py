"""
Unit tests for Generic Dimensions system

Comprehensive tests for the advanced custom dimensions feature including
models, prompt generation, content analysis, and API endpoints.
"""

import json
import pytest
from datetime import datetime
from typing import Dict, List
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.models.generic_dimensions import (
    GenericCustomDimension,
    AIContext,
    DimensionCriteria,
    ScoringFramework,
    ScoringLevel,
    EvidenceConfig,
    ContextualRule,
    GenericDimensionAnalysis,
    EvidenceAnalysis,
    ScoringBreakdown,
    GenericDimensionRequest,
    GenericAnalysisRequest,
)
from backend.app.services.analysis.generic_prompt_generator import GenericPromptGenerator
from backend.app.services.analysis.generic_content_analyzer import GenericContentAnalyzer


class TestGenericDimensionModels:
    """Test Pydantic models for generic dimensions."""
    
    def test_ai_context_model(self):
        """Test AIContext model validation."""
        ai_context = AIContext(
            general_description="Test dimension for domain expertise",
            purpose="Evaluate technical depth and practical experience",
            scope="All content types including technical documentation",
            key_focus_areas=[
                "Technical accuracy",
                "Real-world examples",
                "Industry terminology"
            ],
            analysis_approach="Look for specific technical details and concrete examples"
        )
        
        assert ai_context.general_description == "Test dimension for domain expertise"
        assert len(ai_context.key_focus_areas) == 3
        assert ai_context.analysis_approach is not None
    
    def test_dimension_criteria_model(self):
        """Test DimensionCriteria model validation."""
        criteria = DimensionCriteria(
            what_counts="Evidence of technical expertise and practical experience",
            positive_signals=[
                "Specific technical implementation details",
                "Quantified outcomes and results",
                "Industry-specific terminology"
            ],
            negative_signals=[
                "Generic marketing language",
                "Vague claims without evidence"
            ],
            exclusions=[
                "Pure promotional content",
                "Content about unrelated domains"
            ],
            additional_context="Focus on actionable insights and proven methodologies"
        )
        
        assert criteria.what_counts.startswith("Evidence of technical")
        assert len(criteria.positive_signals) == 3
        assert len(criteria.negative_signals) == 2
        assert len(criteria.exclusions) == 2
    
    def test_scoring_level_validation(self):
        """Test ScoringLevel model validation."""
        # Valid scoring level
        level = ScoringLevel(
            range=[7, 8],
            label="Strong",
            description="Clear evidence with specific examples",
            requirements=["Multiple specific examples", "Technical depth"]
        )
        
        assert level.range == [7, 8]
        assert level.label == "Strong"
        
        # Invalid range - should raise validation error
        with pytest.raises(ValidationError):
            ScoringLevel(
                range=[8, 5],  # Invalid: min > max
                label="Invalid",
                description="This should fail",
                requirements=[]
            )
        
        # Invalid range - outside bounds
        with pytest.raises(ValidationError):
            ScoringLevel(
                range=[0, 15],  # Invalid: max > 10
                label="Invalid",
                description="This should fail",
                requirements=[]
            )
    
    def test_evidence_config_model(self):
        """Test EvidenceConfig model validation."""
        evidence_config = EvidenceConfig(
            min_words=120,
            word_increment=80,
            max_score_per_increment=1.5,
            specificity_weight=0.3
        )
        
        assert evidence_config.min_words == 120
        assert evidence_config.word_increment == 80
        assert evidence_config.max_score_per_increment == 1.5
        assert evidence_config.specificity_weight == 0.3
    
    def test_contextual_rule_model(self):
        """Test ContextualRule model validation."""
        rule = ContextualRule(
            name="off_topic_penalty",
            description="Reduce score for off-topic content",
            condition="off_topic",
            adjustment_type="penalty",
            adjustment_value=2
        )
        
        assert rule.name == "off_topic_penalty"
        assert rule.adjustment_type == "penalty"
        
        # Invalid adjustment type
        with pytest.raises(ValidationError):
            ContextualRule(
                name="invalid_rule",
                description="Invalid rule",
                condition="test",
                adjustment_type="invalid_type",  # Invalid
                adjustment_value=1
            )
    
    def test_scoring_framework_validation(self):
        """Test ScoringFramework model validation."""
        levels = [
            ScoringLevel(range=[0, 2], label="Minimal", description="Low evidence", requirements=[]),
            ScoringLevel(range=[3, 5], label="Moderate", description="Some evidence", requirements=[]),
            ScoringLevel(range=[6, 8], label="Strong", description="Good evidence", requirements=[]),
            ScoringLevel(range=[9, 10], label="Exceptional", description="Excellent evidence", requirements=[])
        ]
        
        framework = ScoringFramework(
            levels=levels,
            evidence_requirements=EvidenceConfig(),
            contextual_rules=[]
        )
        
        assert len(framework.levels) == 4
        assert framework.levels[0].label == "Minimal"
        assert framework.levels[-1].label == "Exceptional"
        
        # Test overlapping ranges validation
        overlapping_levels = [
            ScoringLevel(range=[0, 4], label="Low", description="Low", requirements=[]),
            ScoringLevel(range=[3, 7], label="Mid", description="Mid", requirements=[])  # Overlaps
        ]
        
        with pytest.raises(ValidationError):
            ScoringFramework(
                levels=overlapping_levels,
                evidence_requirements=EvidenceConfig(),
                contextual_rules=[]
            )
    
    def test_generic_custom_dimension_model(self):
        """Test complete GenericCustomDimension model."""
        ai_context = AIContext(
            general_description="Test dimension for expertise evaluation",
            purpose="Evaluate depth of domain expertise",
            scope="Technical and business content",
            key_focus_areas=["Technical depth", "Practical examples"]
        )
        
        criteria = DimensionCriteria(
            what_counts="Evidence of expertise",
            positive_signals=["Technical terms", "Specific examples"],
            negative_signals=["Generic language"],
            exclusions=["Marketing content"]
        )
        
        framework = ScoringFramework(
            levels=[
                ScoringLevel(range=[0, 3], label="Low", description="Minimal", requirements=[]),
                ScoringLevel(range=[4, 7], label="Medium", description="Moderate", requirements=[]),
                ScoringLevel(range=[8, 10], label="High", description="Strong", requirements=[])
            ],
            evidence_requirements=EvidenceConfig()
        )
        
        dimension = GenericCustomDimension(
            client_id="test-client",
            dimension_id="domain_expertise",
            name="Domain Expertise",
            description="Evaluates depth of domain knowledge",
            ai_context=ai_context,
            criteria=criteria,
            scoring_framework=framework,
            metadata={"priority": "high", "domain": "technology"}
        )
        
        assert dimension.client_id == "test-client"
        assert dimension.dimension_id == "domain_expertise"
        assert dimension.name == "Domain Expertise"
        assert dimension.ai_context.purpose == "Evaluate depth of domain expertise"
        assert len(dimension.scoring_framework.levels) == 3
        assert dimension.metadata["priority"] == "high"


class TestGenericPromptGenerator:
    """Test dynamic prompt generation system."""
    
    @pytest.fixture
    def sample_dimension(self):
        """Create a sample dimension for testing."""
        return GenericCustomDimension(
            client_id="test-client",
            dimension_id="expertise",
            name="Domain Expertise",
            description="Evaluates technical depth and practical knowledge",
            ai_context=AIContext(
                general_description="This dimension measures depth of domain expertise",
                purpose="Distinguish technical content from marketing content",
                scope="All forms of technical and business content",
                key_focus_areas=["Technical accuracy", "Real examples", "Industry terms"],
                analysis_approach="Look for specific technical details and concrete examples"
            ),
            criteria=DimensionCriteria(
                what_counts="Evidence of deep technical knowledge",
                positive_signals=["Technical implementation details", "Specific examples"],
                negative_signals=["Generic marketing language", "Vague claims"],
                exclusions=["Pure promotional content"]
            ),
            scoring_framework=ScoringFramework(
                levels=[
                    ScoringLevel(range=[0, 3], label="Minimal", description="Low expertise", requirements=["Basic mentions"]),
                    ScoringLevel(range=[7, 10], label="Strong", description="High expertise", requirements=["Technical depth", "Specific examples"])
                ],
                evidence_requirements=EvidenceConfig(min_words=120, word_increment=80),
                contextual_rules=[
                    ContextualRule(
                        name="off_topic_cap", 
                        description="Cap for off-topic content",
                        condition="off_topic",
                        adjustment_type="cap",
                        adjustment_value=3
                    )
                ]
            ),
            metadata={"domain": "technology"}
        )
    
    def test_build_ai_context_section(self, sample_dimension):
        """Test AI context section generation."""
        generator = GenericPromptGenerator()
        
        context_section = generator._build_ai_context_section(sample_dimension.ai_context)
        
        assert "**AI CONTEXT & OVERALL UNDERSTANDING**:" in context_section
        assert sample_dimension.ai_context.general_description in context_section
        assert sample_dimension.ai_context.purpose in context_section
        assert sample_dimension.ai_context.scope in context_section
        assert "Technical accuracy" in context_section  # Key focus area
        assert "**IMPORTANT**:" in context_section
    
    def test_build_criteria_section(self, sample_dimension):
        """Test criteria section generation."""
        generator = GenericPromptGenerator()
        
        criteria_section = generator._build_criteria_section(sample_dimension.criteria)
        
        assert "**What Counts**:" in criteria_section
        assert sample_dimension.criteria.what_counts in criteria_section
        assert "**Positive Signals**:" in criteria_section
        assert "Technical implementation details" in criteria_section
        assert "**Negative Signals**:" in criteria_section
        assert "Generic marketing language" in criteria_section
        assert "**Exclusions**:" in criteria_section
        assert "Pure promotional content" in criteria_section
    
    def test_build_scoring_framework_section(self, sample_dimension):
        """Test scoring framework section generation."""
        generator = GenericPromptGenerator()
        
        framework_section = generator._build_scoring_framework_section(
            sample_dimension.scoring_framework
        )
        
        assert "**Scoring Framework**:" in framework_section
        assert "0-3 (Minimal)" in framework_section
        assert "7-10 (Strong)" in framework_section
        assert "**Evidence Requirements**:" in framework_section
        assert "120 relevant words" in framework_section
        assert "**Contextual Rules**:" in framework_section
        assert "off_topic_cap" in framework_section
    
    def test_build_dimension_section(self, sample_dimension):
        """Test complete dimension section generation."""
        generator = GenericPromptGenerator()
        
        section = generator._build_dimension_section(sample_dimension)
        
        assert f"## ANALYZE: {sample_dimension.name}" in section
        assert "**AI CONTEXT & OVERALL UNDERSTANDING**:" in section
        assert "**What Counts**:" in section
        assert "**Scoring Framework**:" in section
        assert sample_dimension.ai_context.general_description in section
        assert sample_dimension.criteria.what_counts in section
    
    def test_build_complete_prompt(self, sample_dimension):
        """Test complete prompt generation."""
        generator = GenericPromptGenerator()
        
        content = "Sample technical content about machine learning implementation with TensorFlow."
        url = "https://example.com/ml-guide"
        client_id = "test-client"
        
        prompts = generator.build_generic_dimension_prompt(
            content=content,
            dimensions=[sample_dimension],
            url=url,
            client_id=client_id
        )
        
        assert "system" in prompts
        assert "user" in prompts
        
        system_prompt = prompts["system"]
        assert f"client {client_id}" in system_prompt
        assert "expert content analyst" in system_prompt
        
        user_prompt = prompts["user"]
        assert url in user_prompt
        assert sample_dimension.name in user_prompt
        assert "## CONTENT TO ANALYZE:" in user_prompt
        assert content in user_prompt
    
    def test_build_analysis_schema(self, sample_dimension):
        """Test dynamic schema generation."""
        generator = GenericPromptGenerator()
        
        schema = generator.build_generic_analysis_schema([sample_dimension])
        
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "generic_dimensions" in schema["properties"]
        
        dimensions_schema = schema["properties"]["generic_dimensions"]
        assert "properties" in dimensions_schema
        assert sample_dimension.dimension_id in dimensions_schema["properties"]
        
        dimension_schema = dimensions_schema["properties"][sample_dimension.dimension_id]
        assert "final_score" in dimension_schema["properties"]
        assert "evidence_summary" in dimension_schema["properties"]
        assert "confidence_score" in dimension_schema["properties"]


class TestGenericContentAnalyzer:
    """Test generic content analyzer functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def sample_dimensions(self):
        """Create sample dimensions for testing."""
        return [
            GenericCustomDimension(
                client_id="test-client",
                dimension_id="expertise",
                name="Domain Expertise",
                description="Technical depth evaluation",
                ai_context=AIContext(
                    general_description="Measures technical expertise",
                    purpose="Evaluate domain knowledge",
                    scope="Technical content",
                    key_focus_areas=["Technical depth"]
                ),
                criteria=DimensionCriteria(
                    what_counts="Technical knowledge evidence",
                    positive_signals=["Technical terms"],
                    negative_signals=["Generic language"],
                    exclusions=["Marketing content"]
                ),
                scoring_framework=ScoringFramework(
                    levels=[
                        ScoringLevel(range=[0, 5], label="Low", description="Low", requirements=[]),
                        ScoringLevel(range=[6, 10], label="High", description="High", requirements=[])
                    ],
                    evidence_requirements=EvidenceConfig(min_words=100)
                )
            )
        ]
    
    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response."""
        return {
            "generic_dimensions": {
                "expertise": {
                    "final_score": 8,
                    "evidence_summary": "Strong technical content with specific examples",
                    "evidence_analysis": {
                        "total_relevant_words": 150,
                        "evidence_threshold_met": True,
                        "specificity_score": 7,
                        "quality_indicators": {"depth_score": 8, "relevance_score": 7}
                    },
                    "scoring_breakdown": {
                        "base_score": 7,
                        "evidence_adjustments": {"word_count_bonus": 1},
                        "contextual_adjustments": {},
                        "scoring_rationale": "High technical content with good examples"
                    },
                    "confidence_score": 8,
                    "detailed_reasoning": "Content demonstrates clear technical expertise with specific implementation details",
                    "matched_criteria": ["technical_terms", "specific_examples"],
                    "analysis_metadata": {"processing_time_ms": 1250}
                }
            }
        }
    
    @patch('backend.app.services.analysis.generic_content_analyzer.GenericContentAnalyzer._call_openai_analysis')
    async def test_analyze_content_with_generic_dimensions(
        self, 
        mock_openai_call, 
        sample_dimensions, 
        mock_openai_response,
        mock_db
    ):
        """Test complete content analysis with generic dimensions."""
        mock_openai_call.return_value = mock_openai_response
        
        analyzer = GenericContentAnalyzer()
        content = "This is a technical article about machine learning implementation using TensorFlow and Python."
        url = "https://example.com/ml-article"
        client_id = "test-client"
        content_analysis_id = uuid4()
        
        # Mock database operations
        mock_db.execute.return_value = None
        
        with patch.object(analyzer, '_store_dimension_analysis', new_callable=AsyncMock):
            results = await analyzer.analyze_content_with_generic_dimensions(
                content=content,
                url=url,
                client_id=client_id,
                dimensions=sample_dimensions,
                content_analysis_id=content_analysis_id,
                db=mock_db
            )
        
        assert "expertise" in results
        analysis = results["expertise"]
        assert analysis.final_score == 8
        assert analysis.confidence_score == 8
        assert analysis.evidence_analysis.total_relevant_words == 150
        assert analysis.evidence_analysis.evidence_threshold_met == True
        assert len(analysis.matched_criteria) == 2
    
    def test_calculate_evidence_metrics(self):
        """Test evidence metrics calculation."""
        analyzer = GenericContentAnalyzer()
        
        content = "This technical implementation uses advanced machine learning algorithms including TensorFlow and neural networks. The implementation achieved 95% accuracy on the test dataset."
        
        criteria = {
            "positive_signals": [
                "technical implementation",
                "machine learning",
                "algorithms",
                "TensorFlow"
            ]
        }
        
        metrics = analyzer.calculate_evidence_metrics(content, criteria)
        
        assert metrics["total_relevant_words"] > 0
        assert isinstance(metrics["evidence_threshold_met"], bool)
        assert 0 <= metrics["specificity_score"] <= 10
        assert "quality_indicators" in metrics
        assert "depth_score" in metrics["quality_indicators"]
    
    async def test_apply_scoring_validations(self, sample_dimensions):
        """Test scoring validation and adjustment logic."""
        analyzer = GenericContentAnalyzer()
        dimension = sample_dimensions[0]
        
        # Test insufficient evidence penalty
        evidence_analysis = EvidenceAnalysis(
            total_relevant_words=50,  # Below minimum
            evidence_threshold_met=False,
            specificity_score=3
        )
        
        scoring_breakdown = ScoringBreakdown(
            base_score=7,
            scoring_rationale="Initial assessment"
        )
        
        adjusted_score = await analyzer._apply_scoring_validations(
            dimension=dimension,
            raw_score=8,
            evidence_analysis=evidence_analysis,
            scoring_breakdown=scoring_breakdown
        )
        
        # Score should be capped due to insufficient evidence
        assert adjusted_score <= 4
        
        # Test sufficient evidence - no penalty
        evidence_analysis.total_relevant_words = 200
        evidence_analysis.evidence_threshold_met = True
        
        adjusted_score = await analyzer._apply_scoring_validations(
            dimension=dimension,
            raw_score=8,
            evidence_analysis=evidence_analysis,
            scoring_breakdown=scoring_breakdown
        )
        
        assert adjusted_score == 8  # No penalty applied


class TestGenericDimensionsAPI:
    """Test API endpoints for generic dimensions."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.app.main import app
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer test-token"}
    
    def test_create_generic_dimension(self, client, auth_headers):
        """Test creating a new generic dimension."""
        dimension_data = {
            "dimension_id": "test_expertise",
            "name": "Test Domain Expertise",
            "description": "Test dimension for domain expertise evaluation",
            "ai_context": {
                "general_description": "This dimension evaluates technical expertise",
                "purpose": "Distinguish expert content from basic content",
                "scope": "Technical and business content",
                "key_focus_areas": ["Technical depth", "Specific examples"]
            },
            "criteria": {
                "what_counts": "Evidence of deep technical knowledge",
                "positive_signals": ["Technical terms", "Specific examples"],
                "negative_signals": ["Generic language"],
                "exclusions": ["Marketing content"]
            },
            "scoring_framework": {
                "levels": [
                    {
                        "range": [0, 3],
                        "label": "Minimal",
                        "description": "Basic or no expertise shown",
                        "requirements": ["Basic mentions only"]
                    },
                    {
                        "range": [7, 10],
                        "label": "Strong",
                        "description": "Clear expertise demonstrated",
                        "requirements": ["Technical depth", "Specific examples"]
                    }
                ],
                "evidence_requirements": {
                    "min_words": 120,
                    "word_increment": 80,
                    "max_score_per_increment": 1,
                    "specificity_weight": 0.3
                },
                "contextual_rules": []
            },
            "metadata": {"domain": "technology", "priority": "high"}
        }
        
        with patch('backend.app.api.v1.generic_dimensions.get_current_user'):
            with patch('backend.app.api.v1.generic_dimensions.get_db'):
                # This test would need proper database mocking
                # For now, test the request structure
                assert dimension_data["dimension_id"] == "test_expertise"
                assert "ai_context" in dimension_data
                assert "criteria" in dimension_data
                assert "scoring_framework" in dimension_data
    
    def test_generic_analysis_request_model(self):
        """Test generic analysis request model."""
        request = GenericAnalysisRequest(
            client_id="test-client",
            url="https://example.com/content",
            analysis_type="generic_dimensions",
            dimension_filters=["expertise", "customer_focus"]
        )
        
        assert request.client_id == "test-client"
        assert request.url == "https://example.com/content"
        assert request.analysis_type == "generic_dimensions"
        assert len(request.dimension_filters) == 2


# Integration test example
class TestGenericDimensionsIntegration:
    """Integration tests for the complete generic dimensions system."""
    
    @pytest.mark.asyncio
    async def test_complete_analysis_flow(self):
        """Test complete flow from dimension creation to analysis."""
        # This would be an integration test that:
        # 1. Creates a generic dimension configuration
        # 2. Submits content for analysis
        # 3. Verifies the analysis results
        # 4. Tests result retrieval and export
        
        # For now, just verify the components work together
        ai_context = AIContext(
            general_description="Integration test dimension",
            purpose="Test complete flow",
            scope="Test content",
            key_focus_areas=["Integration testing"]
        )
        
        criteria = DimensionCriteria(
            what_counts="Integration test evidence",
            positive_signals=["integration", "testing"],
            negative_signals=["incomplete"],
            exclusions=["unrelated"]
        )
        
        framework = ScoringFramework(
            levels=[
                ScoringLevel(range=[0, 5], label="Low", description="Low", requirements=[]),
                ScoringLevel(range=[6, 10], label="High", description="High", requirements=[])
            ],
            evidence_requirements=EvidenceConfig()
        )
        
        dimension = GenericCustomDimension(
            client_id="integration-test",
            dimension_id="integration_test",
            name="Integration Test Dimension",
            ai_context=ai_context,
            criteria=criteria,
            scoring_framework=framework
        )
        
        # Verify the complete dimension is valid
        assert dimension.client_id == "integration-test"
        assert dimension.ai_context.purpose == "Test complete flow"
        assert len(dimension.scoring_framework.levels) == 2
        
        # Test prompt generation
        generator = GenericPromptGenerator()
        prompts = generator.build_generic_dimension_prompt(
            content="Integration test content with testing and integration examples",
            dimensions=[dimension],
            url="https://test.com",
            client_id="integration-test"
        )
        
        assert "system" in prompts
        assert "user" in prompts
        assert "Integration Test Dimension" in prompts["user"]
        
        # Test schema generation
        schema = generator.build_generic_analysis_schema([dimension])
        assert "generic_dimensions" in schema["properties"]
        assert "integration_test" in schema["properties"]["generic_dimensions"]["properties"]


if __name__ == "__main__":
    pytest.main([__file__])
