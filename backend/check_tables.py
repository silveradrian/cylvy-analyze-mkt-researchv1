import asyncio
import asyncpg
from app.core.config import settings

async def check_tables():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    # Check if tables exist
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%channel%'
        ORDER BY table_name
    """)
    
    print('Tables with channel in name:')
    for t in tables:
        print(f"  - {t['table_name']}")
    
    # Check if youtube_channel_companies exists
    exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'youtube_channel_companies'
        )
    """)
    
    print(f"\nyoutube_channel_companies exists: {exists}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_tables())
