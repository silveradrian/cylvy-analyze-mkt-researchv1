import asyncio
import asyncpg
from app.core.config import settings

async def check_channels():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    # Get pending channels using the correct query
    pending = await conn.fetch('''
        WITH recent_channels AS (
            SELECT DISTINCT channel_id, channel_title
            FROM video_snapshots
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '2 days'
        )
        SELECT rc.channel_id, MIN(vs.channel_title) as channel_title
        FROM recent_channels rc
        JOIN video_snapshots vs ON vs.channel_id = rc.channel_id
        LEFT JOIN youtube_channel_companies ycc
            ON ycc.channel_id = rc.channel_id
        WHERE ycc.channel_id IS NULL OR COALESCE(ycc.company_domain, '') = ''
        GROUP BY rc.channel_id
        LIMIT 10
    ''')
    
    print(f'Found {len(pending)} pending channels:')
    for p in pending:
        print(f"  - {p['channel_id']}: {p['channel_title']}")
    
    # Check if these are the same 3 channels stuck in a loop
    if pending:
        print("\nChecking why these channels might be stuck:")
        for p in pending[:3]:
            # Check if they were attempted before
            attempts = await conn.fetchrow('''
                SELECT COUNT(*) as attempt_count,
                       MAX(created_at) as last_attempt
                FROM youtube_channel_companies
                WHERE channel_id = $1
            ''', p['channel_id'])
            
            videos = await conn.fetchval('''
                SELECT COUNT(*) FROM video_snapshots WHERE channel_id = $1
            ''', p['channel_id'])
            
            print(f"\n{p['channel_title']}:")
            print(f"  Channel ID: {p['channel_id']}")
            print(f"  Videos: {videos}")
            print(f"  Resolution attempts: {attempts['attempt_count']}")
            print(f"  Last attempt: {attempts['last_attempt']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_channels())
