# 📡 API Endpoints Documentation

## 🎯 **Overview**

Complete API documentation for the Cylvy Market Intelligence Agent backend. All endpoints require authentication except `/health` and `/auth/login`. Base URL: `http://localhost:8001/api/v1`

---

## 🔐 **Authentication Endpoints**

### **POST `/auth/login`**
Authenticate user and receive JWT access token.

**Request:**
```json
{
  "email": "admin@cylvy.com",
  "password": "admin123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "3b2a96b7-c37c-4ae9-9a8a-f7facc70da4d",
    "email": "admin@cylvy.com",
    "full_name": "Default Admin",
    "role": "superadmin",
    "is_active": true,
    "last_login": "2025-09-03T09:44:15.811058Z",
    "created_at": "2025-09-02T09:34:42.872176Z"
  }
}
```

### **GET `/auth/me`**
Get current user information.

**Headers:** `Authorization: Bearer {token}`

**Response (200):**
```json
{
  "id": "3b2a96b7-c37c-4ae9-9a8a-f7facc70da4d", 
  "email": "admin@cylvy.com",
  "full_name": "Default Admin",
  "role": "superadmin"
}
```

---

## ⚙️ **Configuration Endpoints**

### **GET `/config`**
Get client configuration details.

**Headers:** `Authorization: Bearer {token}`

**Response (200):**
```json
{
  "id": "aa3dcc46-e0da-4e15-98ec-77e126c84fdd",
  "company_name": "Finastra",
  "company_domain": "finastra.com", 
  "admin_email": "adrian@silver.agency",
  "support_email": null,
  "description": "Leading financial services software provider",
  "industry": "Financial Services Software",
  "company_logo_url": "/storage/logos/logo_abc123.png",
  "primary_color": "#E51848",
  "secondary_color": "#880CBF",
  "created_at": "2025-09-02T09:34:42.872176Z",
  "updated_at": "2025-09-03T10:15:22.445231Z"
}
```

### **PUT `/config`** 
Update client configuration.

**Headers:** `Authorization: Bearer {token}`, `Content-Type: application/json`

**Request:**
```json
{
  "company_name": "Finastra",
  "company_domain": "finastra.com",
  "admin_email": "adrian@silver.agency", 
  "description": "Leading financial services software provider",
  "industry": "Financial Services Software"
}
```

**Response (200):**
```json
{
  "message": "Configuration updated successfully",
  "updated_fields": ["description", "industry"]
}
```

### **POST `/config/logo`**
Upload company logo.

**Headers:** `Authorization: Bearer {token}`  
**Content-Type:** `multipart/form-data`

**Request:**
```
file: [PNG/JPG/SVG file up to 5MB]
```

**Response (200):**
```json
{
  "message": "Logo uploaded successfully",
  "logo_url": "/storage/logos/logo_abc123.png"
}
```

### **GET `/config/setup-status`**
Get setup completion status.

**Response (200):**
```json
{
  "setup_complete": true,
  "steps_completed": {
    "company_info": true,
    "branding": true,
    "api_keys": false,
    "personas": true,
    "jtbd_phases": true
  },
  "company_name": "Finastra",
  "company_domain": "finastra.com"
}
```

---

## 📊 **Keywords Endpoints**

### **GET `/keywords`**
Get all keywords with pagination.

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**
- `limit` (int, default: 50): Maximum number of keywords
- `offset` (int, default: 0): Pagination offset
- `search` (string, optional): Search term filter
- `category` (string, optional): Category filter

