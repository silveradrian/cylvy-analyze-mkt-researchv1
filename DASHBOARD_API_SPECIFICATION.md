# Digital Landscape Dashboard API Specification

## Service Overview

The Dashboard service is a containerized microservice that provides customer-facing APIs for digital landscape analytics. It leverages the main database's DSI calculations and provides optimized, cached access to landscape intelligence.

---

## API Endpoints Specification

### Base Configuration

```yaml
Base URL: http://localhost:8002/api/v1
Authentication: Bearer JWT token
Content-Type: application/json
Rate Limiting: 100 requests/minute per user
```

---

## 1. Landscape Management Endpoints

### GET `/landscapes`
Get all available digital landscapes

**Response:**
```json
{
  "landscapes": [
    {
      "id": "4e773f12-12b7-4118-b859-faadc0abc60b",
      "name": "Payments",
      "business_unit": "Payments", 
      "region": "Global",
      "description": "Digital payment solutions and infrastructure",
      "is_active": true,
      "total_companies": 238,
      "total_pages": 6605,
      "total_keywords": 103,
      "last_calculated": "2025-09-17"
    }
  ],
  "total": 24
}
```

### GET `/landscapes/{landscape_id}/overview`
Get comprehensive landscape overview

**Parameters:**
- `landscape_id` (UUID): Landscape identifier
- `date` (optional, date): Specific calculation date (defaults to latest)

**Response:**
```json
{
  "landscape": {
    "id": "4e773f12-12b7-4118-b859-faadc0abc60b",
    "name": "Payments",
    "business_unit": "Payments",
    "region": "Global"
  },
  "calculation_date": "2025-09-17",
  "summary_metrics": {
    "total_companies": 238,
    "total_pages": 6605,
    "total_keywords": 103,
    "total_traffic": 2500000,
    "avg_company_dsi": 2.45,
    "top_company_dsi": 15.67,
    "market_concentration": {
      "leaders": 12,
      "challengers": 48,
      "competitors": 98,
      "niche": 80
    }
  },
  "top_performers": {
    "companies": [
      {
        "rank": 1,
        "company_name": "Finastra",
        "domain": "finastra.com", 
        "dsi_score": 15.67,
        "market_position": "leader",
        "keyword_count": 45,
        "traffic_share_pct": 5.2,
        "industry": "Financial Services"
      }
    ],
    "content": [
      {
        "rank": 1,
        "title": "How EU Instant Payments is Reshaping Finance Infrastructure",
        "url": "https://fintechmagazine.com/news/how-eu-instant-payments",
        "domain": "fintechmagazine.com",
        "dsi_score": 1.449,
        "keyword_count": 12,
        "sentiment": "positive"
      }
    ],
    "keywords": [
      {
        "rank": 1,
        "keyword": "instant payments",
        "dsi_score": 2.567,
        "search_volume": 45000,
        "competition": "HIGH",
        "avg_cpc": 8.50
      }
    ]
  }
}
```

---

## 2. Company Analysis Endpoints

### GET `/companies/search`
Search and filter companies across landscapes

**Query Parameters:**
- `query` (string): Company name search
- `industry` (string): Industry filter
- `market_position` (string): Position filter (`leader`, `challenger`, `competitor`, `niche`)
- `min_dsi` (float): Minimum DSI score
- `landscape_id` (UUID): Specific landscape filter
- `limit` (int): Results limit (default: 50, max: 200)
- `offset` (int): Pagination offset

