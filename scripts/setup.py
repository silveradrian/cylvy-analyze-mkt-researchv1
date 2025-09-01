#!/usr/bin/env python3
"""
Cylvy setup script for easy deployment
"""
import asyncio
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.db_init import init_database, DatabaseInitializer
from app.core.database_check import DatabaseHealthChecker
from app.core.config import settings


async def setup_cylvy():
    """Complete Cylvy setup process"""
    print("🚀 Cylvy Digital Landscape Analyzer Setup")
    print("=" * 50)
    
    # 1. Check database connection
    print("1. Checking database connection...")
    checker = DatabaseHealthChecker()
    connection_status = await checker.check_connection()
    
    if connection_status["status"] != "healthy":
        print(f"❌ Database connection failed: {connection_status.get('error')}")
        print("Please check your DATABASE_URL and ensure PostgreSQL is running")
        return False
    
    print("✅ Database connection successful")
    
    # 2. Initialize database
    print("2. Initializing database schema...")
    try:
        await init_database()
        print("✅ Database schema initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    
    # 3. Create admin user
    print("3. Creating admin user...")
    admin_email = input("Admin email (admin@cylvy.com): ") or "admin@cylvy.com"
    admin_password = input("Admin password (admin123): ") or "admin123"
    
    try:
        initializer = DatabaseInitializer()
        await initializer.create_admin_user(admin_email, admin_password)
        print(f"✅ Admin user created: {admin_email}")
    except Exception as e:
        print(f"❌ Admin user creation failed: {e}")
        return False
    
    # 4. Verify setup
    print("4. Verifying setup...")
    health_check = await checker.run_full_health_check()
    
    if health_check["overall_status"] == "healthy":
        print("✅ Setup verification successful")
    else:
        print("⚠️  Setup completed with warnings")
        for check_name, check_data in health_check["checks"].items():
            if check_data["status"] != "healthy":
                print(f"  - {check_name}: {check_data.get('error', 'Issues detected')}")
    
    print("\n🎉 Cylvy setup completed!")
    print("\nNext steps:")
    print("1. Start the application: docker-compose up -d")
    print("2. Access the admin portal: http://localhost:3000/admin/setup")
    print("3. Configure your company settings and upload logo")
    print("4. Add API keys for external services")
    print("5. Upload keywords and start your first analysis")
    print(f"\nAdmin login: {admin_email} / {admin_password}")
    
    return True


async def check_environment():
    """Check if environment is properly configured"""
    print("🔍 Environment Check")
    print("=" * 30)
    
    required_vars = [
        'DATABASE_URL',
        'SECRET_KEY',
        'JWT_SECRET_KEY'
    ]
    
    optional_vars = [
        'OPENAI_API_KEY',
        'SCALE_SERP_API_KEY',
        'SCRAPINGBEE_API_KEY',
        'COGNISM_API_KEY',
        'YOUTUBE_API_KEY'
    ]
    
    missing_required = []
    missing_optional = []
    
    for var in required_vars:
        value = getattr(settings, var, None)
        if not value or value == "your-secret-key-here":
            missing_required.append(var)
        else:
            print(f"✅ {var}: configured")
    
    for var in optional_vars:
        value = getattr(settings, var, None)
        if not value:
            missing_optional.append(var)
        else:
            print(f"✅ {var}: configured")
    
    if missing_required:
        print(f"\n❌ Missing required variables: {', '.join(missing_required)}")
        print("Please configure these in your .env file")
        return False
    
    if missing_optional:
        print(f"\n⚠️  Missing optional API keys: {', '.join(missing_optional)}")
        print("These can be configured later in the admin portal")
    
    print("\n✅ Environment check passed")
    return True


def main():
    """Main setup function"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "check":
            result = asyncio.run(check_environment())
            sys.exit(0 if result else 1)
        elif command == "init":
            result = asyncio.run(setup_cylvy())
            sys.exit(0 if result else 1)
        elif command == "health":
            async def health_check():
                checker = DatabaseHealthChecker()
                result = await checker.run_full_health_check()
                print(f"Database Status: {result['overall_status']}")
                return result['overall_status'] == 'healthy'
            
            result = asyncio.run(health_check())
            sys.exit(0 if result else 1)
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print("Cylvy Setup Script")
        print("Commands:")
        print("  check  - Check environment configuration")
        print("  init   - Initialize database and create admin user")
        print("  health - Check database health")
        print("\nUsage: python scripts/setup.py [command]")


if __name__ == "__main__":
    main()
