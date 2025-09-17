# Multi-Tenant Dashboard Developer Quickstart Guide

## Quick Reference for Client-Agnostic DSI Dashboard Development

**CRITICAL**: This is a multi-tenant SaaS platform. All queries MUST include `client_id` for data isolation.

### Essential Data Tables (Multi-Tenant)

| Table | Purpose | Key Fields | Entity Types |
|-------|---------|------------|--------------|
| `landscape_dsi_metrics` | **PRIMARY DSI DATA** | `client_id`, `dsi_score`, `rank_in_landscape`, `entity_type` | `company`, `page`, `keyword` |
| `client_landscapes` | **Client landscape definitions** | `client_id`, `landscape_name`, `business_unit`, `region` | - |
| `clients` | **Client configuration** | `client_id`, `name`, `logo_url`, `brand_color_primary` | - |
| `client_personas` | **Client persona definitions** | `client_id`, `persona_name`, `weight_technical`, `weight_business` | - |
| `client_metrics` | **Client DSI formulas** | `client_id`, `metric_name`, `component_weights`, `thresholds` | - |
| `company_profiles` | Company details | `company_name`, `industry`, `employee_count` | - |
| `keywords` | Keyword master data | `keyword`, `avg_monthly_searches`, `competition_level` | - |

---

## Most Common Dashboard Queries

### 1. 🏆 Top Companies in Client Landscape

```sql
SELECT 
    ldm.entity_name as company_name,
    ldm.entity_domain as domain,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.market_position,
    cp.industry
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain  
WHERE ldm.client_id = $1              -- CRITICAL: Client isolation
AND ldm.landscape_id = $2             -- Client's landscape UUID
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.rank_in_landscape
LIMIT 20;
```

### 2. 📊 Client Landscape Overview Stats

```sql
SELECT 
    COUNT(CASE WHEN entity_type = 'company' THEN 1 END) as total_companies,
    AVG(CASE WHEN entity_type = 'company' THEN dsi_score END) as avg_dsi,
    MAX(CASE WHEN entity_type = 'company' THEN dsi_score END) as top_dsi,
    SUM(CASE WHEN entity_type = 'company' THEN estimated_traffic END) as total_traffic
FROM landscape_dsi_metrics
WHERE client_id = $1                  -- CRITICAL: Client isolation
AND landscape_id = $2
AND calculation_date = CURRENT_DATE;
```

### 3. 🎯 Company Performance Across Landscapes

```sql
SELECT 
    dl.name as landscape_name,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.market_position,
    ldm.estimated_traffic
FROM landscape_dsi_metrics ldm
JOIN digital_landscapes dl ON ldm.landscape_id = dl.id
WHERE ldm.entity_domain = $1         -- Company domain
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.dsi_score DESC;
```

### 4. 📈 Top Content by Landscape

```sql
SELECT 
    ldm.entity_name as page_title,
    ldm.entity_url as url,
    ldm.entity_domain as domain, 
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.estimated_traffic
FROM landscape_dsi_metrics ldm
WHERE ldm.landscape_id = $1
AND ldm.entity_type = 'page'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.rank_in_landscape
LIMIT 10;
```

---

## FastAPI Service Template

### Basic Service Structure

```python
# app/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import redis.asyncio as redis
from typing import List, Optional
import os

app = FastAPI(
    title="Digital Landscape Dashboards",
    description="Customer-facing DSI analytics and landscape intelligence",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)

@app.on_event("shutdown") 
async def shutdown():
    await db_pool.close()
```

### Authentication Integration

```python
# app/core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
import jwt
from typing import Optional

security = HTTPBearer()

class User:
    def __init__(self, user_id: str, email: str, permissions: dict):
        self.user_id = user_id
        self.email = email
        self.permissions = permissions
    
    def has_landscape_access(self, landscape_id: str) -> bool:
        landscape_perms = self.permissions.get('landscapes', [])
        return 'all' in landscape_perms or landscape_id in landscape_perms

async def get_current_user(token: str = Depends(security)) -> User:
    try:
        payload = jwt.decode(
            token.credentials, 
            os.getenv("JWT_SECRET_KEY"), 
            algorithms=["HS256"]
        )
        return User(
            user_id=payload['user_id'],
            email=payload['email'], 
            permissions=payload['permissions']
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
```

### Sample API Endpoint

