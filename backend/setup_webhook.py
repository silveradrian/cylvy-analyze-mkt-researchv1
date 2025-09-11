#!/usr/bin/env python3
"""
Helper script to set up Scale SERP webhook configuration
"""
import os
import re

def setup_webhook():
    print("🔧 Scale SERP Webhook Setup")
    print("=" * 50)
    
    # Get ngrok URL from user
    print("\n📌 Please check your ngrok terminal and find the HTTPS forwarding URL.")
    print("   It should look like: https://xxxxx-xxx-xxx.ngrok-free.app")
    
    ngrok_url = input("\nEnter your ngrok HTTPS URL: ").strip()
    
    # Validate URL format
    if not ngrok_url.startswith("https://"):
        print("❌ Error: URL must start with https://")
        return
    
    # Construct the full webhook URL
    webhook_url = f"{ngrok_url}/api/v1/webhooks/scaleserp/batch-complete"
    
    print(f"\n✅ Full webhook URL: {webhook_url}")
    
    # Read existing .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    if not os.path.exists(env_path):
        print(f"❌ Error: .env file not found at {env_path}")
        return
    
    with open(env_path, 'r') as f:
        env_content = f.read()
    
    # Check if SCALESERP_WEBHOOK_URL already exists
    if 'SCALESERP_WEBHOOK_URL=' in env_content:
        # Update existing value
        env_content = re.sub(
            r'SCALESERP_WEBHOOK_URL=.*',
            f'SCALESERP_WEBHOOK_URL={webhook_url}',
            env_content
        )
        print("\n✅ Updated existing SCALESERP_WEBHOOK_URL in .env")
    else:
        # Add new value
        env_content += f"\n\n# Scale SERP Webhook Configuration\nSCALESERP_WEBHOOK_URL={webhook_url}\n"
        print("\n✅ Added SCALESERP_WEBHOOK_URL to .env")
    
    # Write back to .env
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print("\n📋 Next steps:")
    print("1. Restart your Docker containers to pick up the new environment variable:")
    print("   docker-compose down && docker-compose up -d")
    print("\n2. The webhook endpoint is available at:")
    print(f"   {webhook_url}")
    print("\n3. Test the webhook health check:")
    print(f"   curl {ngrok_url}/api/v1/webhooks/health")
    print("\n4. When you create Scale SERP batches, they will now send completion notifications!")
    
    print("\n⚠️  Important notes:")
    print("- Keep ngrok running while testing webhooks")
    print("- The ngrok URL changes each time you restart it (unless you have a paid plan)")
    print("- Update the .env file again if you restart ngrok")

if __name__ == "__main__":
    setup_webhook()

