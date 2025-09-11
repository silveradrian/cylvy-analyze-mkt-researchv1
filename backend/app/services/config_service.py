"""
Client configuration service - manages single-instance configuration
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json

from app.core.database import db_pool
from app.models.config import ClientConfig, AnalysisConfig


class ConfigService:
    """Service for managing client configuration"""
    
    async def get_config(self) -> Optional[ClientConfig]:
        """Get client configuration (single record)"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM client_config LIMIT 1"
            )
            
            if not row:
                return None
            
            data = dict(row)
            # Parse JSONB fields if they're strings
            if isinstance(data.get('competitors'), str):
                import json
                data['competitors'] = json.loads(data['competitors'])
            
            return ClientConfig(**data)
    
    async def update_config(self, updates: Dict[str, Any]) -> ClientConfig:
        """Update client configuration"""
        async with db_pool.acquire() as conn:
            # Check if config exists
            existing = await conn.fetchval(
                "SELECT id FROM client_config LIMIT 1"
            )
            
            if not existing:
                # Create initial config
                # Ensure all fields are included
                insert_fields = ['company_name', 'company_domain', 'primary_color', 'secondary_color', 
                                'description', 'legal_name', 'additional_domains', 'competitors']
                placeholders = ', '.join([f'${i+1}' for i in range(len(insert_fields))])
                
                result = await conn.fetchrow(
                    f"""
                    INSERT INTO client_config 
                    ({', '.join(insert_fields)})
                    VALUES ({placeholders})
                    RETURNING *
                    """,
                    updates.get('company_name', 'My Company'),
                    updates.get('company_domain', 'example.com'),
                    updates.get('primary_color', '#3B82F6'),
                    updates.get('secondary_color', '#10B981'),
                    updates.get('description', ''),
                    updates.get('legal_name', updates.get('company_name', 'My Company')),
                    updates.get('additional_domains', []),
                    updates.get('competitors', [])
                )
            else:
                # Build update query
                set_clauses = []
                values = []
                for idx, (key, value) in enumerate(updates.items(), 1):
                    # Handle special types
                    if key == 'competitors' and isinstance(value, list):
                        # Convert list to JSONB
                        set_clauses.append(f"{key} = ${idx}::jsonb")
                        values.append(json.dumps(value))
                    elif key == 'additional_domains' and isinstance(value, list):
                        # PostgreSQL array type
                        set_clauses.append(f"{key} = ${idx}::text[]")
                        values.append(value)
                    else:
                        set_clauses.append(f"{key} = ${idx}")
                        values.append(value)
                
                query = f"""
                    UPDATE client_config 
                    SET {', '.join(set_clauses)}, updated_at = NOW()
                    WHERE id = ${len(values) + 1}
                    RETURNING *
                """
                
                values.append(existing)
                result = await conn.fetchrow(query, *values)
            
            return ClientConfig(**dict(result))
    
    async def get_analysis_config(self) -> AnalysisConfig:
        """Get analysis configuration"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM analysis_config LIMIT 1"
            )
            
            if not row:
                # Create default config
                result = await conn.fetchrow(
                    """
                    INSERT INTO analysis_config 
                    (personas, jtbd_phases, competitor_domains, custom_dimensions)
                    VALUES ($1, $2, $3, $4)
                    RETURNING *
                    """,
                    json.dumps([]),
                    json.dumps([]),
                    json.dumps([]),
                    json.dumps({})
                )
                return AnalysisConfig(**dict(result))
            
            return AnalysisConfig(**dict(row))
    
    async def update_analysis_config(self, updates: Dict[str, Any]) -> AnalysisConfig:
        """Update analysis configuration"""
        async with db_pool.acquire() as conn:
            # Ensure config exists
            existing = await conn.fetchval(
                "SELECT id FROM analysis_config LIMIT 1"
            )
            
            if not existing:
                await self.get_analysis_config()  # Creates default
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
            
            return AnalysisConfig(**dict(result))
    
    async def get_api_keys_status(self) -> Dict[str, bool]:
        """Check which API keys are configured"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT service_name, is_active 
                FROM api_keys 
                WHERE is_active = true
                """
            )
            
            return {
                row['service_name']: True 
                for row in rows
            }
    
    async def set_api_key(self, service_name: str, api_key: str, encrypted: bool = False):
        """Set an API key (should be encrypted in production)"""
        if not encrypted:
            # TODO: Implement encryption
            api_key_encrypted = api_key  # Placeholder
        else:
            api_key_encrypted = api_key
        
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO api_keys (service_name, api_key_encrypted)
                VALUES ($1, $2)
                ON CONFLICT (service_name) 
                DO UPDATE SET 
                    api_key_encrypted = EXCLUDED.api_key_encrypted,
                    updated_at = NOW()
                """,
                service_name,
                api_key_encrypted
            )
    
    async def get_api_key(self, service_name: str) -> Optional[str]:
        """Get decrypted API key"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT api_key_encrypted 
                FROM api_keys 
                WHERE service_name = $1 AND is_active = true
                """,
                service_name
            )
            
            if not row:
                return None
            
            # TODO: Implement decryption
            return row['api_key_encrypted']  # Placeholder
    
    async def initialize_default_config(self):
        """Initialize configuration for first-time setup"""
        # Check if already initialized
        config = await self.get_config()
        if config:
            return
        
        # Create default client config
        await self.update_config({
            'company_name': 'My Company',
            'company_domain': 'example.com'
        })
        
        # Create default analysis config
        await self.update_analysis_config({
            'personas': [],
            'jtbd_phases': [
                {"name": "Problem Identification", "description": "Identifying the problem or opportunity"},
                {"name": "Solution Exploration", "description": "Exploring potential solutions"},
                {"name": "Requirements Building", "description": "Building specific requirements"},
                {"name": "Supplier Selection", "description": "Selecting the right supplier"},
                {"name": "Validation", "description": "Validating the solution"},
                {"name": "Consensus Creation", "description": "Creating organizational consensus"}
            ],
            'competitor_domains': [],
            'custom_dimensions': {}
        })