```python
# app/api/v1/landscapes.py
from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from uuid import UUID
from datetime import date

router = APIRouter(prefix="/landscapes", tags=["landscapes"])

@router.get("/{landscape_id}/overview")
async def get_landscape_overview(
    landscape_id: UUID,
    calculation_date: Optional[date] = Query(None),
    user: User = Depends(get_current_user)
):
    # Verify access
    if not user.has_landscape_access(str(landscape_id)):
        raise HTTPException(403, "Insufficient landscape permissions")
    
    # Get from cache first
    cache_key = f"dash:landscape:{landscape_id}:{calculation_date or 'latest'}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Query database
    async with db_pool.acquire() as conn:
        # Landscape basic info
        landscape = await conn.fetchrow("""
            SELECT id, name, business_unit, region, description
            FROM digital_landscapes 
            WHERE id = $1 AND is_active = true
        """, landscape_id)
        
        if not landscape:
            raise HTTPException(404, "Landscape not found")
        
        # Summary metrics
        summary = await conn.fetchrow("""
            SELECT 
                COUNT(CASE WHEN entity_type = 'company' THEN 1 END) as total_companies,
                AVG(CASE WHEN entity_type = 'company' THEN dsi_score END) as avg_company_dsi,
                MAX(CASE WHEN entity_type = 'company' THEN dsi_score END) as top_company_dsi,
                SUM(CASE WHEN entity_type = 'company' THEN estimated_traffic END) as total_traffic
            FROM landscape_dsi_metrics
            WHERE landscape_id = $1 AND calculation_date = COALESCE($2, CURRENT_DATE)
        """, landscape_id, calculation_date)
        
        # Top performers
        top_companies = await conn.fetch("""
            SELECT entity_name, entity_domain, dsi_score, rank_in_landscape, market_position
            FROM landscape_dsi_metrics ldm
            WHERE landscape_id = $1 AND entity_type = 'company'
            AND calculation_date = COALESCE($2, CURRENT_DATE)
            ORDER BY rank_in_landscape LIMIT 5
        """, landscape_id, calculation_date)
        
        result = {
            "landscape": dict(landscape),
            "calculation_date": str(calculation_date or date.today()),
            "summary": dict(summary),
            "top_companies": [dict(row) for row in top_companies]
        }
        
        # Cache result
        await redis_client.setex(cache_key, 3600, json.dumps(result, default=str))
        return result
```

---

## Frontend Integration Examples

### React Component Data Flow

```typescript
// types/landscape.ts
interface LandscapeOverview {
  landscape_id: string;
  name: string;
  business_unit: string;
  region: string;
  calculation_date: string;
  summary: {
    total_companies: number;
    avg_company_dsi: number;
    top_company_dsi: number;
    total_traffic: number;
  };
  top_companies: Company[];
}

interface Company {
  rank: number;
  company_name: string;
  domain: string;
  dsi_score: number;
  market_position: 'leader' | 'challenger' | 'competitor' | 'niche';
  industry?: string;
  keyword_count: number;
  estimated_traffic: number;
}
```

```typescript
// hooks/useLandscapeData.ts
import { useQuery } from '@tanstack/react-query';

export const useLandscapeOverview = (landscapeId: string) => {
  return useQuery({
    queryKey: ['landscape', 'overview', landscapeId],
    queryFn: () => fetch(`/api/v1/landscapes/${landscapeId}/overview`).then(r => r.json()),
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 30 * 60 * 1000 // 30 minutes
  });
};

export const useCompanyRankings = (landscapeId: string, page = 1, limit = 50) => {
  return useQuery({
    queryKey: ['landscape', 'companies', landscapeId, page],
    queryFn: () => 
      fetch(`/api/v1/landscapes/${landscapeId}/companies?page=${page}&limit=${limit}`)
        .then(r => r.json()),
    keepPreviousData: true
  });
};
```

---

## Data Visualization Patterns

### 1. DSI Score Visualization

```javascript
// DSI score color mapping
const getDSIColor = (score, entityType) => {
  const thresholds = {
    company: { leader: 10, challenger: 5, competitor: 1 },
    page: { leader: 1, challenger: 0.5, competitor: 0.1 },
    keyword: { leader: 1, challenger: 0.5, competitor: 0.1 }
  };
  
  const t = thresholds[entityType];
  if (score >= t.leader) return '#10B981'; // Green
  if (score >= t.challenger) return '#F59E0B'; // Orange  
  if (score >= t.competitor) return '#6B7280'; // Gray
  return '#EF4444'; // Red
};
```

### 2. Market Position Mapping

