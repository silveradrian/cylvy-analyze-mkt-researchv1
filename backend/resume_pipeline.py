import httpx
import asyncio
import json

async def resume_pipeline():
    pipeline_id = "1a1bac89-8056-41ff-8f20-8e82ec67999f"
    url = f"http://localhost:8000/api/v1/pipeline/{pipeline_id}/resume"
    
    async with httpx.AsyncClient() as client:
        try:
            # Try without authentication first
            response = await client.post(url, json={})
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
            
            if response.status_code == 200:
                print("Pipeline resumed successfully!")
            elif response.status_code == 401:
                print("Authentication required. Pipeline needs to be resumed with proper credentials.")
            else:
                print(f"Failed to resume pipeline: {response.status_code}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(resume_pipeline())