**Response (200):**
```json
{
  "keywords": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "keyword": "digital banking",
      "category": "Financial Technology",
      "jtbd_stage": "Consideration",
      "client_score": 85.5,
      "persona_score": 91.2,
      "seo_score": 78.8,
      "composite_score": 85.2,
      "avg_monthly_searches": 5400,
      "competition_level": "MEDIUM",
      "is_brand": false,
      "created_at": "2025-09-02T14:22:15.123Z",
      "updated_at": "2025-09-03T10:15:44.567Z"
    }
  ],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

### **POST `/keywords/upload`**
Upload keywords from CSV file.

**Headers:** `Authorization: Bearer {token}`  
**Content-Type:** `multipart/form-data`

**Request:**
```
file: [CSV file with keywords]
regions: "US,UK,DE,SA,VN"
```

**Response (200):**
```json
{
  "total_keywords": 15,
  "keywords_processed": 15,
  "metrics_fetched": 0,
  "csv_parsing_errors": 0,
  "database_errors": 0,
  "errors": []
}
```

**Error Response (422):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "CSV validation failed",
    "details": [
      "Row 3: Missing required keyword field",
      "Row 7: Invalid score value (must be 0-100)"
    ]
  }
}
```

### **GET `/keywords/categories`**
Get available keyword categories.

**Response (200):**
```json
{
  "categories": [
    "Financial Technology",
    "API Technology", 
    "Solutions",
    "Banking Software",
    "Payment Processing"
  ]
}
```

---

## 🚀 **Pipeline Endpoints**

### **POST `/pipeline/start`**
Start new analysis pipeline execution.

**Headers:** `Authorization: Bearer {token}`, `Content-Type: application/json`

**Request:**
```json
{
  "collect_serp": true,
  "enrich_companies": true,
  "scrape_content": false,
  "analyze_content": false,
  "enable_landscape_dsi": true
}
```

**Response (200):**
```json
{
  "pipeline_id": "f9c7c5aa-bfc9-4819-9cef-eda5cfdf6f09",
  "message": "Pipeline started successfully", 
  "status": "pending"
}
```

### **GET `/pipeline/recent`**
Get recent pipeline executions.

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**
- `limit` (int, default: 10): Number of recent pipelines

**Response (200):**
```json
{
  "pipelines": [
    {
      "pipeline_id": "f9c7c5aa-bfc9-4819-9cef-eda5cfdf6f09",
      "status": "completed",
      "mode": "manual",
      "started_at": "2025-09-03T10:04:41.071070+00:00",
      "completed_at": "2025-09-03T10:04:41.191603+00:00", 
      "duration_seconds": 0.12,
      "keywords_processed": 15,
      "serp_results_collected": 0,
      "companies_enriched": 0,
      "content_analyzed": 0,
      "landscapes_calculated": 0,
      "errors_count": 0,
      "warnings_count": 0
    }
  ]
}
```

### **GET `/pipeline/status/{pipeline_id}`**
Get specific pipeline execution status.

**Headers:** `Authorization: Bearer {token}`

**Response (200):**
```json
{
  "pipeline_id": "f9c7c5aa-bfc9-4819-9cef-eda5cfdf6f09",
  "status": "running",
  "mode": "batch_optimized",
  "started_at": "2025-09-03T10:04:41.071070+00:00",
  "current_phase": "serp_collection",
  "phases_completed": ["keyword_metrics_enrichment"],
  "phases_remaining": ["serp_collection", "company_enrichment", "dsi_calculation"],
  "progress_percentage": 25,
  "keywords_processed": 15,
  "serp_results_collected": 45,
  "estimated_completion": "2025-09-03T10:15:00.000Z",
  "errors": [],
  "warnings": []
}
```

### **WebSocket `/ws/pipeline`**
Real-time pipeline status updates.

**Connection:** `ws://localhost:8001/ws/pipeline`

**Message Format:**
```json
{
  "type": "pipeline_update",
  "pipeline_id": "f9c7c5aa-bfc9-4819-9cef-eda5cfdf6f09",
  "timestamp": "2025-09-03T10:05:15.234Z",
  "data": {
    "status": "running",
    "current_phase": "company_enrichment", 
    "phase_completed": "serp_collection",
    "progress": {
      "keywords_processed": 15,
      "serp_results_collected": 150,
      "companies_enriched": 8
    }
  }
}
```

---

## 🌍 **Digital Landscapes Endpoints**

### **GET `/landscapes`**
Get all digital landscapes.

**Headers:** `Authorization: Bearer {token}`

