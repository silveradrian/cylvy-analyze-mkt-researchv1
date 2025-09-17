import httpx
import asyncio

async def check_and_resume():
    pipeline_id = "1a1bac89-8056-41ff-8f20-8e82ec67999f"
    
    async with httpx.AsyncClient() as client:
        # Check status
        try:
            status_resp = await client.get(f"http://localhost:8000/api/v1/monitoring/pipeline/{pipeline_id}/phases")
            if status_resp.status_code == 200:
                phases = status_resp.json()
                print("Pipeline phase status:")
                for phase in phases:
                    print(f"  {phase['phase']}: {phase['status']}")
                    
                # Check if we need to resume
                incomplete_phases = [p for p in phases if p['status'] not in ['completed', 'skipped']]
                if incomplete_phases:
                    print(f"\nFound {len(incomplete_phases)} incomplete phases. Resuming pipeline...")
                    resume_resp = await client.post(f"http://localhost:8000/api/v1/pipeline/{pipeline_id}/resume", json={})
                    if resume_resp.status_code == 200:
                        print("Pipeline resumed successfully!")
                    else:
                        print(f"Failed to resume: {resume_resp.status_code}")
                else:
                    print("\nAll phases completed!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_and_resume())