**Response:**
```json
{
  "companies": [
    {
      "domain": "finastra.com",
      "company_name": "Finastra",
      "industry": "Financial Services",
      "employee_count": "10001+",
      "avg_dsi_score": 12.34,
      "best_dsi_score": 15.67,
      "landscapes_present": 8,
      "primary_landscape": "Payments",
      "market_positions": ["leader", "challenger"]
    }
  ],
  "total": 156,
  "pagination": {
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

### GET `/companies/{domain}/analysis`
Detailed company analysis across all landscapes

**Parameters:**
- `domain` (string): Company domain
- `include_content` (boolean): Include top content (default: false)
- `include_keywords` (boolean): Include keyword performance (default: false)

**Response:**
```json
{
  "company": {
    "domain": "finastra.com",
    "company_name": "Finastra", 
    "industry": "Financial Services",
    "employee_count": "10001+",
    "description": "Global financial technology company..."
  },
  "landscape_performance": [
    {
      "landscape_id": "4e773f12-12b7-4118-b859-faadc0abc60b",
      "landscape_name": "Payments",
      "dsi_score": 15.67,
      "rank": 1,
      "total_competitors": 238,
      "market_position": "leader",
      "keyword_count": 45,
      "page_count": 23,
      "keyword_coverage_pct": 43.7,
      "traffic_share_pct": 5.2,
      "persona_alignment_pct": 78.4,
      "estimated_traffic": 125000
    }
  ],
  "performance_summary": {
    "best_landscape": "Payments",
    "best_dsi_score": 15.67,
    "avg_dsi_score": 8.94,
    "total_landscapes": 8,
    "leader_positions": 2,
    "challenger_positions": 4,
    "competitor_positions": 2
  },
  "content_highlights": [
    {
      "title": "Finastra Payment Solutions Overview",
      "url": "https://finastra.com/payments",
      "dsi_score": 2.45,
      "keyword_count": 8,
      "sentiment": "positive",
      "landscape": "Payments"
    }
  ],
  "keyword_performance": [
    {
      "keyword": "payment orchestration",
      "rank": 3,
      "dsi_score": 0.8934,
      "search_volume": 12000,
      "competition": "HIGH",
      "landscape": "Payments"
    }
  ]
}
```

---

## 3. Content Analysis Endpoints

### GET `/content/top-performing`
Get top-performing content across landscapes

**Query Parameters:**
- `landscape_id` (UUID): Specific landscape
- `content_type` (string): Content type filter (`organic`, `news`, `video`)
- `sentiment` (string): Sentiment filter (`positive`, `neutral`, `negative`)
- `min_dsi` (float): Minimum DSI threshold
- `date_range` (string): Date range (`7d`, `30d`, `90d`)
- `limit` (int): Results limit

**Response:**
```json
{
  "content": [
    {
      "rank": 1,
      "title": "How EU Instant Payments is Reshaping Finance Infrastructure",
      "url": "https://fintechmagazine.com/news/how-eu-instant-payments",
      "domain": "fintechmagazine.com",
      "company_name": "FinTech Magazine",
      "dsi_score": 1.449,
      "landscape_rank": 1,
      "keyword_count": 12,
      "estimated_traffic": 45000,
      "avg_position": 2.3,
      "top_keywords": ["instant payments", "EU payments", "finance infrastructure"],
      "sentiment": "positive",
      "content_type": "news",
      "word_count": 1200,
      "brand_mentions": 3,
      "publish_date": "2025-09-15",
      "freshness_score": 0.95
    }
  ],
  "summary": {
    "total_pages": 6605,
    "avg_dsi_score": 0.234,
    "sentiment_distribution": {
      "positive": 45.2,
      "neutral": 48.1,
      "negative": 6.7
    }
  }
}
```

---

## 4. Keyword Intelligence Endpoints

### GET `/keywords/{landscape_id}/performance`
Keyword performance analysis for landscape

**Query Parameters:**
- `category` (string): Keyword category filter
- `jtbd_stage` (string): JTBD stage filter
- `min_search_volume` (int): Minimum search volume
- `competition_level` (string): Competition filter
- `sort` (string): Sort field (`dsi_score`, `search_volume`, `competition`)

**Response:**
```json
{
  "keywords": [
    {
      "rank": 1,
      "keyword": "instant payments",
      "category": "solution",
      "jtbd_stage": "consideration", 
      "is_brand": false,
      "dsi_score": 2.567,
      "search_volume": 45000,
      "competition_level": "HIGH",
      "low_cpc": 5.20,
      "high_cpc": 18.50,
      "serp_results": 89,
      "unique_domains": 34,
      "avg_position": 3.2,
      "top_10_results": 67,
      "persona_score": 8.4,
      "strategic_score": 7.8,
      "analyzed_pages": 23,
      "sentiment_distribution": {
        "positive": 65.2,
        "neutral": 30.4,
        "negative": 4.4
      }
    }
  ],
  "landscape": {
    "name": "Payments", 
    "total_keywords": 103,
    "avg_search_volume": 8420
  }
}
```

---

## 5. Competitive Intelligence Endpoints

### POST `/competitive/comparison`
Compare multiple companies across landscapes

**Request Body:**
```json
{
  "companies": ["finastra.com", "temenos.com", "fiserv.com"],
  "landscapes": ["payments", "universal-banking"],
  "metrics": ["dsi_score", "keyword_count", "traffic_share"],
  "date_range": "30d"
}
```

**Response:**
```json
{
  "comparison": {
    "companies": [
      {
        "domain": "finastra.com",
        "company_name": "Finastra",
        "landscapes": {
          "Payments": {
            "dsi_score": 15.67,
            "rank": 1,
            "market_position": "leader"
          },
          "Universal Banking": {
            "dsi_score": 8.23,
            "rank": 5,
            "market_position": "challenger"
          }
        },
        "overall_performance": {
          "avg_dsi": 11.95,
          "best_rank": 1,
          "landscapes_leading": 1,
          "total_traffic": 234000
        }
      }
    ],
    "market_insights": {
      "most_competitive_landscape": "Payments",
      "avg_market_concentration": 0.23,
      "emerging_players": ["newcomer.com"]
    }
  }
}
```

---

## Authentication Integration

### JWT Token Structure

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@company.com",
  "permissions": {
    "landscapes": ["all"] | ["4e773f12-12b7-4118-b859-faadc0abc60b"],
    "access_level": "read" | "full",
    "features": ["export", "alerts", "competitive_intel"]
  },
  "client_id": "finastra",
  "exp": 1705123456
}
```