**Response (200):**
```json
[
  {
    "id": "456e7890-e12b-34d5-a678-426614174111",
    "name": "UK Banking Technology",
    "description": "Digital banking and fintech landscape for UK market",
    "is_active": true,
    "keyword_count": 25,
    "last_calculation": "2025-09-03T09:30:00Z",
    "created_at": "2025-09-02T15:22:10Z"
  }
]
```

### **POST `/landscapes`**
Create new digital landscape.

**Headers:** `Authorization: Bearer {token}`, `Content-Type: application/json`

**Request:**
```json
{
  "name": "UK Banking Technology",
  "description": "Digital banking and fintech competitive landscape for UK market analysis"
}
```

**Response (201):**
```json
{
  "landscape_id": "456e7890-e12b-34d5-a678-426614174111",
  "message": "Landscape created successfully"
}
```

### **GET `/landscapes/keywords/available`**
Get keywords available for landscape assignment.

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**
- `search` (string, optional): Search term filter
- `limit` (int, default: 100): Maximum results

**Response (200):**
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "keyword": "digital banking",
    "search_volume": 5400,
    "competition_level": "MEDIUM"
  },
  {
    "id": "789e0123-e89b-45d6-a789-426614174222", 
    "keyword": "open banking API",
    "search_volume": 1200,
    "competition_level": "LOW"
  }
]
```

### **POST `/landscapes/{landscape_id}/keywords`**
Assign keywords to landscape.

**Headers:** `Authorization: Bearer {token}`, `Content-Type: application/json`

**Request:**
```json
{
  "keyword_ids": [
    "123e4567-e89b-12d3-a456-426614174000",
    "789e0123-e89b-45d6-a789-426614174222"
  ]
}
```

**Response (200):**
```json
{
  "message": "Keywords assigned successfully",
  "assigned_count": 2,
  "landscape_id": "456e7890-e12b-34d5-a678-426614174111"
}
```

### **POST `/landscapes/{landscape_id}/calculate`**
Trigger DSI calculation for landscape.

**Headers:** `Authorization: Bearer {token}`

**Response (202):**
```json
{
  "message": "DSI calculation started", 
  "calculation_id": "calc_abc123",
  "estimated_duration_minutes": 5,
  "landscape_id": "456e7890-e12b-34d5-a678-426614174111"
}
```

### **GET `/landscapes/{landscape_id}/metrics`**
Get calculated DSI metrics for landscape.

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**
- `calculation_date` (date, optional): Specific calculation date
- `entity_type` (enum): 'company' or 'page'
- `limit` (int, default: 50): Maximum results

**Response (200):**
```json
{
  "landscape_id": "456e7890-e12b-34d5-a678-426614174111",
  "calculation_date": "2025-09-03",
  "total_entities": 12,
  "entities": [
    {
      "entity_id": "comp_123",
      "entity_name": "Finastra",
      "entity_domain": "finastra.com", 
      "dsi_score": 78.5,
      "rank": 1,
      "market_position": "LEADER",
      "traffic_share": 18.2,
      "keyword_coverage": 0.72,
      "unique_keywords": 18,
      "estimated_traffic": 125000,
      "persona_alignment": 0.85,
      "funnel_value": 0.91
    },
    {
      "entity_id": "comp_456", 
      "entity_name": "Temenos",
      "entity_domain": "temenos.com",
      "dsi_score": 72.1,
      "rank": 2,
      "market_position": "CHALLENGER",
      "traffic_share": 15.8,
      "keyword_coverage": 0.68,
      "unique_keywords": 17,
      "estimated_traffic": 108000,
      "persona_alignment": 0.79,
      "funnel_value": 0.88
    }
  ]
}
```

### **GET `/landscapes/{landscape_id}/summary`**
Get landscape performance summary with trends.

**Response (200):**
```json
{
  "landscape_id": "456e7890-e12b-34d5-a678-426614174111",
  "name": "UK Banking Technology",
  "calculation_date": "2025-09-03",
  "summary": {
    "total_companies": 12,
    "total_keywords": 25,
    "avg_dsi_score": 67.5,
    "market_concentration": "moderate",
    "top_performers": ["Finastra", "Temenos", "FIS Global"]
  },
  "trends": {
    "dsi_change_30d": +5.2,
    "traffic_change_30d": +12.8,
    "market_position_changes": 2,
    "keyword_expansion": +3
  }
}
```

---

## 👥 **Analysis Configuration Endpoints**

### **GET `/analysis/personas`**
Get configured personas.

**Headers:** `Authorization: Bearer {token}`

**Response (200):**
```json
{
  "personas": [
    {
      "name": "The Payments Innovator",
      "description": "Mission: Modernize payments infrastructure while preserving compliance and operational stability...",
      "title": "Head of Payments, VP of Transaction Banking",
      "goals": [
        "Scalability improvement",
        "Interoperability enhancement", 
        "Operational resilience"
      ],
      "pain_points": [
        "Legacy system integration",
        "Regulatory compliance complexity",
        "Real-time processing demands"
      ],
      "decision_criteria": [
        "Proven scalability",
        "Regulatory compliance",
        "Integration capabilities"
      ]
    }
  ]
}
```

### **PUT `/analysis/personas`**
Update personas configuration.

**Headers:** `Authorization: Bearer {token}`, `Content-Type: application/json`

**Request:**
```json
{
  "personas": [
    {
      "name": "The Payments Innovator",
      "description": "Updated description...",
      "goals": ["Goal 1", "Goal 2"],
      "pain_points": ["Pain 1", "Pain 2"],
      "decision_criteria": ["Criteria 1", "Criteria 2"]
    }
  ]
}
```

**Response (200):**
```json
{
  "message": "Personas updated successfully"
}
```

### **GET `/analysis/jtbd`**
Get JTBD phases configuration.

**Response (200):**
```json
{
  "phases": [
    {
      "name": "Awareness",
      "description": "Customer becomes aware of the problem",
      "buyer_mindset": "Problem identification",
      "key_questions": [
        "What challenges do we face?",
        "How are others solving this?"
      ],
      "content_types": [
        "Educational content",
        "Industry reports",
        "Thought leadership"
      ]
    }
  ]
}
```

### **PUT `/analysis/jtbd`**
Update JTBD phases configuration.

**Request:**
```json
{
  "phases": [
    {
      "name": "Awareness",
      "description": "Customer becomes aware of the problem",
      "buyer_mindset": "Problem identification"
    }
  ]
}
```

### **GET `/analysis/competitors`**
Get competitor domains configuration.

**Response (200):**
```json
{
  "competitor_domains": [
    "temenos.com",
    "fisglobal.com", 
    "fiserv.com",
    "ncino.com"
  ]
}
```

---

## 📈 **Historical Metrics Endpoints**

### **GET `/historical-metrics/summary`**
Get historical metrics summary.

**Query Parameters:**
- `country_code` (string, optional): Filter by country
- `months` (int, default: 12): Time period for analysis

**Response (200):**
```json
{
  "summary": {
    "unique_keywords": 15,
    "countries_tracked": 5,
    "pipeline_runs": 3,
    "google_ads_metrics": 75,
    "serp_metrics": 150,
    "avg_search_volume": 3420.5,
    "high_competition_count": 8,
    "latest_snapshot": "2025-09-03"
  },
  "time_period": "12 months"
}
```

### **GET `/historical-metrics/keywords/trends/{keyword_id}`**
Get trend analysis for specific keyword.

**Query Parameters:**
- `country_code` (string, optional): Filter by country
- `months` (int, default: 12): Trend period

**Response (200):**
```json
{
  "keyword_id": "123e4567-e89b-12d3-a456-426614174000",
  "keyword_text": "digital banking",
  "trends": [
    {
      "snapshot_date": "2025-02-01",
      "country_code": "US",
      "avg_monthly_searches": 5200,
      "competition_level": "MEDIUM",
      "avg_cpc_usd": 2.45
    },
    {
      "snapshot_date": "2025-03-01", 
      "country_code": "US",
      "avg_monthly_searches": 5400,
      "competition_level": "MEDIUM",
      "avg_cpc_usd": 2.52
    }
  ],
  "trend_analysis": {
    "search_volume_trend": "increasing",
    "competition_trend": "stable", 
    "avg_growth_rate": 3.8
  }
}
```

### **GET `/historical-metrics/landscapes/performance`**
Get landscape performance trends.

**Query Parameters:**
- `landscape_id` (string): Landscape identifier
- `entity_id` (string, optional): Specific company/entity
- `months` (int, default: 6): Analysis period

**Response (200):**
```json
{
  "landscape_id": "456e7890-e12b-34d5-a678-426614174111",
  "entity_name": "Finastra",
  "performance_trends": [
    {
      "month": "2025-01",
      "dsi_score": 76.2,
      "rank": 1,
      "traffic_share": 17.5,
      "keyword_coverage": 0.68
    },
    {
      "month": "2025-02",
      "dsi_score": 77.8,
      "rank": 1, 
      "traffic_share": 18.1,
      "keyword_coverage": 0.71
    }
  ],
  "performance_summary": {
    "dsi_trend": "increasing",
    "rank_stability": "stable",
    "traffic_growth_rate": "+3.4%",
    "keyword_expansion_rate": "+4.4%"
  }
}
```

---

## 🎯 **Custom Dimensions Endpoints**

### **GET `/generic-dimensions`**
Get all custom dimensions.

**Headers:** `Authorization: Bearer {token}`

**Response (200):**
```json
{
  "dimensions": [
    {
      "id": "dim_123",
      "name": "Technology Innovation",
      "description": "Evaluation of technological advancement and innovation capabilities",
      "category": "Strategic Pillars",
      "scoring_levels": [
        {
          "level": 1,
          "label": "Traditional",
          "description": "Legacy technology with minimal innovation"
        },
        {
          "level": 10,
          "label": "Cutting Edge",
          "description": "Industry-leading innovation and technology adoption"
        }
      ],
      "is_active": true,
      "created_at": "2025-09-02T16:45:22Z"
    }
  ]
}
```

### **POST `/generic-dimensions`**
Create new custom dimension.

**Request:**
```json
{
  "name": "Technology Innovation",
  "description": "Evaluation of technological advancement",
  "category": "Strategic Pillars", 
  "scoring_levels": [
    {
      "level": 1,
      "label": "Traditional",
      "description": "Legacy technology approach"
    }
  ]
}
```

### **GET `/generic-dimensions/templates`**
Get predefined dimension templates.

**Response (200):**
```json
{
  "templates": [
    {
      "name": "Finastra Strategic Pillars",
      "description": "Strategic evaluation framework for financial services",
      "dimensions": [
        {
          "name": "Technology Innovation",
          "scoring_levels": [...]
        },
        {
          "name": "Market Leadership", 
          "scoring_levels": [...]
        }
      ]
    }
  ]
}
```

---

## 📊 **Error Response Formats**

### **Standard Error Response:**
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "type": "error_type",
    "details": ["Additional context", "Field-specific errors"]
  }
}
```

