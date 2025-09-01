"""
Analysis configuration service
"""
from typing import Dict, Any, Optional, List
import json

from app.core.database import db_pool
from app.models.analysis_config import AnalysisConfig


class AnalysisConfigService:
    """Service for managing analysis configuration"""
    
    def __init__(self, settings, db):
        self.settings = settings
        self.db = db
    
    async def get_config(self) -> AnalysisConfig:
        """Get current analysis configuration"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM analysis_config LIMIT 1"
            )
            
            if not row:
                # Create default config
                return await self.create_default_config()
            
            data = dict(row)
            # Parse JSON fields
            for field in ['personas', 'jtbd_phases', 'competitor_domains', 'custom_dimensions']:
                if data[field] and isinstance(data[field], str):
                    data[field] = json.loads(data[field])
            
            return AnalysisConfig(**data)
    
    async def update_config(self, updates: Dict[str, Any]) -> AnalysisConfig:
        """Update analysis configuration"""
        async with db_pool.acquire() as conn:
            # Ensure config exists
            existing = await conn.fetchval(
                "SELECT id FROM analysis_config LIMIT 1"
            )
            
            if not existing:
                await self.create_default_config()
                existing = await conn.fetchval(
                    "SELECT id FROM analysis_config LIMIT 1"
                )
            
            # Convert lists/dicts to JSON
            json_fields = ['personas', 'jtbd_phases', 'competitor_domains', 'custom_dimensions']
            for field in json_fields:
                if field in updates and not isinstance(updates[field], str):
                    updates[field] = json.dumps(updates[field])
            
            # Build update query
            set_clauses = []
            values = []
            for idx, (key, value) in enumerate(updates.items(), 1):
                set_clauses.append(f"{key} = ${idx}")
                values.append(value)
            
            query = f"""
                UPDATE analysis_config 
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = $%s
                RETURNING *
            """ % (len(values) + 1)
            
            values.append(existing)
            result = await conn.fetchrow(query, *values)
            
            data = dict(result)
            # Parse JSON fields
            for field in json_fields:
                if data[field] and isinstance(data[field], str):
                    data[field] = json.loads(data[field])
            
            return AnalysisConfig(**data)
    
    async def create_default_config(self) -> AnalysisConfig:
        """Create default analysis configuration"""
        default_personas = [
            {
                "name": "Technical Decision Maker",
                "description": "CTO/VP Engineering evaluating technical solutions",
                "title": "CTO / VP Engineering",
                "goals": ["Scalable architecture", "Developer productivity", "Technical innovation"],
                "pain_points": ["Legacy system limitations", "Integration complexity", "Technical debt"],
                "decision_criteria": ["Performance", "Scalability", "Developer experience", "Security"],
                "content_preferences": ["Technical deep-dives", "Architecture guides", "Performance benchmarks"]
            },
            {
                "name": "Business Decision Maker",
                "description": "CFO/VP Finance focused on ROI and business impact",
                "title": "CFO / VP Finance", 
                "goals": ["Cost reduction", "Revenue growth", "Operational efficiency"],
                "pain_points": ["Budget constraints", "ROI justification", "Hidden costs"],
                "decision_criteria": ["ROI", "Total cost of ownership", "Time to value", "Risk"],
                "content_preferences": ["ROI calculators", "Case studies", "Business impact analysis"]
            }
        ]
        
        default_jtbd_phases = [
            {
                "name": "Problem Identification",
                "description": "Buyers recognize a problem or opportunity that requires a solution",
                "buyer_mindset": "We need to address this challenge",
                "key_questions": ["What's the impact of this problem?", "What opportunities are we missing?"],
                "content_types": ["Industry trends", "Research reports", "Problem analysis"]
            },
            {
                "name": "Solution Exploration", 
                "description": "Buyers research potential solutions and evaluate different options",
                "buyer_mindset": "What solutions are available?",
                "key_questions": ["What approaches exist?", "What are the pros and cons?", "What's possible?"],
                "content_types": ["Solution guides", "Option comparisons", "Capability overviews"]
            },
            {
                "name": "Requirements Building",
                "description": "Buyers define the specific requirements and specifications for the desired solution",
                "buyer_mindset": "What exactly do we need?",
                "key_questions": ["What are our must-haves?", "What constraints exist?", "What's our criteria?"],
                "content_types": ["Requirements guides", "Specification templates", "Evaluation criteria"]
            },
            {
                "name": "Supplier Selection",
                "description": "Buyers evaluate potential suppliers and make a decision on which one to partner with",
                "buyer_mindset": "Which vendor is the best fit?",
                "key_questions": ["Who can deliver?", "Who do we trust?", "Who offers best value?"],
                "content_types": ["Vendor comparisons", "Customer reviews", "Analyst reports"]
            },
            {
                "name": "Validation",
                "description": "Buyers assess the chosen supplier's capabilities and ensure they can meet the defined requirements",
                "buyer_mindset": "Can they really deliver?",
                "key_questions": ["Does it work as promised?", "What's the real ROI?", "What are the risks?"],
                "content_types": ["Proof of concepts", "Case studies", "Reference checks"]
            },
            {
                "name": "Consensus Creation",
                "description": "Buyers build internal agreement and support for the purchase decision",
                "buyer_mindset": "How do we get everyone aligned?",
                "key_questions": ["How to get buy-in?", "Who needs convincing?", "What are the objections?"],
                "content_types": ["Business cases", "Executive summaries", "Change management plans"]
            }
        ]
        
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO analysis_config 
                (personas, jtbd_phases, competitor_domains, custom_dimensions)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                json.dumps(default_personas),
                json.dumps(default_jtbd_phases),
                json.dumps([]),
                json.dumps({})
            )
            
            data = dict(result)
            # Parse JSON fields
            for field in ['personas', 'jtbd_phases', 'competitor_domains', 'custom_dimensions']:
                if data[field] and isinstance(data[field], str):
                    data[field] = json.loads(data[field])
            
            return AnalysisConfig(**data)
