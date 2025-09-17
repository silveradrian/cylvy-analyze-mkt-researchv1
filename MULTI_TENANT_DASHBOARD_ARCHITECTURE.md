# Multi-Tenant Digital Landscape Dashboard Architecture

## Overview

The Digital Landscape Dashboard is designed as a **client-agnostic, multi-tenant SaaS platform** that serves multiple clients, each with their own unique configurations, custom metrics, personas, and branding. Each client gets their own isolated data views while sharing the underlying infrastructure.

---

## Multi-Tenant Architecture Principles

### 1. **Data Isolation Strategy**

**Logical Separation**: All data tables include `client_id` for tenant isolation
**Configuration Isolation**: Each client has custom landscapes, metrics, and personas  
**Brand Isolation**: Client-specific logos and styling (no white-labeling beyond logo)
**Permission Isolation**: Role-based access control per client tenant

### 2. **Client Variability**

Each client can have completely different:
- **Digital Landscapes** (e.g., "Core Banking" vs "Retail Banking" vs "Wealth Management")
- **Keyword Sets** (different market focus and terminology)
- **Persona Definitions** (CTO, Product Manager, Business Analyst with custom weights)
- **DSI Calculation Formulas** (custom component weights and thresholds)
- **Market Position Thresholds** (different definitions of "leader" vs "challenger")

---

## Client Configuration Examples

### Example Client A: "Financial Technology Vendor"

```json
{
  "client_id": "fintech_vendor_a",
  "landscapes": [
    {
      "name": "Core Banking Platforms",
      "keywords": ["core banking", "digital banking platform", "bank modernization"],
      "custom_weightings": {
        "technical_content": 0.6,
        "market_presence": 0.4
      }
    },
    {
      "name": "Payment Solutions", 
      "keywords": ["payment processing", "digital wallets", "instant payments"],
      "custom_weightings": {
        "innovation_score": 0.5,
        "market_share": 0.5
      }
    }
  ],
  "personas": [
    {
      "name": "Bank CTO",
      "weights": {
        "technical_depth": 0.8,
        "business_impact": 0.2
      }
    },
    {
      "name": "Product Manager",
      "weights": {
        "market_trends": 0.6,
        "competitive_analysis": 0.4
      }
    }
  ],
  "dsi_formula": {
    "components": {
      "keyword_coverage": 0.3,
      "traffic_share": 0.4, 
      "persona_alignment": 0.3
    },
    "thresholds": {
      "leader": 15.0,
      "challenger": 8.0,
      "competitor": 3.0
    }
  }
}
```

### Example Client B: "Banking Consultancy"

```json
{
  "client_id": "banking_consultancy_b",
  "landscapes": [
    {
      "name": "Digital Transformation",
      "keywords": ["digital transformation banking", "cloud banking", "API banking"],
      "region_focus": "EMEA"
    },
    {
      "name": "Regulatory Technology",
      "keywords": ["regtech", "compliance automation", "risk management"],
      "custom_weightings": {
        "regulatory_relevance": 0.7,
        "technology_maturity": 0.3
      }
    }
  ],
  "personas": [
    {
      "name": "Chief Risk Officer",
      "weights": {
        "compliance_focus": 0.9,
        "technology_focus": 0.1
      }
    },
    {
      "name": "Digital Strategy Lead",
      "weights": {
        "innovation_potential": 0.6,
        "implementation_feasibility": 0.4
      }
    }
  ],
  "dsi_formula": {
    "components": {
      "thought_leadership": 0.4,
      "market_presence": 0.3,
      "content_authority": 0.3
    }
  }
}
```

---

## Database Schema Changes for Multi-Tenancy

### Required Schema Updates