### **Common Error Codes:**
```
400 - VALIDATION_ERROR: Request validation failed
401 - AUTH_ERROR: Authentication required or invalid token
403 - FORBIDDEN: Insufficient permissions  
404 - NOT_FOUND: Resource not found
422 - UNPROCESSABLE_ENTITY: Business logic validation failed
500 - INTERNAL_ERROR: Unexpected server error
```

### **Authentication Errors:**
```json
// 401 Unauthorized
{
  "error": {
    "code": "AUTH_ERROR",
    "message": "Invalid token",
    "type": "authentication_error"
  }
}

// 403 Forbidden  
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Admin access required",
    "type": "authorization_error"
  }
}
```

### **Validation Errors:**
```json
// 422 Unprocessable Entity
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "type": "missing",
        "loc": ["body", "phases", 0, "name"],
        "msg": "Field required",
        "input": {"phase": "Awareness", "description": "..."}
      }
    ],
    "type": "validation_error"
  }
}
```

---

## 🔄 **Rate Limiting & Usage Quotas**

### **API Rate Limits:**
```
Authentication Endpoints: 5 requests/minute
Configuration Endpoints: 60 requests/minute  
Keywords Endpoints: 30 requests/minute
Pipeline Endpoints: 10 requests/minute
Landscape Endpoints: 20 requests/minute
Historical Metrics: 100 requests/minute
```