```javascript
const marketPositions = {
  leader: { 
    icon: '👑', 
    color: '#10B981', 
    description: 'Market leader with strong DSI performance' 
  },
  challenger: { 
    icon: '🚀', 
    color: '#F59E0B', 
    description: 'Strong challenger with growth potential' 
  },
  competitor: { 
    icon: '⚡', 
    color: '#6B7280', 
    description: 'Established competitor with steady presence' 
  },
  niche: { 
    icon: '🎯', 
    color: '#EF4444', 
    description: 'Specialized niche player' 
  }
};
```

---

## Critical Data Relationships

### Join Patterns for Dashboard Queries

```sql
-- Standard landscape data join
FROM landscape_dsi_metrics ldm
JOIN digital_landscapes dl ON ldm.landscape_id = dl.id
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain

-- For keyword details
FROM landscape_dsi_metrics ldm  
JOIN keywords k ON ldm.entity_id::text = k.id::text
WHERE ldm.entity_type = 'keyword'

-- For page content details
FROM landscape_dsi_metrics ldm
LEFT JOIN historical_page_dsi_snapshots hpds ON ldm.entity_url = hpds.url
WHERE ldm.entity_type = 'page'

-- For real-time SERP data (drill-downs)
FROM landscape_dsi_metrics ldm
JOIN serp_results sr ON (
    (ldm.entity_type = 'company' AND sr.domain = ldm.entity_domain) OR
    (ldm.entity_type = 'page' AND sr.url = ldm.entity_url) OR  
    (ldm.entity_type = 'keyword' AND sr.keyword_id::text = ldm.entity_id)
)
```

---

## Dashboard Components Checklist

### Essential Dashboard Views

- [ ] **Landscape Grid**: Overview of all 24 landscapes with key metrics
- [ ] **Company Rankings**: Sortable, filterable company leaderboards
- [ ] **Competitive Positioning**: Bubble chart with DSI vs traffic share
- [ ] **Content Performance**: Top-performing pages and content pieces
- [ ] **Keyword Analysis**: Keyword difficulty vs opportunity matrix
- [ ] **Company Deep Dive**: Multi-landscape company analysis
- [ ] **Market Trends**: Time series DSI performance charts
- [ ] **Export Functions**: CSV/PDF export capabilities

### Advanced Features

- [ ] **Real-time Updates**: WebSocket integration for live DSI updates
- [ ] **Alerts**: Threshold-based notifications for DSI changes
- [ ] **Competitor Tracking**: Watch list for competitive intelligence
- [ ] **Custom Dashboards**: User-configurable dashboard layouts
- [ ] **Data Drill-downs**: Link to detailed SERP and content analysis
- [ ] **API Access**: Developer API for custom integrations

---

## Sample Frontend Component

```typescript
// components/LandscapeOverview.tsx
interface LandscapeOverviewProps {
  landscapeId: string;
}

export const LandscapeOverview: React.FC<LandscapeOverviewProps> = ({ landscapeId }) => {
  const { data: overview, isLoading, error } = useLandscapeOverview(landscapeId);
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  
  return (
    <div className="landscape-overview">
      <div className="header">
        <h1>{overview.landscape.name}</h1>
        <div className="metrics-grid">
          <MetricCard 
            label="Companies" 
            value={overview.summary.total_companies}
            trend="+5.2%"
          />
          <MetricCard 
            label="Avg DSI" 
            value={overview.summary.avg_company_dsi.toFixed(2)}
            trend="+0.8%"
          />
          <MetricCard 
            label="Top DSI" 
            value={overview.summary.top_company_dsi.toFixed(2)}
            trend="+2.1%"
          />
          <MetricCard 
            label="Total Traffic" 
            value={formatNumber(overview.summary.total_traffic)}
            trend="+12.3%"
          />
        </div>
      </div>
      
      <div className="rankings">
        <CompanyRankingsTable companies={overview.top_companies} />
      </div>
      
      <div className="charts">
        <CompetitivePositioningChart landscapeId={landscapeId} />
        <MarketShareChart landscapeId={landscapeId} />
      </div>
    </div>
  );
};
```

---

## Database Connection Pool