```sql
-- Add client_id to existing tables
ALTER TABLE landscape_dsi_metrics ADD COLUMN client_id VARCHAR NOT NULL DEFAULT 'default';
ALTER TABLE digital_landscapes ADD COLUMN client_id VARCHAR NOT NULL DEFAULT 'default';

-- Update unique constraints for multi-tenancy
ALTER TABLE landscape_dsi_metrics 
DROP CONSTRAINT IF EXISTS landscape_dsi_metrics_unique,
ADD CONSTRAINT landscape_dsi_metrics_unique 
UNIQUE (client_id, landscape_id, calculation_date, entity_type, entity_id);

-- Create indexes for client isolation
CREATE INDEX idx_landscape_dsi_client_isolation 
ON landscape_dsi_metrics (client_id, calculation_date, entity_type);

CREATE INDEX idx_client_landscapes_lookup
ON client_landscapes (client_id, is_active, display_order);
```

### Migration Strategy

```sql
-- Migration script for existing data
-- 1. Identify current client (e.g., "finastra") 
UPDATE landscape_dsi_metrics SET client_id = 'finastra';
UPDATE digital_landscapes SET client_id = 'finastra';

-- 2. Create client configuration
INSERT INTO clients (id, name, industry_focus, is_active, subscription_tier)
VALUES ('finastra', 'Finastra', 'Financial Services', true, 'enterprise');

-- 3. Migrate landscape definitions to client_landscapes
INSERT INTO client_landscapes (
    id, client_id, landscape_name, business_unit, region, 
    description, is_active, display_order
)
SELECT 
    id, 'finastra', name, 'Financial Services', region,
    description, is_active, ROW_NUMBER() OVER (ORDER BY name)
FROM digital_landscapes;
```

---

## Multi-Tenant Query Patterns

### 1. Client Landscape Overview

```sql
-- Always filter by client_id first for tenant isolation
SELECT 
    cl.id as landscape_id,
    cl.landscape_name,
    cl.business_unit,
    cl.region,
    COUNT(CASE WHEN ldm.entity_type = 'company' THEN 1 END) as companies,
    AVG(CASE WHEN ldm.entity_type = 'company' THEN ldm.dsi_score END) as avg_dsi,
    MAX(CASE WHEN ldm.entity_type = 'company' THEN ldm.dsi_score END) as top_dsi
FROM client_landscapes cl
LEFT JOIN landscape_dsi_metrics ldm ON cl.id = ldm.landscape_id 
    AND ldm.client_id = cl.client_id
    AND ldm.calculation_date = CURRENT_DATE
WHERE cl.client_id = $1                     -- Client isolation
AND cl.is_active = true
GROUP BY cl.id, cl.landscape_name, cl.business_unit, cl.region, cl.display_order
ORDER BY cl.display_order;
```

### 2. Client-Specific Company Rankings

```sql
-- Company rankings with client-specific DSI calculations
SELECT 
    ldm.entity_name as company_name,
    ldm.entity_domain as domain,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.market_position,
    -- Apply client-specific thresholds for market position
    CASE 
        WHEN ldm.dsi_score >= cm.threshold_leader THEN 'leader'
        WHEN ldm.dsi_score >= cm.threshold_challenger THEN 'challenger'  
        WHEN ldm.dsi_score >= cm.threshold_competitor THEN 'competitor'
        ELSE 'niche'
    END as custom_market_position,
    cp.industry
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
JOIN client_metrics cm ON cl.client_id = cm.client_id AND cm.metric_name = 'company_dsi'
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain
WHERE ldm.client_id = $1                    -- Client isolation
AND cl.landscape_name = $2                   -- Client's landscape
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.rank_in_landscape
LIMIT $3;
```

### 3. Persona-Specific Content Analysis

```sql
-- Content analysis with client-specific persona weighting
SELECT 
    ldm.entity_name as page_title,
    ldm.entity_url as url,
    ldm.entity_domain as domain,
    ldm.dsi_score,
    -- Apply client-specific persona weighting
    (ldm.persona_alignment * cp.weight_technical + 
     ldm.funnel_value * cp.weight_business) as custom_persona_score,
    hpds.sentiment,
    hpds.content_classification
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
JOIN client_personas cp ON cl.client_id = cp.client_id AND cp.persona_name = $3
LEFT JOIN historical_page_dsi_snapshots hpds ON ldm.entity_url = hpds.url
WHERE ldm.client_id = $1                    -- Client isolation
AND cl.landscape_name = $2                   -- Client's landscape
AND ldm.entity_type = 'page'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY custom_persona_score DESC
LIMIT 20;
```

