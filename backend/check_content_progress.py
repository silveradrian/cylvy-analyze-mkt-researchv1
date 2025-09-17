import asyncio
from app.core.database import db_pool
import uuid

async def check():
    pipeline_id = uuid.UUID("1a1bac89-8056-41ff-8f20-8e82ec67999f")
    
    async with db_pool.acquire() as conn:
        # Check scraped content for this pipeline
        scraped_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_scraped,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                COUNT(CASE WHEN content_analyzed = true THEN 1 END) as analyzed
            FROM scraped_content
            WHERE pipeline_execution_id = $1::text
        """, str(pipeline_id))
        
        print(f"Content Scraping Progress:")
        print(f"  Total scraped: {scraped_stats['total_scraped']}")
        print(f"  Successful: {scraped_stats['successful']}")
        print(f"  Failed: {scraped_stats['failed']}")
        print(f"  Analyzed: {scraped_stats['analyzed']}")
        
        # Get total URLs from SERP
        total_urls = await conn.fetchval("""
            SELECT COUNT(DISTINCT url)
            FROM serp_results
            WHERE pipeline_execution_id = $1
            AND serp_type IN ('organic', 'news')
        """, pipeline_id)
        
        print(f"\nTotal URLs to process: {total_urls}")
        print(f"Progress: {scraped_stats['total_scraped']}/{total_urls} ({scraped_stats['total_scraped']/total_urls*100:.1f}%)")

asyncio.run(check())
