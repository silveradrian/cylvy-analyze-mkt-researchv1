# Cylvy Digital Landscape Analyzer - Deployment Guide

## Single-Instance Deployment Model

Each client gets their own dedicated instance with complete data isolation and customization.

## Prerequisites

- Docker & Docker Compose
- PostgreSQL with TimescaleDB
- Redis
- At least 4GB RAM, 2 CPU cores
- 50GB storage space

## Quick Deployment

### 1. Clone Repository
```bash
git clone https://github.com/silveradrian/cylvy-analyze-mkt-researchv1.git
cd cylvy-analyze-mkt-researchv1
```

### 2. Environment Configuration
```bash
# Backend environment
cp backend/.env.example backend/.env
# Edit backend/.env with your settings

# Frontend environment  
cp frontend/.env.example frontend/.env
# Edit frontend/.env with your settings
```

### 3. Start Services
```bash
# Development
docker-compose up -d

# Production (with optimized images)
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Initialize Database
```bash
# Run migrations
docker-compose exec backend python -c "
from app.core.database import db_pool
import asyncio
import asyncpg

async def run_migrations():
    await db_pool.initialize()
    # Migrations would run here
    print('Database initialized')

asyncio.run(run_migrations())
"
```

### 5. Create Admin User
```bash
docker-compose exec backend python -c "
from app.core.auth import AuthService
from app.core.database import db_pool
import asyncio

async def create_admin():
    await db_pool.initialize()
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (email, hashed_password, full_name, role)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (email) DO NOTHING
        ''', 
        'admin@yourcompany.com',
        AuthService.get_password_hash('admin123'),
        'Admin User',
        'superadmin')
    print('Admin user created')

asyncio.run(create_admin())
"
```

### 6. Access Application
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Admin Setup**: http://localhost:3000/admin/setup

## Client Customization

### Initial Setup Wizard
1. Navigate to `/admin/setup`
2. Configure company information
3. Upload logo and set brand colors
4. Configure API keys
5. Set up personas and JTBD phases
6. Start first pipeline

### Configuration Options
- **Company Branding**: Logo, colors, name
- **AI Analysis**: Custom prompts, personas, JTBD phases
- **Competitor Tracking**: Domain lists
- **API Integration**: External service keys
- **Pipeline Settings**: Scheduling, concurrency limits

## Production Deployment

### Environment Variables
```bash
# Security (REQUIRED)
SECRET_KEY=generate-secure-32-character-key
JWT_SECRET_KEY=generate-different-secure-key

# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# External APIs (Configure in admin portal)
OPENAI_API_KEY=sk-your-key
SCALE_SERP_API_KEY=your-key
SCRAPINGBEE_API_KEY=your-key
COGNISM_API_KEY=your-key
YOUTUBE_API_KEY=your-key
```

### Resource Requirements
- **Minimum**: 2 CPU, 4GB RAM, 50GB storage
- **Recommended**: 4 CPU, 8GB RAM, 100GB storage
- **High Volume**: 8 CPU, 16GB RAM, 200GB storage

### Monitoring
- Health checks at `/health`
- WebSocket connections for real-time updates
- Application logs in `/var/log/cylvy/`
- Database metrics via TimescaleDB

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│    Backend      │────▶│   Database      │
│   (Next.js)     │     │   (FastAPI)     │     │ (TimescaleDB)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                        │                        │
         │                        ▼                        │
         │               ┌─────────────────┐                │
         │               │     Redis       │                │
         │               │   (Caching)     │                │
         │               └─────────────────┘                │
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Client Storage  │     │ External APIs   │     │ File Storage    │
│ (Logos/Exports) │     │ (OpenAI, etc.)  │     │ (Local/Cloud)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Support

For deployment support, refer to the application documentation or contact technical support.
