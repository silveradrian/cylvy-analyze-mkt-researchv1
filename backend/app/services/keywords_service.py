"""
Keywords management service
"""
import csv
import io
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import UploadFile
from loguru import logger

from app.core.database import db_pool
from app.models.keyword import Keyword, KeywordCreate, KeywordUpdate


class KeywordsService:
    """Service for managing keywords"""
    
    def __init__(self, settings, db):
        self.settings = settings
        self.db = db
    
    async def get_keywords(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Keyword]:
        """Get keywords with filtering and pagination"""
        async with db_pool.acquire() as conn:
            query = "SELECT * FROM keywords WHERE 1=1"
            params = []
            
            if category:
                params.append(category)
                query += f" AND category = ${len(params)}"
            
            if search:
                params.append(f"%{search}%")
                query += f" AND keyword ILIKE ${len(params)}"
            
            query += f" ORDER BY keyword LIMIT {limit} OFFSET {offset}"
            
            rows = await conn.fetch(query, *params)
            return [Keyword(**dict(row)) for row in rows]
    
    async def create_keyword(self, keyword_data: KeywordCreate) -> Keyword:
        """Create a new keyword"""
        keyword_id = uuid4()
        
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO keywords (
                    id, keyword, category, jtbd_stage, is_brand,
                    client_score, persona_score, seo_score, composite_score
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
                """,
                keyword_id,
                keyword_data.keyword,
                keyword_data.category,
                keyword_data.jtbd_stage,
                keyword_data.is_brand,
                keyword_data.client_score,
                keyword_data.persona_score,
                keyword_data.seo_score,
                keyword_data.composite_score
            )
            
            return Keyword(**dict(row))
    
    async def update_keyword(self, keyword_id: UUID, updates: KeywordUpdate) -> Keyword:
        """Update an existing keyword"""
        # Build update query
        set_clauses = []
        values = []
        
        for field, value in updates.dict(exclude_unset=True).items():
            if value is not None:
                set_clauses.append(f"{field} = ${len(values) + 1}")
                values.append(value)
        
        if not set_clauses:
            raise ValueError("No updates provided")
        
        values.append(keyword_id)
        query = f"""
            UPDATE keywords 
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = ${len(values)}
            RETURNING *
        """
        
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
            
            if not row:
                raise ValueError(f"Keyword {keyword_id} not found")
            
            return Keyword(**dict(row))
    
    async def delete_keyword(self, keyword_id: UUID) -> bool:
        """Delete a keyword"""
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM keywords WHERE id = $1",
                keyword_id
            )
            
            return result == "DELETE 1"
    
    async def upload_keywords_from_csv(
        self, 
        file: UploadFile, 
        regions: List[str]
    ) -> Dict[str, Any]:
        """Upload keywords from CSV file"""
        contents = await file.read()
        csv_data = contents.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        keywords_data = []
        
        for row in csv_reader:
            # Look for keyword column (case insensitive)
            keyword = None
            for key, value in row.items():
                if 'keyword' in key.lower():
                    keyword = value.strip()
                    break
            
            if not keyword:
                continue
            
            keyword_data = {
                'keyword': keyword,
                'category': row.get('category', '').strip() or None,
                'jtbd_stage': row.get('jtbd_stage', '').strip() or None,
                'client_score': self._parse_float(row.get('client_score')),
                'persona_score': self._parse_float(row.get('persona_score')),
                'seo_score': self._parse_float(row.get('seo_score')),
                'composite_score': self._parse_float(row.get('composite_score')),
                'is_brand': keyword.lower().find('cylvy') != -1 or keyword.lower().find('company') != -1
            }
            
            keywords_data.append(keyword_data)
        
        # Insert keywords
        keywords_processed = 0
        errors = []
        
        async with db_pool.acquire() as conn:
            for kw_data in keywords_data:
                try:
                    await conn.execute(
                        """
                        INSERT INTO keywords (
                            id, keyword, category, jtbd_stage, is_brand,
                            client_score, persona_score, seo_score, composite_score
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (keyword) DO UPDATE SET
                            category = EXCLUDED.category,
                            jtbd_stage = EXCLUDED.jtbd_stage,
                            client_score = EXCLUDED.client_score,
                            persona_score = EXCLUDED.persona_score,
                            seo_score = EXCLUDED.seo_score,
                            composite_score = EXCLUDED.composite_score,
                            updated_at = NOW()
                        """,
                        uuid4(),
                        kw_data['keyword'],
                        kw_data['category'],
                        kw_data['jtbd_stage'],
                        kw_data['is_brand'],
                        kw_data['client_score'],
                        kw_data['persona_score'],
                        kw_data['seo_score'],
                        kw_data['composite_score']
                    )
                    keywords_processed += 1
                except Exception as e:
                    errors.append(f"Failed to insert '{kw_data['keyword']}': {str(e)}")
        
        return {
            'total_keywords': len(keywords_data),
            'keywords_processed': keywords_processed,
            'metrics_fetched': 0,  # Would be implemented with Google Ads API
            'errors': errors
        }
    
    async def get_categories(self) -> List[str]:
        """Get all unique categories"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT category FROM keywords 
                WHERE category IS NOT NULL 
                ORDER BY category
                """
            )
            return [row['category'] for row in rows]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get keyword statistics"""
        async with db_pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_keywords,
                    COUNT(CASE WHEN is_brand = true THEN 1 END) as brand_keywords,
                    COUNT(CASE WHEN category IS NOT NULL THEN 1 END) as categorized_keywords,
                    COUNT(DISTINCT category) as total_categories,
                    AVG(client_score) as avg_client_score,
                    AVG(persona_score) as avg_persona_score,
                    AVG(seo_score) as avg_seo_score
                FROM keywords
                """
            )
            
            return dict(stats) if stats else {}
    
    def _parse_float(self, value: Any) -> Optional[float]:
        """Parse float value safely"""
        if not value:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
