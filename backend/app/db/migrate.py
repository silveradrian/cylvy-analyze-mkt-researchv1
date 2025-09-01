"""
Database migration runner
"""
import asyncio
import sys
from pathlib import Path

from app.core.db_init import DatabaseInitializer, init_database, reset_database
from app.core.database_check import DatabaseHealthChecker
from loguru import logger


async def run_migrations():
    """Run database migrations"""
    initializer = DatabaseInitializer()
    await initializer.initialize_database()


async def check_health():
    """Check database health"""
    checker = DatabaseHealthChecker()
    result = await checker.run_full_health_check()
    
    # Print results
    print(f"Database Status: {result['overall_status']}")
    for check_name, check_data in result['checks'].items():
        print(f"  {check_name}: {check_data['status']}")


async def create_admin_user(email: str = None, password: str = None):
    """Create admin user"""
    initializer = DatabaseInitializer()
    await initializer.create_admin_user(
        email or "admin@cylvy.com",
        password or "admin123"
    )


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python -m app.db.migrate [command]")
        print("Commands:")
        print("  init     - Initialize database with schema")
        print("  reset    - Reset database (DANGEROUS)")
        print("  health   - Check database health")
        print("  admin    - Create admin user")
        return
    
    command = sys.argv[1]
    
    if command == "init":
        asyncio.run(run_migrations())
    elif command == "reset":
        if input("Are you sure you want to reset the database? (yes/no): ") == "yes":
            asyncio.run(reset_database())
        else:
            print("Reset cancelled")
    elif command == "health":
        asyncio.run(check_health())
    elif command == "admin":
        email = input("Admin email (admin@cylvy.com): ") or "admin@cylvy.com"
        password = input("Admin password (admin123): ") or "admin123"
        asyncio.run(create_admin_user(email, password))
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
