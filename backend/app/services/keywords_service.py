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
        """Upload keywords from CSV file with enhanced format support"""
        contents = await file.read()
        csv_data = contents.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        keywords_data = []
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header row
            try:
                # Look for keyword column (case insensitive)
                keyword = self._extract_field(row, ['keyword', 'term'])
                
                if not keyword:
                    errors.append(f"Row {row_num}: Missing keyword")
                    continue
                
                # Extract basic fields that exist in current database schema
                keyword_data = {
                    'keyword': keyword,
                    'category': self._extract_field(row, ['primary category', 'category', 'main category']),
                    'jtbd_stage': self._extract_field(row, ['jtbd stage', 'jtbd', 'stage', 'funnel stage']),
                    'avg_monthly_searches': self._parse_int(self._extract_field(row, [
                        'avg monthly searches (us)', 'monthly searches', 'search volume', 'volume'
                    ])),
                    'client_score': self._parse_float(self._extract_field(row, ['client score', 'business score'])),
                    'persona_score': self._parse_float(self._extract_field(row, ['persona score', 'audience score'])),
                    'seo_score': self._parse_float(self._extract_field(row, ['seo score', 'search score'])),
                    'is_brand': self._parse_boolean(self._extract_field(row, ['is branded', 'branded', 'brand keyword']))
                    # Note: Enhanced fields (rationales, all_categories) will be added when database is migrated
                }
                
                # Calculate composite score if not provided
                if not keyword_data.get('composite_score') and all([
                    keyword_data.get('client_score'), 
                    keyword_data.get('persona_score'), 
                    keyword_data.get('seo_score')
                ]):
                    keyword_data['composite_score'] = (
                        keyword_data['client_score'] + 
                        keyword_data['persona_score'] + 
                        keyword_data['seo_score']
                    ) / 3
                
                # Ensure all required fields have defaults
                keyword_data.setdefault('composite_score', None)
                keyword_data.setdefault('client_score', None)
                keyword_data.setdefault('persona_score', None)
                keyword_data.setdefault('seo_score', None)
                keyword_data.setdefault('avg_monthly_searches', None)
                keyword_data.setdefault('is_brand', False)
                
                keywords_data.append(keyword_data)
                
            except Exception as e:
                errors.append(f"Row {row_num}: Error parsing data - {str(e)}")
                continue
        
        # Insert keywords with enhanced schema
        keywords_processed = 0
        insert_errors = []
        
        try:
            async with db_pool.acquire() as conn:
                # First, check what columns actually exist in the keywords table
                columns_result = await conn.fetch("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'keywords' 
                    ORDER BY ordinal_position
                """)
                available_columns = [row['column_name'] for row in columns_result]
                logger.info(f"Available keywords table columns: {available_columns}")
                
                # Build dynamic insert query based on available columns
                base_columns = ['id', 'keyword']
                optional_columns = {
                    'category': 'category',
                    'jtbd_stage': 'jtbd_stage', 
                    'is_brand': 'is_brand',
                    'client_score': 'client_score',
                    'persona_score': 'persona_score',
                    'seo_score': 'seo_score',
                    'composite_score': 'composite_score',
                    'avg_monthly_searches': 'avg_monthly_searches'
                }
                
                # Only include columns that exist in the database
                insert_columns = base_columns.copy()
                insert_values = ['$1', '$2']  # id, keyword
                update_clauses = []
                
                param_index = 3
                for col_name, col_key in optional_columns.items():
                    if col_name in available_columns:
                        insert_columns.append(col_name)
                        insert_values.append(f'${param_index}')
                        if col_name != 'id':  # Don't update id on conflict
                            update_clauses.append(f"{col_name} = EXCLUDED.{col_name}")
                        param_index += 1
                
                # Add updated_at if it exists
                if 'updated_at' in available_columns:
                    update_clauses.append("updated_at = NOW()")
                
                insert_query = f"""
                    INSERT INTO keywords ({', '.join(insert_columns)})
                    VALUES ({', '.join(insert_values)})
                    ON CONFLICT (keyword) DO UPDATE SET
                        {', '.join(update_clauses) if update_clauses else 'keyword = EXCLUDED.keyword'}
                """
                
                logger.info(f"Using dynamic insert query with {len(insert_columns)} columns")
                
                for kw_data in keywords_data:
                    try:
                        # Build parameter list based on available columns
                        params = [uuid4(), kw_data['keyword']]
                        
                        for col_name, col_key in optional_columns.items():
                            if col_name in available_columns:
                                params.append(kw_data.get(col_key))
                        
                        await conn.execute(insert_query, *params)
                        keywords_processed += 1
                        
                    except Exception as e:
                        insert_errors.append(f"Failed to insert '{kw_data['keyword']}': {str(e)}")
                        logger.error(f"Keyword insert error: {e}")
                        
        except Exception as db_error:
            # Database connection failed
            insert_errors.append(f"Database connection failed: {str(db_error)}")
            logger.error(f"Database error in keyword upload: {db_error}")
            
            # For testing purposes, still return parsed data
            keywords_processed = 0
        
        # Combine parsing and insert errors
        all_errors = errors + insert_errors
        
        return {
            'total_keywords': len(keywords_data),
            'keywords_processed': keywords_processed,
            'metrics_fetched': 0,  # Google Ads metrics not implemented yet
            'csv_parsing_errors': len(errors),
            'database_errors': len(insert_errors),
            'errors': all_errors
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
    
    def _parse_int(self, value) -> Optional[int]:
        """Parse integer value safely"""
        if not value or str(value).strip() == '':
            return None
        try:
            return int(float(value))  # Handle decimal strings
        except (ValueError, TypeError):
            return None
    
    def _parse_boolean(self, value) -> bool:
        """Parse boolean value safely"""
        if not value:
            return False
        
        value_str = str(value).strip().lower()
        return value_str in ['true', 'yes', '1', 'branded', 'brand']
    
    def _extract_field(self, row: dict, possible_names: List[str]) -> Optional[str]:
        """Extract field value from CSV row using multiple possible column names"""
        for name in possible_names:
            # Try exact match first
            if name in row and row[name]:
                return str(row[name]).strip()
            
            # Try case-insensitive match
            for key, value in row.items():
                if key.lower() == name.lower() and value:
                    return str(value).strip()
        
        return None
