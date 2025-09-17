import asyncio
import asyncpg
from app.core.config import settings

async def check_scraped_content():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    # Total rows in scraped_content
    total = await conn.fetchval('SELECT COUNT(*) FROM scraped_content')
    print(f'Total rows in scraped_content table: {total:,}')
    
    # Breakdown by status
    status_breakdown = await conn.fetch('''
        SELECT status, COUNT(*) as count
        FROM scraped_content
        GROUP BY status
        ORDER BY count DESC
    ''')
    
    print(f'\nBreakdown by status:')
    for row in status_breakdown:
        print(f'  {row["status"]}: {row["count"]:,}')
    
    # Recent activity
    recent = await conn.fetchval('''
        SELECT COUNT(*) 
        FROM scraped_content 
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
    ''')
    
    print(f'\nRows added in last 7 days: {recent:,}')
    
    # By pipeline
    pipeline_breakdown = await conn.fetch('''
        SELECT 
            COALESCE(pipeline_execution_id::text, 'NULL') as pipeline_id,
            COUNT(*) as count
        FROM scraped_content
        GROUP BY pipeline_execution_id
        ORDER BY count DESC
        LIMIT 10
    ''')
    
    print(f'\nTop 10 pipelines by scraped content:')
    for row in pipeline_breakdown:
        pid = row["pipeline_id"]
        if pid != 'NULL':
            pid = pid[:8] + '...'
        print(f'  {pid}: {row["count"]:,}')
    
    # Check for duplicates
    duplicates = await conn.fetchval('''
        SELECT COUNT(*) 
        FROM (
            SELECT url, COUNT(*) as cnt
            FROM scraped_content
            GROUP BY url
            HAVING COUNT(*) > 1
        ) as dup
    ''')
    
    print(f'\nURLs scraped multiple times: {duplicates:,}')
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_scraped_content())