---

## Client Onboarding Process

### 1. Client Configuration Setup

```sql
-- 1. Create client record
INSERT INTO clients (
    id, name, industry_focus, logo_url, brand_color_primary,
    subscription_tier, max_landscapes, max_keywords, is_active
) VALUES (
    'new_client', 'New Client Inc', 'Financial Services',
    'https://cdn.example.com/new-client-logo.png', '#0066CC',
    'premium', 20, 500, true
);

-- 2. Create default personas
INSERT INTO client_personas (client_id, persona_name, display_name, weight_technical, weight_business, is_default)
VALUES 
    ('new_client', 'cto', 'Chief Technology Officer', 0.8, 0.2, true),
    ('new_client', 'product_manager', 'Product Manager', 0.4, 0.6, false),
    ('new_client', 'business_analyst', 'Business Analyst', 0.2, 0.8, false);

-- 3. Create custom metrics configuration
INSERT INTO client_metrics (
    client_id, metric_name, display_name, formula_type, component_weights,
    threshold_leader, threshold_challenger, threshold_competitor
) VALUES (
    'new_client', 'company_dsi', 'Company Dominance Score', 'weighted_sum',
    '{"keyword_coverage": 0.4, "traffic_share": 0.4, "persona_alignment": 0.2}',
    20.0, 10.0, 3.0
);

-- 4. Create initial landscapes
INSERT INTO client_landscapes (
    client_id, landscape_name, business_unit, description, display_order, is_active
) VALUES 
    ('new_client', 'Core Platform', 'Technology', 'Core technology platform landscape', 1, true),
    ('new_client', 'Market Solutions', 'Business', 'Market-facing solution landscape', 2, true);
```

### 2. Keyword Assignment

```sql
-- Assign keywords to client landscapes based on criteria
INSERT INTO client_landscape_keywords (client_id, landscape_id, keyword_id, custom_weight)
SELECT 
    'new_client',
    cl.id,
    k.id,
    1.0
FROM client_landscapes cl
CROSS JOIN keywords k
WHERE cl.client_id = 'new_client'
AND cl.landscape_name = 'Core Platform'
AND k.keyword LIKE '%platform%'  -- Custom keyword selection logic
AND k.is_active = true;
```

---

## Dashboard API Patterns (Multi-Tenant)

### 1. Client Context in All Endpoints

```python
# All endpoints require client context
@router.get("/landscapes")
@require_client_access()
async def get_client_landscapes(client_id: str, user=Depends(get_current_user)):
    """Get all landscapes for authenticated client"""
    async with db_pool.acquire() as conn:
        landscapes = await conn.fetch("""
            SELECT 
                cl.id, cl.landscape_name, cl.business_unit, cl.region,
                COUNT(ldm.entity_id) as total_entities,
                MAX(ldm.dsi_score) as top_dsi_score
            FROM client_landscapes cl
            LEFT JOIN landscape_dsi_metrics ldm ON cl.id = ldm.landscape_id 
                AND ldm.client_id = cl.client_id
                AND ldm.calculation_date = CURRENT_DATE
            WHERE cl.client_id = $1 AND cl.is_active = true
            GROUP BY cl.id, cl.landscape_name, cl.business_unit, cl.region, cl.display_order
            ORDER BY cl.display_order
        """, client_id)
        
        return {"landscapes": [dict(row) for row in landscapes]}
```

### 2. Brand Customization Endpoint

```python
@router.get("/branding")
@require_client_access()
async def get_client_branding(client_id: str, user=Depends(get_current_user)):
    """Get client-specific branding configuration"""
    async with db_pool.acquire() as conn:
        branding = await conn.fetchrow("""
            SELECT 
                name as client_name,
                logo_url,
                brand_color_primary,
                brand_color_secondary,
                timezone,
                date_format,
                currency
            FROM clients
            WHERE id = $1 AND is_active = true
        """, client_id)
        
        if not branding:
            raise HTTPException(404, "Client configuration not found")
            
        return dict(branding)
```

