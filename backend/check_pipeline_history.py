import asyncio
import asyncpg
from app.core.config import settings

async def check_pipeline_history():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    print("Pipeline Execution History:\n")
    
    # Get all pipelines
    pipelines = await conn.fetch("""
        SELECT id, mode, started_at, completed_at, 
               keywords_processed, serp_results_collected,
               content_scraped, companies_enriched,
               phase_results->>'keyword_metrics'->>'keywords' as keywords_data
        FROM pipeline_executions
        ORDER BY started_at DESC
        LIMIT 10
    """)
    
    for p in pipelines:
        print(f"Pipeline: {p['id']}")
        print(f"  Started: {p['started_at']}")
        print(f"  Mode: {p['mode']}")
        print(f"  Keywords: {p['keywords_processed']}")
        print(f"  SERP Results: {p['serp_results_collected']}")
        print(f"  Content Scraped: {p['content_scraped']}")
        print()
    
    # Check keyword overlap between pipelines
    print("\nChecking keyword overlap between current and previous pipeline...\n")
    
    current_keywords = await conn.fetch("""
        SELECT DISTINCT k.keyword
        FROM serp_results sr
        JOIN keywords k ON k.id = sr.keyword_id
        WHERE sr.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    """)
    
    previous_keywords = await conn.fetch("""
        SELECT DISTINCT k.keyword
        FROM serp_results sr
        JOIN keywords k ON k.id = sr.keyword_id
        WHERE sr.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    current_set = {k['keyword'] for k in current_keywords}
    previous_set = {k['keyword'] for k in previous_keywords}
    
    overlap = current_set & previous_set
    new_keywords = current_set - previous_set
    
    print(f"Current pipeline keywords: {len(current_set)}")
    print(f"Previous pipeline keywords: {len(previous_set)}")
    print(f"Overlapping keywords: {len(overlap)}")
    print(f"New keywords in current: {len(new_keywords)}")
    
    if new_keywords and len(new_keywords) < 10:
        print(f"\nNew keywords:")
        for k in sorted(new_keywords)[:10]:
            print(f"  - {k}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_pipeline_history())