### **Usage Quotas:**
```
CSV Upload: 10 files/hour, max 1000 keywords/file
Logo Upload: 5 uploads/hour, max 5MB/file
Pipeline Executions: 10 executions/hour
DSI Calculations: 20 calculations/hour
```

---

## 📚 **Interactive API Documentation**

### **Swagger/OpenAPI Documentation:**
- **URL:** http://localhost:8001/docs
- **Interactive Testing:** Try endpoints directly in browser
- **Schema Exploration:** Complete request/response models
- **Authentication:** Built-in token testing interface

### **API Client Examples:**

#### **JavaScript/TypeScript (Frontend):**
```typescript
// Centralized API client
class CylvyAPI {
  private baseURL = '/api/v1';
  private token = localStorage.getItem('access_token');
  
  async request(endpoint: string, options: RequestInit = {}) {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    
    if (!response.ok) {
      throw new APIError(response.status, await response.json());
    }
    
    return await response.json();
  }
  
  // Pipeline management
  async startPipeline(config: PipelineConfig) {
    return this.request('/pipeline/start', {
      method: 'POST',
      body: JSON.stringify(config)
    });
  }
  
  // Landscape management
  async createLandscape(landscape: LandscapeData) {
    return this.request('/landscapes', {
      method: 'POST', 
      body: JSON.stringify(landscape)
    });
  }
}
```