```python
# app/core/database.py
import asyncpg
import os

class DatabaseManager:
    def __init__(self):
        self.pool = None
    
    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL"),
            min_size=5,
            max_size=20,
            command_timeout=30,
            server_settings={
                'application_name': 'dashboard_service',
                'search_path': 'public'
            }
        )
    
    async def fetch_landscape_overview(self, landscape_id: str, calculation_date: str = None):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT 
                    dl.name, dl.business_unit, dl.region,
                    COUNT(CASE WHEN ldm.entity_type = 'company' THEN 1 END) as companies,
                    AVG(CASE WHEN ldm.entity_type = 'company' THEN ldm.dsi_score END) as avg_dsi
                FROM digital_landscapes dl
                LEFT JOIN landscape_dsi_metrics ldm ON dl.id = ldm.landscape_id
                WHERE dl.id = $1 AND ldm.calculation_date = COALESCE($2::date, CURRENT_DATE)
                GROUP BY dl.id, dl.name, dl.business_unit, dl.region
            """, landscape_id, calculation_date)

# Global instance
db = DatabaseManager()
```

---

## Cache Service

```python
# app/services/cache_service.py
import redis.asyncio as redis
import json
from typing import Any, Optional
import os

class CacheService:
    def __init__(self):
        self.redis = redis.from_url(os.getenv("REDIS_URL"))
    
    async def get_landscape_overview(self, landscape_id: str, date: str) -> Optional[dict]:
        key = f"dash:landscape:{landscape_id}:{date}"
        cached = await self.redis.get(key)
        return json.loads(cached) if cached else None
    
    async def set_landscape_overview(self, landscape_id: str, date: str, data: dict, ttl: int = 3600):
        key = f"dash:landscape:{landscape_id}:{date}"
        await self.redis.setex(key, ttl, json.dumps(data, default=str))
    
    async def invalidate_landscape(self, landscape_id: str):
        pattern = f"dash:landscape:{landscape_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

# Global instance
cache = CacheService()
```

---

## Testing Data Queries

### Verify DSI Data Availability

```sql
-- Check data freshness and coverage
SELECT 
    dl.name,
    ldm.calculation_date,
    COUNT(CASE WHEN ldm.entity_type = 'company' THEN 1 END) as companies,
    COUNT(CASE WHEN ldm.entity_type = 'page' THEN 1 END) as pages,
    COUNT(CASE WHEN ldm.entity_type = 'keyword' THEN 1 END) as keywords,
    MAX(CASE WHEN ldm.entity_type = 'company' THEN ldm.dsi_score END) as top_company_dsi
FROM digital_landscapes dl
LEFT JOIN landscape_dsi_metrics ldm ON dl.id = ldm.landscape_id
    AND ldm.calculation_date >= CURRENT_DATE - INTERVAL '7 days'
WHERE dl.is_active = true
GROUP BY dl.id, dl.name, ldm.calculation_date
ORDER BY dl.name, ldm.calculation_date DESC;
```

### Sample Data Check

```sql
-- Get sample data for development
SELECT 
    'company' as entity_type, entity_name, dsi_score, market_position
FROM landscape_dsi_metrics
WHERE landscape_id = (SELECT id FROM digital_landscapes WHERE name = 'Payments' LIMIT 1)
AND entity_type = 'company' AND calculation_date = CURRENT_DATE
ORDER BY rank_in_landscape LIMIT 5

UNION ALL

SELECT 
    'page' as entity_type, entity_name, dsi_score, market_position  
FROM landscape_dsi_metrics
WHERE landscape_id = (SELECT id FROM digital_landscapes WHERE name = 'Payments' LIMIT 1)
AND entity_type = 'page' AND calculation_date = CURRENT_DATE
ORDER BY rank_in_landscape LIMIT 5;
```

---

## Production Deployment

### Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    try:
        # Check database
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        # Check redis
        await cache.redis.ping()
        
        # Check latest DSI data
        latest_calc = await db.fetch_landscape_overview(
            "4e773f12-12b7-4118-b859-faadc0abc60b"  # Sample landscape
        )
        
        return {
            "status": "healthy",
            "database": "connected",
            "cache": "connected", 
            "latest_dsi_data": latest_calc is not None,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
```

### Environment Variables

```bash
# Required environment variables for dashboard service
DATABASE_URL=postgresql://dashboard_user:password@postgres:5432/cylvy_analyze
REDIS_URL=redis://redis:6379
JWT_SECRET_KEY=your_super_secret_jwt_key
CORS_ORIGINS=["http://localhost:3000","https://yourdomain.com"]
LOG_LEVEL=INFO
CACHE_DEFAULT_TTL=3600
```

---

This quickstart guide provides all the essential patterns and code examples needed to rapidly develop the digital landscape dashboard service!