### 3. Custom Metrics Configuration

```python
@router.get("/metrics/configuration")
@require_client_access()
async def get_client_metrics_config(client_id: str, user=Depends(get_current_user)):
    """Get client-specific metrics configuration"""
    async with db_pool.acquire() as conn:
        metrics = await conn.fetch("""
            SELECT 
                metric_name,
                display_name,
                formula_type,
                component_weights,
                score_range_min,
                score_range_max,
                threshold_leader,
                threshold_challenger,
                threshold_competitor,
                description
            FROM client_metrics
            WHERE client_id = $1 AND is_active = true
            ORDER BY metric_name
        """, client_id)
        
        return {"metrics": [dict(row) for row in metrics]}
```

### 4. Persona-Aware Content Ranking

```python
@router.get("/landscapes/{landscape_id}/content") 
@require_client_access()
@require_landscape_access
async def get_landscape_content(
    landscape_id: str,
    client_id: str,
    persona: str = Query("default"),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user)
):
    """Get content ranked by client-specific persona preferences"""
    async with db_pool.acquire() as conn:
        # Get persona weights
        persona_config = await conn.fetchrow("""
            SELECT weight_technical, weight_business, weight_strategic
            FROM client_personas
            WHERE client_id = $1 AND (persona_name = $2 OR ($2 = 'default' AND is_default = true))
        """, client_id, persona)
        
        if not persona_config:
            raise HTTPException(404, "Persona not found")
        
        # Get content with persona-weighted scoring
        content = await conn.fetch("""
            SELECT 
                ldm.entity_name as title,
                ldm.entity_url as url,
                ldm.entity_domain as domain,
                ldm.dsi_score,
                ldm.rank_in_landscape,
                -- Apply client-specific persona weighting
                (ldm.persona_alignment * $4 + 
                 ldm.funnel_value * $5) as persona_weighted_score,
                hpds.sentiment,
                hpds.content_classification,
                hpds.word_count
            FROM landscape_dsi_metrics ldm
            LEFT JOIN historical_page_dsi_snapshots hpds ON ldm.entity_url = hpds.url
            WHERE ldm.client_id = $1
            AND ldm.landscape_id = $2
            AND ldm.entity_type = 'page'
            AND ldm.calculation_date = CURRENT_DATE
            ORDER BY persona_weighted_score DESC
            LIMIT $3
        """, client_id, landscape_id, limit, 
             persona_config['weight_technical'], 
             persona_config['weight_business'])
        
        return {
            "content": [dict(row) for row in content],
            "persona_applied": persona,
            "total_pages": len(content)
        }
```

---

## Client Configuration Management

### Admin Endpoints for Client Setup

```python
# Admin-only endpoints for managing client configurations
@router.post("/admin/clients")
@require_platform_admin()
async def create_client(client_config: ClientCreateRequest):
    """Create new client configuration"""
    pass

@router.put("/admin/clients/{client_id}/landscapes")
@require_platform_admin()
async def update_client_landscapes(client_id: str, landscapes: List[LandscapeConfig]):
    """Update client's landscape definitions"""
    pass

@router.put("/admin/clients/{client_id}/personas")
@require_platform_admin() 
async def update_client_personas(client_id: str, personas: List[PersonaConfig]):
    """Update client's persona definitions"""
    pass

@router.put("/admin/clients/{client_id}/metrics")
@require_platform_admin()
async def update_client_metrics(client_id: str, metrics: ClientMetricsConfig):
    """Update client's DSI calculation formulas"""
    pass
```

---

## Data Pipeline Integration

### Pipeline Service Updates Required

The existing pipeline service needs to be updated to support multi-tenant DSI calculations:

