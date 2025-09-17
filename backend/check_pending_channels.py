import asyncio
import asyncpg
from app.core.config import settings

async def check_channels():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    # Get pending channels
    pending = await conn.fetch('''
        SELECT DISTINCT v.channel_id, v.channel_title
        FROM video_snapshots v
        LEFT JOIN channel_domains cd ON v.channel_id = cd.channel_id
        WHERE cd.channel_id IS NULL
        LIMIT 10
    ''')
    
    print(f'Found {len(pending)} pending channels:')
    for p in pending:
        print(f"  - {p['channel_id']}: {p['channel_title']}")
    
    # Check if these channels have any useful info
    if pending:
        print("\nChecking channel context...")
        for p in pending[:3]:
            context = await conn.fetchrow('''
                SELECT COUNT(*) as video_count,
                       MIN(published_at) as first_video,
                       MAX(published_at) as last_video
                FROM video_snapshots
                WHERE channel_id = $1
            ''', p['channel_id'])
            print(f"\n{p['channel_title']}:")
            print(f"  Videos: {context['video_count']}")
            print(f"  First: {context['first_video']}")
            print(f"  Last: {context['last_video']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_channels())
