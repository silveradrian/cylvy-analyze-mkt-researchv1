import requests
import json
from datetime import datetime

# Setup
token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzYjJhOTZiNy1jMzdjLTRhZTktOWE4YS1mN2ZhY2M3MGRhNGQiLCJleHAiOjE3NTY4MjM1ODB9.b58THGU8LjfWa4jnfMaGybtWSyeOFbGtt9rcemKOfk4'
headers = {'Authorization': f'Bearer {token}'}
api_base = 'http://localhost:8001/api/v1'

print('🎯 Finastra System Monitoring Dashboard')
print('=' * 50)

def check_endpoint(name, url, expected_keys=None):
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if expected_keys:
                found_keys = [key for key in expected_keys if key in data and data[key]]
                status = '✅' if found_keys else '⚠️'
                print(f'{status} {name}: {response.status_code} - {len(found_keys)}/{len(expected_keys)} configured')
                if found_keys:
                    print(f'   Configured: {", ".join(found_keys)}')
            else:
                print(f'✅ {name}: {response.status_code} - Working')
                if isinstance(data, list):
                    print(f'   Records: {len(data)}')
        else:
            print(f'❌ {name}: {response.status_code} - {response.text[:100]}')
    except Exception as e:
        print(f'❌ {name}: Connection error - {str(e)[:100]}')

# Check system components
print('\n🔧 System Health:')
check_endpoint('API Health', f'{api_base}/health')
check_endpoint('Auth Status', f'{api_base}/auth/me')

print('\n🏢 Finastra Configuration:')
check_endpoint('Company Config', f'{api_base}/config', ['company_name', 'company_domain', 'admin_email'])
check_endpoint('Branding Config', f'{api_base}/config/branding', ['primary_color', 'secondary_color'])

print('\n📊 Analysis Setup:') 
check_endpoint('Personas', f'{api_base}/analysis/personas', ['personas'])
check_endpoint('Competitors', f'{api_base}/analysis/competitors', ['competitor_domains'])
check_endpoint('Keywords', f'{api_base}/keywords')

print('\n🚀 Ready Actions:')
print('   • Frontend Admin: http://localhost:3000')
print('   • API Documentation: http://localhost:8001/docs')
print('   • Setup Wizard: http://localhost:3000/setup (auto-detects existing config)')

# Show timestamp
print(f'\n⏰ Status checked at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