### Permission Middleware

```python
from functools import wraps

def require_landscape_access(landscape_id: str = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = get_current_user()
            if landscape_id and not user.has_landscape_access(landscape_id):
                raise HTTPException(403, "Insufficient landscape permissions")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Usage
@router.get("/landscapes/{landscape_id}/overview")
@require_landscape_access()
async def get_landscape_overview(landscape_id: str, user=Depends(get_current_user)):
    # Implementation
    pass
```

---

## Data Access Patterns

### Optimized Query Patterns

**1. Dashboard Home Page** (Landscape Grid):
```sql
-- Single query for landscape overview grid
SELECT 
    dl.id, dl.name, dl.business_unit, dl.region,
    COUNT(CASE WHEN ldm.entity_type = 'company' THEN 1 END) as company_count,
    AVG(CASE WHEN ldm.entity_type = 'company' THEN ldm.dsi_score END) as avg_company_dsi,
    MAX(CASE WHEN ldm.entity_type = 'company' THEN ldm.dsi_score END) as top_company_dsi,
    SUM(CASE WHEN ldm.entity_type = 'company' THEN ldm.estimated_traffic END) as total_traffic
FROM digital_landscapes dl
LEFT JOIN landscape_dsi_metrics ldm ON dl.id = ldm.landscape_id 
    AND ldm.calculation_date = CURRENT_DATE
WHERE dl.is_active = true
GROUP BY dl.id, dl.name, dl.business_unit, dl.region
ORDER BY total_traffic DESC;
```

**2. Company Rankings** (Paginated):
```sql
-- Efficient company rankings with pagination
SELECT 
    ldm.entity_name as company_name,
    ldm.entity_domain as domain,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.market_position,
    ldm.estimated_traffic,
    cp.industry,
    cp.employee_count
FROM landscape_dsi_metrics ldm
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain
WHERE ldm.landscape_id = $1
AND ldm.entity_type = 'company'  
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.rank_in_landscape
LIMIT $2 OFFSET $3;
```

**3. Time Series Data**:
```sql
-- Company performance trends
SELECT 
    calculation_date,
    dsi_score,
    rank_in_landscape,
    estimated_traffic,
    market_position
FROM landscape_dsi_metrics
WHERE entity_domain = $1
AND entity_type = 'company'
AND landscape_id = $2
AND calculation_date >= CURRENT_DATE - INTERVAL $3
ORDER BY calculation_date DESC;
```

---

## Caching Strategy

### Redis Cache Structure

```python
# Cache key patterns
CACHE_KEYS = {
    'landscape_overview': 'dash:landscape:{landscape_id}:{date}',
    'company_rankings': 'dash:companies:{landscape_id}:{date}:{page}',
    'company_profile': 'dash:company:{domain}',
    'keyword_performance': 'dash:keywords:{landscape_id}:{date}',
    'competitive_data': 'dash:competitive:{company_domains_hash}:{date}'
}

# TTL settings
CACHE_TTL = {
    'landscape_overview': 3600,    # 1 hour
    'company_rankings': 1800,      # 30 minutes
    'company_profile': 86400,      # 24 hours
    'keyword_performance': 3600,   # 1 hour
    'competitive_data': 1800       # 30 minutes
}
```

### Cache Invalidation

```python
# Invalidate on new DSI calculations
async def invalidate_landscape_cache(landscape_id: str, calculation_date: str):
    patterns = [
        f'dash:landscape:{landscape_id}:*',
        f'dash:companies:{landscape_id}:*', 
        f'dash:keywords:{landscape_id}:*'
    ]
    for pattern in patterns:
        await redis.delete_pattern(pattern)
```

---

## Real-time Features

### WebSocket Integration

**Connection Pattern:**
```javascript
// Client-side WebSocket connection
const ws = new WebSocket('ws://localhost:8002/ws/landscape/{landscape_id}');

ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    if (update.type === 'dsi_update') {
        updateDashboard(update.data);
    }
};
```

