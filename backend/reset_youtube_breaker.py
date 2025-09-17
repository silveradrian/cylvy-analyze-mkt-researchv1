import asyncio
import redis.asyncio as redis
import json

async def reset():
    # Connect to Redis
    r = await redis.from_url("redis://redis:6379", decode_responses=True)
    
    # Reset YouTube circuit breaker
    key = "circuit_breaker:youtube_api"
    
    # Delete the key to fully reset
    result = await r.delete(key)
    if result:
        print(f"✅ Reset YouTube API circuit breaker")
    else:
        print("YouTube API circuit breaker was not set")
    
    await r.aclose()

asyncio.run(reset())