```python
# Update DSI calculation to be client-aware
async def calculate_client_landscape_dsi(self, client_id: str, landscape_id: str):
    """Calculate DSI for specific client's landscape using their custom configuration"""
    
    # Get client's custom metric configuration
    metric_config = await self.get_client_metric_config(client_id, 'company_dsi')
    
    # Get client's landscape keywords
    keywords = await self.get_client_landscape_keywords(client_id, landscape_id)
    
    # Get client's persona weights
    persona_weights = await self.get_client_default_persona(client_id)
    
    # Calculate DSI using client-specific formula
    dsi_results = await self.calculate_dsi_with_custom_formula(
        keywords=keywords,
        persona_weights=persona_weights,
        formula_weights=metric_config['component_weights']
    )
    
    # Store with client_id
    await self.store_client_dsi_results(client_id, landscape_id, dsi_results)
```

### Client-Specific Pipeline Execution

```python
# Pipeline service modifications for multi-tenant support
class ClientAwarePipelineService:
    async def execute_pipeline_for_client(self, client_id: str, config: PipelineConfig):
        """Execute pipeline with client-specific configurations"""
        
        # Get client's landscapes and keywords
        client_landscapes = await self.get_client_landscapes(client_id)
        
        # For each client landscape, calculate DSI
        for landscape in client_landscapes:
            await self.calculate_client_landscape_dsi(
                client_id=client_id,
                landscape_id=landscape['id'],
                custom_config=landscape['custom_weightings']
            )
```

---

## Frontend Multi-Tenant Patterns

### Client Context Provider

```typescript
// Client context for all dashboard components
interface ClientContext {
  clientId: string;
  clientName: string;
  branding: {
    logoUrl: string;
    primaryColor: string;
    secondaryColor: string;
  };
  subscription: {
    tier: 'basic' | 'premium' | 'enterprise';
    features: string[];
  };
  personas: PersonaConfig[];
  defaultPersona: string;
}

const ClientProvider: React.FC = ({ children }) => {
  const [clientContext, setClientContext] = useState<ClientContext | null>(null);
  
  useEffect(() => {
    // Load client configuration from JWT token
    const token = getAuthToken();
    const decoded = jwt.decode(token);
    setClientContext({
      clientId: decoded.client_id,
      clientName: decoded.client_name,
      branding: decoded.branding,
      // ... rest of client config
    });
  }, []);
  
  return (
    <ClientContext.Provider value={clientContext}>
      {children}
    </ClientContext.Provider>
  );
};
```

### Dynamic Branding

```tsx
// Component that adapts to client branding
const DashboardHeader: React.FC = () => {
  const { branding, clientName } = useClientContext();
  
  return (
    <header style={{ 
      backgroundColor: branding.primaryColor,
      borderBottom: `3px solid ${branding.secondaryColor}`
    }}>
      <img src={branding.logoUrl} alt={`${clientName} Logo`} />
      <h1>Digital Landscape Analytics</h1>
    </header>
  );
};
```

### Client-Aware API Calls

```typescript
// All API calls include client context automatically
const useClientApi = () => {
  const { clientId } = useClientContext();
  
  const apiCall = async (endpoint: string, options?: RequestInit) => {
    const response = await fetch(`/api/v1${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'X-Client-ID': clientId,  // Additional client header
        'Content-Type': 'application/json',
        ...options?.headers
      }
    });
    
    if (!response.ok) {
      throw new Error(`API call failed: ${response.statusText}`);
    }
    
    return response.json();
  };
  
  return { apiCall };
};

// Usage in components
const { data: landscapes } = useQuery({
  queryKey: ['landscapes', clientId],
  queryFn: () => apiCall('/landscapes')
});
```

---

## Deployment Configuration

### Multi-Tenant Environment Variables

```bash
# Multi-tenant dashboard service configuration
DATABASE_URL=postgresql://dashboard_user:password@postgres:5432/cylvy_analyze
REDIS_URL=redis://redis:6379

# Multi-tenant settings
ENABLE_CLIENT_ISOLATION=true
DEFAULT_CLIENT_ID=demo
REQUIRE_CLIENT_CONTEXT=true

# Feature flags per subscription tier
FEATURES_BASIC=landscapes,companies,basic_export
FEATURES_PREMIUM=landscapes,companies,pages,keywords,advanced_export,alerts
FEATURES_ENTERPRISE=all

