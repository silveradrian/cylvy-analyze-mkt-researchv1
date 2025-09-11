"""
Migration script to convert all existing dimensions to the advanced framework structure
"""
import asyncio
import json
from typing import Dict, List, Any
from datetime import datetime
import asyncpg
from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool


class AdvancedFrameworkMigrator:
    """Migrates personas, JTBD phases, and custom dimensions to advanced framework"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_url = settings.get_database_url()
    
    async def migrate_all(self):
        """Run complete migration to advanced framework"""
        logger.info("🚀 Starting migration to advanced framework...")
        
        # Create connection pool
        pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=5)
        
        try:
            async with pool.acquire() as conn:
                # Create tables if they don't exist
                await self._ensure_tables_exist(conn)
                
                # Get all projects
                projects = await conn.fetch("SELECT id, company_name FROM projects")
                
                for project in projects:
                    logger.info(f"📊 Migrating project: {project['company_name']} ({project['id']})")
                    
                    # Migrate personas
                    await self._migrate_personas(conn, project['id'])
                    
                    # Migrate JTBD phases (same for all projects)
                    await self._migrate_jtbd_phases(conn, project['id'])
                    
                    # Migrate existing custom dimensions
                    await self._migrate_custom_dimensions(conn, project['id'])
                
                logger.info("✅ Migration completed successfully!")
                
        finally:
            await pool.close()
    
    async def _ensure_tables_exist(self, conn):
        """Ensure advanced framework tables exist"""
        # Check if tables exist
        tables_exist = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'generic_custom_dimensions'
            )
        """)
        
        if not tables_exist:
            logger.info("📋 Creating advanced framework tables...")
            # Read and execute migration SQL
            with open('migrations/create_advanced_unified_analysis_tables.sql', 'r') as f:
                sql = f.read()
                await conn.execute(sql)
    
    async def _migrate_personas(self, conn, project_id: str):
        """Convert personas to advanced dimension format"""
        personas = await conn.fetch("""
            SELECT * FROM personas 
            WHERE project_id = $1 OR project_id IS NULL
        """, project_id)
        
        logger.info(f"  👥 Found {len(personas)} personas to migrate")
        
        for persona in personas:
            dimension_id = f"persona_{persona['name'].lower().replace(' ', '_')}"
            
            # Build advanced dimension structure
            dimension_config = {
                "dimension_id": dimension_id,
                "name": f"Persona Alignment: {persona['name']}",
                "description": f"Alignment with {persona['name']} ({persona.get('title', 'Unknown Role')})",
                "ai_context": {
                    "general_description": f"This dimension measures how well content aligns with the needs, goals, and decision-making criteria of the {persona['name']} persona",
                    "purpose": f"Evaluate content relevance and value for {persona.get('title', 'professionals')} in {persona.get('department', 'various')} departments",
                    "scope": "All content types that could influence or inform this persona's decision-making process",
                    "key_focus_areas": [
                        f"Addressing goals: {', '.join(persona.get('goals', [])[:3])}",
                        f"Solving pain points: {', '.join(persona.get('challenges', [])[:3])}",
                        f"Supporting decision criteria: {', '.join(persona.get('decision_criteria', [])[:3])}",
                        f"Role in buying journey: {persona.get('buying_journey_involvement', 'Not specified')}",
                        f"Influence level: {persona.get('influence_level', 'Not specified')}"
                    ],
                    "analysis_approach": "Evaluate how directly and effectively the content speaks to this persona's specific needs and concerns"
                },
                "criteria": {
                    "what_counts": f"Content that directly addresses {persona['name']}'s goals, challenges, and decision criteria",
                    "positive_signals": self._build_persona_positive_signals(persona),
                    "negative_signals": [
                        "Content for different departments or roles",
                        "Technical level mismatch for this persona",
                        "Irrelevant examples or use cases",
                        "Wrong stage of buying journey"
                    ],
                    "exclusions": [
                        "Generic marketing content without persona focus",
                        "Content explicitly for other personas"
                    ],
                    "additional_context": f"Consider {persona['name']}'s influence level and role in buying journey"
                },
                "scoring_framework": {
                    "levels": [
                        {
                            "range": [0, 2],
                            "label": "Poor Fit",
                            "description": "Content not relevant to this persona",
                            "requirements": ["No alignment with goals", "Wrong audience"]
                        },
                        {
                            "range": [3, 4],
                            "label": "Weak Alignment",
                            "description": "Some relevance but not targeted",
                            "requirements": ["Tangential relevance", "Generic content"]
                        },
                        {
                            "range": [5, 6],
                            "label": "Moderate Alignment",
                            "description": "Addresses some persona needs",
                            "requirements": ["Addresses 1-2 goals or pain points", "Appropriate level"]
                        },
                        {
                            "range": [7, 8],
                            "label": "Strong Alignment",
                            "description": "Well-targeted to persona",
                            "requirements": ["Addresses multiple goals", "Solves key pain points", "Right language"]
                        },
                        {
                            "range": [9, 10],
                            "label": "Perfect Fit",
                            "description": "Exceptionally well-suited",
                            "requirements": ["Comprehensive goal alignment", "All decision criteria met", "Compelling examples"]
                        }
                    ],
                    "evidence_requirements": {
                        "min_words": 80,
                        "word_increment": 60,
                        "max_score_per_increment": 1,
                        "specificity_weight": 0.4
                    },
                    "contextual_rules": [
                        {
                            "name": "wrong_persona_penalty",
                            "description": "Reduce score if content targets different persona",
                            "condition": "wrong_persona",
                            "adjustment_type": "cap",
                            "adjustment_value": 3
                        }
                    ]
                },
                "metadata": {
                    "persona_type": "buyer_persona",
                    "original_persona_id": str(persona['id']),
                    "department": persona.get('department', ''),
                    "seniority": persona.get('title', ''),
                    "influence_level": persona.get('influence_level', 'Unknown')
                }
            }
            
            # Insert into generic dimensions table
            await self._insert_dimension(conn, project_id, dimension_config)
    
    def _build_persona_positive_signals(self, persona: Dict) -> List[str]:
        """Build positive signals based on persona data"""
        signals = []
        
        # Add department-specific signals
        if persona.get('department'):
            signals.append(f"Direct mention of {persona['department']} challenges")
        
        # Add goal-based signals
        if persona.get('goals'):
            for goal in persona['goals'][:2]:
                signals.append(f"Solutions for: {goal}")
        
        # Add pain point signals
        if persona.get('challenges'):
            for challenge in persona['challenges'][:2]:
                signals.append(f"Addresses pain point: {challenge}")
        
        # Add decision criteria signals
        if persona.get('decision_criteria'):
            for criteria in persona['decision_criteria'][:2]:
                signals.append(f"Supports criteria: {criteria}")
        
        # Add standard signals
        signals.extend([
            "Language appropriate for this seniority level",
            "Examples relevant to this department",
            "Clear value proposition for this role"
        ])
        
        return signals
    
    async def _migrate_jtbd_phases(self, conn, project_id: str):
        """Convert JTBD phases to advanced dimension format"""
        logger.info("  🎯 Migrating JTBD phases...")
        
        jtbd_phases = [
            {
                "phase": 1,
                "name": "Problem Identification",
                "description": "Recognition of business problem or opportunity",
                "questions": ["What's wrong with our current approach?", "What risks are we facing?"],
                "indicators": ["challenges", "problems", "risks", "inefficiencies", "gaps"]
            },
            {
                "phase": 2,
                "name": "Solution Exploration",
                "description": "Research and discovery of potential solutions",
                "questions": ["What types of solutions exist?", "What are the options?"],
                "indicators": ["solutions", "approaches", "methods", "strategies", "alternatives"]
            },
            {
                "phase": 3,
                "name": "Requirements Building",
                "description": "Definition of specific needs and criteria",
                "questions": ["What do we need specifically?", "What's our criteria?"],
                "indicators": ["requirements", "criteria", "specifications", "features", "capabilities"]
            },
            {
                "phase": 4,
                "name": "Vendor Selection",
                "description": "Evaluation and comparison of vendors",
                "questions": ["Who are the vendors?", "How do they compare?"],
                "indicators": ["comparison", "vendor", "provider", "differentiation", "competitive"]
            },
            {
                "phase": 5,
                "name": "Validation & Consensus",
                "description": "Building internal agreement and validation",
                "questions": ["Will this work for us?", "Can we trust this vendor?"],
                "indicators": ["case study", "testimonial", "reference", "proof", "validation"]
            },
            {
                "phase": 6,
                "name": "Negotiation & Purchase",
                "description": "Final negotiations and purchase decision",
                "questions": ["What's the pricing?", "How do we get started?"],
                "indicators": ["pricing", "contract", "terms", "implementation", "onboarding"]
            }
        ]
        
        for phase in jtbd_phases:
            dimension_id = f"jtbd_phase_{phase['phase']}"
            
            dimension_config = {
                "dimension_id": dimension_id,
                "name": f"JTBD Phase {phase['phase']}: {phase['name']}",
                "description": phase['description'],
                "ai_context": {
                    "general_description": f"This dimension evaluates how well content aligns with the '{phase['name']}' phase of the B2B buying journey",
                    "purpose": f"Determine if content effectively serves buyers in the {phase['name']} phase",
                    "scope": "All content types that could influence buyers during this phase",
                    "key_focus_areas": [
                        f"Answering buyer questions: {', '.join(phase['questions'])}",
                        "Using appropriate language and indicators for this phase",
                        "Providing value specific to this stage of the journey",
                        "Guiding buyers to the next phase"
                    ],
                    "analysis_approach": "Look for content that directly addresses the concerns and questions buyers have in this specific phase"
                },
                "criteria": {
                    "what_counts": f"Content that addresses {phase['name']} phase concerns",
                    "positive_signals": phase['indicators'] + [f"Answers: {q}" for q in phase['questions']],
                    "negative_signals": [
                        "Content for different buying phases",
                        "Premature selling" if phase['phase'] < 4 else "",
                        "Too technical for early phases" if phase['phase'] < 3 else ""
                    ],
                    "exclusions": ["Generic content without phase focus"],
                    "additional_context": f"Phase {phase['phase']} of 6 in Gartner B2B journey"
                },
                "scoring_framework": {
                    "levels": [
                        {"range": [0, 2], "label": "Wrong Phase", "description": "Content for different phase", "requirements": ["No phase alignment"]},
                        {"range": [3, 4], "label": "Weak Match", "description": "Some phase relevance", "requirements": ["Minimal indicators"]},
                        {"range": [5, 6], "label": "Moderate Match", "description": "Addresses phase needs", "requirements": ["Some questions answered"]},
                        {"range": [7, 8], "label": "Strong Match", "description": "Well-aligned to phase", "requirements": ["Multiple questions answered"]},
                        {"range": [9, 10], "label": "Perfect Match", "description": "Ideal for this phase", "requirements": ["All questions addressed"]}
                    ],
                    "evidence_requirements": {
                        "min_words": 100,
                        "word_increment": 75,
                        "max_score_per_increment": 1,
                        "specificity_weight": 0.35
                    },
                    "contextual_rules": [
                        {
                            "name": "wrong_phase_cap",
                            "description": "Cap score if content is for wrong phase",
                            "condition": "wrong_phase",
                            "adjustment_type": "cap",
                            "adjustment_value": 2
                        }
                    ]
                },
                "metadata": {
                    "dimension_type": "jtbd_phase",
                    "phase_number": phase['phase'],
                    "phase_name": phase['name'],
                    "gartner_framework": True
                }
            }
            
            await self._insert_dimension(conn, project_id, dimension_config)
    
    async def _migrate_custom_dimensions(self, conn, project_id: str):
        """Migrate existing custom dimensions to advanced format"""
        # Check if there are any legacy dimensions
        legacy_dims = await conn.fetch("""
            SELECT * FROM custom_dimensions 
            WHERE project_id = $1
        """, project_id)
        
        if legacy_dims:
            logger.info(f"  🔧 Found {len(legacy_dims)} custom dimensions to migrate")
            
            for dim in legacy_dims:
                # Convert to advanced format
                dimension_config = {
                    "dimension_id": f"custom_{dim['name'].lower().replace(' ', '_')}",
                    "name": dim['name'],
                    "description": dim.get('description', f"Custom dimension: {dim['name']}"),
                    "ai_context": {
                        "general_description": dim.get('description', f"Evaluate content for {dim['name']}"),
                        "purpose": f"Assess {dim['name']} in content",
                        "scope": "All relevant content types",
                        "key_focus_areas": dim.get('evidence_types', []),
                        "analysis_approach": "Standard evaluation methodology"
                    },
                    "criteria": {
                        "what_counts": f"Evidence of {dim['name']}",
                        "positive_signals": dim.get('positive_indicators', []),
                        "negative_signals": dim.get('negative_indicators', []),
                        "exclusions": [],
                        "additional_context": ""
                    },
                    "scoring_framework": {
                        "levels": self._convert_legacy_scoring_levels(dim.get('scoring_levels', [])),
                        "evidence_requirements": {
                            "min_words": 80,
                            "word_increment": 60,
                            "max_score_per_increment": 1,
                            "specificity_weight": 0.3
                        },
                        "contextual_rules": []
                    },
                    "metadata": {
                        "dimension_type": "custom",
                        "migrated_from_legacy": True,
                        "original_id": str(dim['id'])
                    }
                }
                
                await self._insert_dimension(conn, project_id, dimension_config)
    
    def _convert_legacy_scoring_levels(self, legacy_levels: List) -> List[Dict]:
        """Convert legacy scoring format"""
        if not legacy_levels:
            return [
                {"range": [0, 3], "label": "Low", "description": "Minimal evidence", "requirements": []},
                {"range": [4, 7], "label": "Medium", "description": "Moderate evidence", "requirements": []},
                {"range": [8, 10], "label": "High", "description": "Strong evidence", "requirements": []}
            ]
        
        return legacy_levels  # Assuming they're already in correct format
    
    async def _insert_dimension(self, conn, project_id: str, config: Dict):
        """Insert dimension into generic_custom_dimensions table"""
        try:
            await conn.execute("""
                INSERT INTO generic_custom_dimensions (
                    project_id, dimension_id, name, description,
                    ai_context, criteria, scoring_framework, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (project_id, dimension_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    ai_context = EXCLUDED.ai_context,
                    criteria = EXCLUDED.criteria,
                    scoring_framework = EXCLUDED.scoring_framework,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """,
                project_id,
                config['dimension_id'],
                config['name'],
                config['description'],
                json.dumps(config['ai_context']),
                json.dumps(config['criteria']),
                json.dumps(config['scoring_framework']),
                json.dumps(config['metadata'])
            )
            logger.info(f"    ✅ Migrated: {config['name']}")
        except Exception as e:
            logger.error(f"    ❌ Failed to migrate {config['name']}: {e}")


async def main():
    """Run the migration"""
    settings = Settings()
    migrator = AdvancedFrameworkMigrator(settings)
    await migrator.migrate_all()


if __name__ == "__main__":
    asyncio.run(main())