**Server-side Broadcasting:**
```python
# Broadcast DSI updates to connected clients
async def broadcast_dsi_update(landscape_id: str, update_data: dict):
    await websocket_manager.broadcast_to_landscape(
        landscape_id, 
        {
            "type": "dsi_update",
            "data": update_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

---

## Dashboard Component Data Requirements

### 1. Landscape Overview Cards

**Data Needed:**
```sql
SELECT 
    name, business_unit, region,
    COUNT(CASE WHEN entity_type = 'company' THEN 1 END) as companies,
    MAX(CASE WHEN entity_type = 'company' THEN dsi_score END) as top_dsi,
    SUM(CASE WHEN entity_type = 'company' THEN estimated_traffic END) as traffic
FROM digital_landscapes dl
JOIN landscape_dsi_metrics ldm ON dl.id = ldm.landscape_id
WHERE calculation_date = CURRENT_DATE
GROUP BY dl.id, name, business_unit, region;
```

### 2. Company Rankings Table

**Required Fields:**
- Rank, Company Name, Domain, DSI Score, Market Position
- Industry, Employee Count, Keyword Count, Traffic Share
- Trend indicators (up/down/stable)

### 3. Competitive Positioning Chart

**Data Structure:**
```json
{
  "chart_data": {
    "x_axis": "keyword_coverage_pct",
    "y_axis": "traffic_share_pct", 
    "bubble_size": "dsi_score",
    "companies": [
      {
        "name": "Finastra",
        "x": 43.7,
        "y": 5.2,
        "size": 15.67,
        "position": "leader",
        "industry": "Financial Services"
      }
    ]
  },
  "quadrant_analysis": {
    "leaders": {"count": 12, "avg_dsi": 18.5},
    "challengers": {"count": 48, "avg_dsi": 8.2},
    "competitors": {"count": 98, "avg_dsi": 3.1},
    "niche": {"count": 80, "avg_dsi": 0.8}
  }
}
```

### 4. Keyword Performance Heatmap

**Data Query:**
```sql
SELECT 
    k.keyword,
    k.category,
    k.avg_monthly_searches,
    k.competition_level,
    ldm.dsi_score as keyword_dsi,
    ldm.rank_in_landscape,
    COUNT(DISTINCT sr.domain) as competing_domains
FROM landscape_dsi_metrics ldm
JOIN keywords k ON ldm.entity_id::text = k.id::text
LEFT JOIN serp_results sr ON k.id = sr.keyword_id
WHERE ldm.landscape_id = $1
AND ldm.entity_type = 'keyword'
AND ldm.calculation_date = CURRENT_DATE
GROUP BY k.keyword, k.category, k.avg_monthly_searches, k.competition_level, ldm.dsi_score, ldm.rank_in_landscape
ORDER BY ldm.rank_in_landscape;
```

---

## Error Handling

### Standard Error Responses

```json
{
  "error": {
    "code": "LANDSCAPE_NOT_FOUND",
    "message": "Landscape with ID {id} not found",
    "details": {
      "landscape_id": "invalid-uuid",
      "available_landscapes": [...]
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `LANDSCAPE_NOT_FOUND` | 404 | Landscape ID doesn't exist |
| `COMPANY_NOT_FOUND` | 404 | Company domain not found |
| `INSUFFICIENT_PERMISSIONS` | 403 | User lacks landscape access |
| `INVALID_DATE_RANGE` | 400 | Invalid date parameters |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `DSI_DATA_UNAVAILABLE` | 503 | DSI calculation in progress |

---

## Docker Integration

### Dockerfile Template

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

### Docker Compose Integration

```yaml
services:
  dashboard:
    build: ./dashboard
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=postgresql://readonly_user:password@postgres:5432/cylvy_analyze
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    depends_on:
      - postgres
      - redis
    networks:
      - cylvy-network
    restart: unless-stopped
```

---

## Performance Benchmarks

### Expected Query Performance

| Query Type | Expected Response Time | Cache Hit Rate |
|------------|------------------------|----------------|
| Landscape Overview | < 200ms | 90% |
| Company Rankings (50 items) | < 300ms | 85% |
| Company Deep Dive | < 400ms | 80% |
| Keyword Analysis | < 500ms | 75% |
| Competitive Comparison | < 800ms | 70% |

### Scaling Considerations

- **Database**: Read replicas for dashboard queries
- **Caching**: Redis cluster for high availability
- **API**: Horizontal scaling with load balancer
- **WebSockets**: Redis pub/sub for multi-instance broadcasting

---

This specification provides all the technical details needed to develop high-performance, feature-rich digital landscape dashboards that leverage the comprehensive DSI data system.