# Performance settings per tier
MAX_CONCURRENT_QUERIES_BASIC=5
MAX_CONCURRENT_QUERIES_PREMIUM=20
MAX_CONCURRENT_QUERIES_ENTERPRISE=50

# Cache TTL per tier (seconds)
CACHE_TTL_BASIC=7200        # 2 hours
CACHE_TTL_PREMIUM=3600      # 1 hour  
CACHE_TTL_ENTERPRISE=1800   # 30 minutes
```

### Docker Compose Multi-Tenant Setup

```yaml
services:
  dashboard:
    build: ./dashboard
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ENABLE_CLIENT_ISOLATION=true
      - DEFAULT_CLIENT_ID=${DEFAULT_CLIENT_ID:-demo}
    depends_on:
      - postgres
      - redis
    networks:
      - cylvy-network
    restart: unless-stopped
    
  # Admin service for client management
  dashboard-admin:
    build: ./dashboard
    command: ["uvicorn", "app.admin:app", "--host", "0.0.0.0", "--port", "8003"]
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - ADMIN_MODE=true
    networks:
      - cylvy-network
```

---

## Testing Multi-Tenant Functionality

### Test Client Setup

```sql
-- Create test clients for development
INSERT INTO clients VALUES 
    ('test_client_a', 'Test Client A', 'Banking', 'http://example.com/logo-a.png', '#FF0000', '#FFFFFF', 'UTC', 'YYYY-MM-DD', 'USD', true, 'premium', 10, 100),
    ('test_client_b', 'Test Client B', 'Fintech', 'http://example.com/logo-b.png', '#00FF00', '#000000', 'America/New_York', 'MM/DD/YYYY', 'USD', true, 'enterprise', 25, 500);

-- Create different landscape sets for each client
INSERT INTO client_landscapes (client_id, landscape_name, business_unit, display_order, is_active) VALUES
    ('test_client_a', 'Retail Banking', 'Banking', 1, true),
    ('test_client_a', 'Commercial Banking', 'Banking', 2, true),
    ('test_client_b', 'Payment Innovation', 'Payments', 1, true),
    ('test_client_b', 'Embedded Finance', 'Fintech', 2, true);
```

### Verification Queries

```sql
-- Verify client data isolation
SELECT 
    client_id,
    COUNT(DISTINCT landscape_id) as landscapes,
    COUNT(*) as total_dsi_records,
    MAX(calculation_date) as latest_calculation
FROM landscape_dsi_metrics
GROUP BY client_id;

-- Verify no data leakage between clients
SELECT 
    cl.client_id,
    cl.landscape_name,
    COUNT(ldm.*) as dsi_records
FROM client_landscapes cl
LEFT JOIN landscape_dsi_metrics ldm ON cl.id = ldm.landscape_id 
    AND cl.client_id = ldm.client_id  -- Should always match
GROUP BY cl.client_id, cl.landscape_name
HAVING COUNT(ldm.*) > 0;
```

---

## Migration Path for Existing Data

### Current State → Multi-Tenant Migration

**Phase 1**: Add Multi-Tenant Schema
```sql
-- Add client columns to existing tables
ALTER TABLE landscape_dsi_metrics ADD COLUMN client_id VARCHAR;
ALTER TABLE digital_landscapes ADD COLUMN client_id VARCHAR;

-- Create client configuration tables
-- (Use table definitions from schema documentation)
```

**Phase 2**: Migrate Existing Data
```sql
-- Assign existing data to default client
UPDATE landscape_dsi_metrics SET client_id = 'finastra';
UPDATE digital_landscapes SET client_id = 'finastra';

-- Create client configuration from current setup
INSERT INTO clients (id, name, is_active, subscription_tier) 
VALUES ('finastra', 'Finastra', true, 'enterprise');
```

**Phase 3**: Update Application Code
- Add client_id to all DSI queries
- Update authentication to include client context
- Add client configuration APIs
- Update frontend for multi-tenant support

---

**This multi-tenant architecture allows the platform to serve unlimited clients, each with completely customized digital landscape definitions, personas, metrics, and branding while maintaining strict data isolation and security.**