#### **Python (Testing/Automation):**
```python
import requests

class CylvyAPIClient:
    def __init__(self, base_url="http://localhost:8001/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def login(self, email: str, password: str):
        response = self.session.post(f"{self.base_url}/auth/login", json={
            "email": email,
            "password": password
        })
        token = response.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def start_pipeline(self, config: dict):
        return self.session.post(f"{self.base_url}/pipeline/start", json=config)
    
    def get_landscapes(self):
        return self.session.get(f"{self.base_url}/landscapes")

# Usage example
client = CylvyAPIClient()
client.login("admin@cylvy.com", "admin123")
pipeline = client.start_pipeline({
    "collect_serp": True,
    "enrich_companies": True
})
```

---

## ⚡ **Performance Considerations**

### **Response Time Targets:**
```
Authentication: < 200ms
Configuration: < 500ms
Keywords List: < 800ms
Pipeline Start: < 1000ms
Landscape Calculation: < 30 seconds
Trend Analysis: < 2000ms (TimescaleDB optimized)
```

### **Caching Strategy:**
```python
# Redis caching for frequently accessed data
@cache(expire=300)  # 5 minute cache
async def get_landscape_summary(landscape_id: str):
    """Cached landscape summary for performance"""
    return await generate_landscape_summary(landscape_id)

# Cache invalidation on data updates
async def update_landscape(landscape_id: str, updates: dict):
    await update_landscape_data(landscape_id, updates)
    await cache.delete(f"landscape_summary:{landscape_id}")
```

### **Pagination Strategy:**
```python
# Consistent pagination across all list endpoints
class PaginationParams:
    limit: int = Query(50, ge=1, le=500)
    offset: int = Query(0, ge=0)
    
# Standard pagination response
{
  "items": [...],
  "pagination": {
    "total": 1205,
    "limit": 50, 
    "offset": 100,
    "has_more": true,
    "next_offset": 150
  }
}
```

---

This comprehensive API documentation provides complete integration specifications for frontend development, testing automation, and third-party integrations with the Cylvy Market Intelligence Agent platform.
