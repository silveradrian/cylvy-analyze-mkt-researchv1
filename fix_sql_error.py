import asyncio
from app.core.database import db_pool
import uuid

async def fix():
    pipeline_id = uuid.UUID("1a1bac89-8056-41ff-8f20-8e82ec67999f")
    
    async with db_pool.acquire() as conn:
        # Check for problematic content with "_blank" in scraped_content
        problematic = await conn.fetch("""
            SELECT id, url, 
                   CASE 
                     WHEN content::text LIKE '%_blank%' THEN 'content'
                     WHEN meta_description::text LIKE '%_blank%' THEN 'meta_description'
                     WHEN meta_keywords::text LIKE '%_blank%' THEN 'meta_keywords'
                     ELSE 'unknown'
                   END as field_with_issue
            FROM scraped_content
            WHERE pipeline_execution_id = $1
            AND (content::text LIKE '%_blank%' 
                 OR meta_description::text LIKE '%_blank%'
                 OR meta_keywords::text LIKE '%_blank%')
            LIMIT 10
        """, pipeline_id)
        
        print(f"Found {len(problematic)} entries with potential '_blank' issues")
        for row in problematic:
            print(f"  ID: {row['id']}, URL: {row['url'][:50]}..., Field: {row['field_with_issue']}")
        
        # Clean the problematic content by escaping quotes
        if problematic:
            for row in problematic:
                await conn.execute("""
                    UPDATE scraped_content
                    SET content = REPLACE(content::text, '"_blank"', '\"_blank\"')::jsonb,
                        meta_description = REPLACE(meta_description, '"_blank"', '\"_blank\"'),
                        meta_keywords = REPLACE(meta_keywords, '"_blank"', '\"_blank\"')
                    WHERE id = $1
                """, row['id'])
            
            print(f"✅ Fixed {len(problematic)} entries with '_blank' issues")
        
        # Reset stuck content analysis entries
        await conn.execute("""
            UPDATE scraped_content
            SET content_analyzed = false,
                analysis_error = NULL
            WHERE pipeline_execution_id = $1
            AND content_analyzed = false
            AND created_at < NOW() - INTERVAL '30 minutes'
        """, pipeline_id)
        
        print("✅ Reset stuck content analysis entries")

asyncio.run(fix())
