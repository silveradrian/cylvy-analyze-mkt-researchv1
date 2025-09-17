import asyncio
from app.core.database import db_pool
import redis.asyncio as redis
import json

async def reset():
    # Connect to Redis
    r = await redis.from_url("redis://redis:6379", decode_responses=True)
    
    # Reset YouTube circuit breaker
    key = "circuit_breaker:youtube_api"
    
    # Get current state
    current = await r.get(key)
    if current:
        data = json.loads(current)
        print(f"Current circuit breaker state: {data}")
        
        # Reset to closed state
        data['state'] = 'CLOSED'
        data['failure_count'] = 0
        data['last_failure_time'] = None
        data['consecutive_successes'] = 0
        
        await r.set(key, json.dumps(data))
        print(f"✅ Reset YouTube circuit breaker to CLOSED state")
    else:
        print("No circuit breaker data found")
    
    await r.close()

asyncio.run(reset())
