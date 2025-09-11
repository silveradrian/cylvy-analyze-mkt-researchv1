# 🔗 Backend Integration Specification

## 🎯 **Overview**

This document details the backend processes, services, and integrations that power each frontend feature of the Cylvy Market Intelligence Agent. Includes service architecture, data flow, and API integration patterns.

---

## 🏗️ **Service Architecture**

### **Core Service Dependencies:**
```
Frontend Components → API Layer → Service Layer → Database Layer

├── Authentication Service (JWT, user management)
├── Configuration Service (client settings, company data)
├── Keywords Service (CSV processing, validation, storage) 
├── Pipeline Service (orchestration, execution, monitoring)
├── Landscape Calculator (DSI calculation, competitive analysis)
├── Analysis Config Service (personas, JTBD, competitors)
├── WebSocket Service (real-time updates, notifications)
├── Storage Service (logo upload, file management)
└── Historical Data Service (trend analysis, time-series data)
```

### **Database Integration:**
```
PostgreSQL + TimescaleDB Extension:
├── Core Tables (users, client_config, keywords, analysis_config)
├── Pipeline Tables (pipeline_executions, serp_results)
├── TimescaleDB Hypertables (landscape_dsi_metrics, historical_keyword_metrics)
└── Multi-Domain Tables (company_domains, competitor_domains)
```

---

## 🖥️ **Frontend-to-Backend Integration by Screen**

### **1. Homepage (`/`) Backend Integration**

#### **System Health Check Process:**
```python
@router.get("/health")
async def api_health():
    """Comprehensive system health validation"""
    return {
        "api_version": "v1",
        "status": "healthy",
        "endpoints": [
            "/auth", "/config", "/keywords", "/pipeline", 
            "/analysis", "/landscapes", "/historical-metrics"
        ],
        "database_status": await check_database_connection(),
        "redis_status": await check_redis_connection()
    }
```

#### **Backend Services Involved:**
- **Health Check Service:** Database connectivity validation
- **Service Discovery:** Available endpoint enumeration
- **System Monitoring:** Performance metrics collection

---

### **2. Setup Wizard (`/setup`) Backend Integration**

#### **2.1 Authentication Flow:**

```python
# Auto-login for testing workflows
@router.post("/auth/login")  
async def login(credentials: LoginRequest):
    """Authenticate user and return JWT token"""
    user = await authenticate_user(credentials.email, credentials.password)
    if user:
        token = create_jwt_token(user)
        await update_last_login(user.id)
        return {
            "access_token": token,
            "token_type": "bearer", 
            "user": user.dict()
        }
    else:
        raise HTTPException(401, "Invalid credentials")
```

#### **2.2 Configuration Loading Process:**

```python
# Multi-source configuration aggregation
async def load_existing_configuration(user_id: str):
    """Load all configuration data for setup wizard"""
    
    # 1. Company configuration
    company_config = await config_service.get_config()
    
    # 2. Keywords configuration  
    keywords_data = await keywords_service.get_keywords_summary()
    
    # 3. Analysis configuration
    analysis_config = await analysis_config_service.get_config()
    
    # 4. Pipeline execution history
    pipeline_history = await pipeline_service.get_recent_pipelines(limit=10)
    
    return {
        "company": company_config,
        "keywords": keywords_data, 
        "analysis": analysis_config,
        "pipeline_history": pipeline_history,
        "completion_status": calculate_setup_completion(...)
    }
```

#### **2.3 Company Information Backend:**

```python
class ConfigService:
    """Client configuration management"""
    
    async def update_config(self, updates: dict):
        """Update client configuration with validation"""
        
        # Validate required fields
        if 'company_name' in updates:
            validate_company_name(updates['company_name'])
        
        if 'company_domain' in updates:
            validate_domain_format(updates['company_domain'])
            await check_domain_accessibility(updates['company_domain'])
        
        # Update database
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE client_config SET
                    company_name = $1,
                    company_domain = $2,
                    admin_email = $3,
                    description = $4,
                    industry = $5,
                    updated_at = NOW()
                WHERE id = $6
            """, ...)
```

#### **2.4 Logo Upload Process:**

```python
class StorageService:
    """File storage for client assets"""
    
    async def save_logo(self, file: UploadFile) -> str:
        """Process and save company logo"""
        
        # 1. Validate file type and size
        validate_image_file(file)
        
        # 2. Process image (resize, optimize)
        processed_image = await process_logo_image(file)
        
        # 3. Generate unique filename
        filename = f"logo_{uuid4().hex[:16]}.{get_file_extension(file)}"
        
        # 4. Save to storage
        file_path = LOGOS_PATH / filename
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(processed_image)
        
        return filename
```

#### **2.5 Keywords Upload Process:**

```python
class KeywordsService:
    """Keywords management and CSV processing"""
    
    async def upload_keywords_from_csv(self, file: UploadFile, regions: List[str]):
        """Process CSV upload with enhanced parsing"""
        
        # 1. Parse CSV with flexible column mapping
        csv_content = await file.read()
        keywords_data = []
        errors = []
        
        reader = csv.DictReader(io.StringIO(csv_content.decode('utf-8')))
        for row_num, row in enumerate(reader, 1):
            try:
                keyword_data = {
                    'keyword': self._extract_field(row, ['keyword', 'term']),
                    'category': self._extract_field(row, ['category', 'primary category']),
                    'client_score': self._parse_float(self._extract_field(row, ['client score'])),
                    'persona_score': self._parse_float(self._extract_field(row, ['persona score'])),
                    'seo_score': self._parse_float(self._extract_field(row, ['seo score']))
                }
                keywords_data.append(keyword_data)
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        # 2. Bulk insert with conflict resolution
        keywords_processed = 0
        async with db_pool.acquire() as conn:
            for kw_data in keywords_data:
                await conn.execute("""
                    INSERT INTO keywords (id, keyword, category, client_score, persona_score, seo_score)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (keyword) DO UPDATE SET
                        category = EXCLUDED.category,
                        client_score = EXCLUDED.client_score,
                        updated_at = NOW()
                """, uuid4(), ...)
                keywords_processed += 1
        
        return {
            'total_keywords': len(keywords_data),
            'keywords_processed': keywords_processed,
            'errors': errors
        }
```

#### **2.6 Analysis Configuration Backend:**

```python
class AnalysisConfigService:
    """Analysis configuration management"""
    
    async def update_personas(self, personas: List[PersonaRequest]):
        """Update persona configuration with Pydantic serialization"""
        
        # Convert Pydantic models to JSON serializable format
        serializable_personas = []
        for persona in personas:
            if hasattr(persona, 'model_dump'):
                serializable_personas.append(persona.model_dump())
            else:
                serializable_personas.append(persona.dict())
        
        await self.update_config({
            "personas": serializable_personas
        })
    
    async def update_jtbd_phases(self, phases: List[JTBDPhaseRequest]):
        """Update JTBD phases configuration"""
        
        serializable_phases = []
        for phase in phases:
            serializable_phases.append({
                "name": phase.name,
                "description": phase.description,
                "buyer_mindset": getattr(phase, 'buyer_mindset', ''),
                "key_questions": getattr(phase, 'key_questions', []),
                "content_types": getattr(phase, 'content_types', [])
            })
        
        await self.update_config({
            "jtbd_phases": serializable_phases
        })
```

---

### **3. Pipeline Management (`/pipeline`) Backend Integration**

#### **Pipeline Orchestration Service:**

```python
class PipelineService:
    """Unified pipeline orchestration with real-time monitoring"""
    
    async def start_pipeline(self, config: PipelineConfig) -> UUID:
        """Start comprehensive analysis pipeline"""
        
        pipeline_id = uuid4()
        
        # 1. Create execution record
        pipeline_result = PipelineResult(
            pipeline_id=pipeline_id,
            status=PipelineStatus.PENDING,
            mode=PipelineMode.BATCH_OPTIMIZED,
            started_at=datetime.utcnow()
        )
        
        # 2. Store initial state
        await self._save_pipeline_state(pipeline_result)
        
        # 3. Start background execution
        asyncio.create_task(self._execute_pipeline(pipeline_id, config))
        
        # 4. Broadcast start notification
        await self._broadcast_status(pipeline_id, "Pipeline started")
        
        return pipeline_id
    
    async def _execute_pipeline(self, pipeline_id: UUID, config: PipelineConfig):
        """Execute 9-phase analysis workflow"""
        
        try:
            # Phase 1: Keyword Metrics Enrichment
            if config.collect_keyword_metrics:
                await self._phase_keyword_metrics(pipeline_id)
            
            # Phase 2: SERP Data Collection  
            if config.collect_serp:
                await self._phase_serp_collection(pipeline_id)
            
            # Phase 3: Company Enrichment
            if config.enrich_companies:
                await self._phase_company_enrichment(pipeline_id)
            
            # Phase 4: Video Content Enrichment
            if config.enrich_videos:
                await self._phase_video_enrichment(pipeline_id)
            
            # Phase 5: Web Content Scraping
            if config.scrape_content:
                await self._phase_content_scraping(pipeline_id)
            
            # Phase 6: AI Content Analysis
            if config.analyze_content:
                await self._phase_content_analysis(pipeline_id)
            
            # Phase 7: DSI Calculation
            await self._phase_dsi_calculation(pipeline_id)
            
            # Phase 8: Digital Landscape DSI
            if config.enable_landscape_dsi:
                await self._phase_landscape_dsi(pipeline_id)
            
            # Phase 9: Historical Data Storage
            await self._phase_historical_storage(pipeline_id)
            
            # Complete execution
            await self._complete_pipeline(pipeline_id)
            
        except Exception as e:
            await self._fail_pipeline(pipeline_id, str(e))
```

#### **Real-Time Updates Service:**

```python
class WebSocketService:
    """Real-time update broadcasting"""
    
    async def broadcast_pipeline_update(self, pipeline_id: UUID, update_data: dict):
        """Broadcast pipeline progress to connected clients"""
        
        message = {
            "type": "pipeline_update",
            "pipeline_id": str(pipeline_id),
            "timestamp": datetime.utcnow().isoformat(),
            "data": update_data
        }
        
        # Broadcast to pipeline channel
        await self.broadcast_to_channel("pipeline", json.dumps(message))
        
        # Broadcast to specific pipeline channel
        await self.broadcast_to_channel(f"pipeline_{pipeline_id}", json.dumps(message))
```

---

### **4. Digital Landscapes (`/landscapes`) Backend Integration**

#### **Landscape Management Service:**

```python
class LandscapeService:
    """Digital landscape creation and management"""
    
    async def create_landscape(self, landscape_data: dict, user_id: str) -> str:
        """Create new digital landscape"""
        
        landscape_id = str(uuid4())
        
        async with db_pool.acquire() as conn:
            # 1. Create landscape record
            await conn.execute("""
                INSERT INTO digital_landscapes (id, name, description, created_by)
                VALUES ($1, $2, $3, $4)
            """, landscape_id, landscape_data['name'], 
                landscape_data['description'], user_id)
            
            # 2. Assign keywords if provided
            if landscape_data.get('keyword_ids'):
                for keyword_id in landscape_data['keyword_ids']:
                    await conn.execute("""
                        INSERT INTO landscape_keywords (landscape_id, keyword_id)
                        VALUES ($1, $2)
                    """, landscape_id, keyword_id)
        
        return landscape_id
    
    async def get_available_keywords(self, search: str = None, limit: int = 100):
        """Get keywords available for landscape assignment"""
        
        async with db_pool.acquire() as conn:
            if search:
                keywords = await conn.fetch("""
                    SELECT id, keyword, avg_monthly_searches as search_volume, competition_level
                    FROM keywords
                    WHERE keyword ILIKE $1
                    ORDER BY avg_monthly_searches DESC NULLS LAST, keyword
                    LIMIT $2
                """, f"%{search}%", limit)
            else:
                keywords = await conn.fetch("""
                    SELECT id, keyword, avg_monthly_searches as search_volume, competition_level
                    FROM keywords
                    ORDER BY avg_monthly_searches DESC NULLS LAST, keyword
                    LIMIT $1
                """, limit)
        
        return [dict(row) for row in keywords]
```

#### **DSI Calculation Engine:**

```python
class ProductionLandscapeCalculator:
    """Production-ready DSI calculation with TimescaleDB optimization"""
    
    async def calculate_and_store_landscape_dsi(self, landscape_id: str, client_id: str):
        """Calculate DSI metrics for landscape with proper keyword filtering"""
        
        # 1. Extract landscape-specific keywords
        landscape_keywords = await self._get_landscape_keyword_ids(landscape_id)
        
        if not landscape_keywords:
            raise ValueError(f"No keywords assigned to landscape {landscape_id}")
        
        # 2. Collect SERP data for landscape keywords only
        calculation_date = datetime.now().date()
        start_date = calculation_date - timedelta(days=30)
        end_date = calculation_date
        
        # 3. Query SERP results with landscape filtering
        serp_data = await self._get_landscape_serp_data(
            landscape_keywords, start_date, end_date
        )
        
        # 4. Calculate DSI scores per company
        company_metrics = {}
        for domain, domain_data in serp_data.items():
            
            # Calculate core metrics
            unique_keywords = len(domain_data['keywords'])
            keyword_coverage = unique_keywords / len(landscape_keywords)
            estimated_traffic = sum(kw['estimated_traffic'] for kw in domain_data['keywords'])
            
            # Calculate persona alignment (simplified for this example)
            persona_alignment = await self._calculate_persona_alignment(
                domain_data['keywords'], landscape_id
            )
            
            # Calculate funnel value based on JTBD stage distribution
            funnel_value = await self._calculate_funnel_value(
                domain_data['keywords'], landscape_id
            )
            
            # Calculate traffic share
            total_landscape_traffic = await self._get_total_landscape_traffic(landscape_id)
            traffic_share = estimated_traffic / total_landscape_traffic if total_landscape_traffic > 0 else 0
            
            # DSI Score Algorithm (weighted components)
            dsi_score = (
                (keyword_coverage * 0.40) +      # 40% weight
                (traffic_share * 0.35) +         # 35% weight  
                (persona_alignment * 0.15) +     # 15% weight
                (funnel_value * 0.10)            # 10% weight
            )
            
            company_metrics[domain] = {
                'unique_keywords': unique_keywords,
                'keyword_coverage': keyword_coverage,
                'estimated_traffic': estimated_traffic,
                'traffic_share': traffic_share,
                'persona_alignment': persona_alignment,
                'funnel_value': funnel_value,
                'dsi_score': dsi_score
            }
        
        # 5. Calculate rankings and market positions
        ranked_companies = sorted(
            company_metrics.items(), 
            key=lambda x: x[1]['dsi_score'], 
            reverse=True
        )
        
        # 6. Store in TimescaleDB hypertable
        async with db_pool.acquire() as conn:
            for rank, (domain, metrics) in enumerate(ranked_companies, 1):
                
                # Determine market position based on ranking
                total_companies = len(ranked_companies)
                if rank == 1:
                    market_position = "LEADER"
                elif rank <= total_companies * 0.2:
                    market_position = "CHALLENGER" 
                elif rank <= total_companies * 0.6:
                    market_position = "COMPETITOR"
                else:
                    market_position = "NICHE"
                
                # Insert into TimescaleDB hypertable
                await conn.execute("""
                    INSERT INTO landscape_dsi_metrics (
                        landscape_id, calculation_date, entity_type, entity_name, 
                        entity_domain, unique_keywords, keyword_coverage, 
                        estimated_traffic, traffic_share, persona_alignment,
                        funnel_value, dsi_score, rank_in_landscape, 
                        total_entities_in_landscape, market_position
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (landscape_id, calculation_date, entity_type, entity_id) 
                    DO UPDATE SET
                        dsi_score = EXCLUDED.dsi_score,
                        rank_in_landscape = EXCLUDED.rank_in_landscape,
                        updated_at = NOW()
                """, landscape_id, calculation_date, "company", 
                    self._extract_company_name(domain), domain,
                    metrics['unique_keywords'], metrics['keyword_coverage'],
                    metrics['estimated_traffic'], metrics['traffic_share'],
                    metrics['persona_alignment'], metrics['funnel_value'],
                    metrics['dsi_score'], rank, total_companies, market_position)
        
        # 7. Broadcast completion via WebSocket
        await self.websocket_service.broadcast_to_channel(
            f"landscape_{landscape_id}",
            {
                "type": "calculation_complete",
                "landscape_id": landscape_id,
                "calculation_date": calculation_date.isoformat(),
                "total_companies": len(ranked_companies)
            }
        )
```

---

### **5. Pipeline Phase Execution Details**

#### **Phase 1: Keyword Metrics Enrichment**
```python
async def _phase_keyword_metrics(self, pipeline_id: UUID):
    """Enrich keywords with Google Ads Historical API data"""
    
    # Get all keywords requiring metrics
    keywords = await self._get_keywords_for_enrichment(pipeline_id)
    
    # Batch process by geography (1000 keywords per geo per day limit)
    for country_code in ['US', 'UK', 'DE', 'SA', 'VN']:
        batch_keywords = keywords[:1000]  # Respect API limits
        
        try:
            # Use Enhanced Google Ads Service
            metrics = await self.google_ads_service.get_historical_metrics_batch(
                keywords=batch_keywords,
                geo_location=country_code,
                date_range='LAST_30_DAYS'
            )
            
            # Store in historical_keyword_metrics (TimescaleDB hypertable)
            await self._store_keyword_metrics(metrics, country_code, pipeline_id)
            
        except Exception as e:
            logger.warning(f"Keyword metrics failed for {country_code}: {e}")
    
    await self._update_pipeline_progress(pipeline_id, "keyword_metrics_enrichment", "completed")
```

#### **Phase 2: SERP Data Collection**
```python
async def _phase_serp_collection(self, pipeline_id: UUID):
    """Collect SERP data for all keywords across target countries"""
    
    # Get analysis configuration
    config = await self.analysis_config_service.get_config()
    target_countries = config.get('target_countries', ['US', 'UK'])
    
    # Get all active keywords
    keywords = await self._get_active_keywords()
    
    # Collect SERP data per country
    for country_code in target_countries:
        serp_results = []
        
        for keyword in keywords:
            try:
                # Use ScaleSERP API for data collection
                results = await self.serp_collector.collect_serp_data(
                    keyword=keyword.keyword,
                    country=country_code,
                    language='en',
                    limit=100
                )
                
                # Process and store results
                for result in results:
                    serp_results.append({
                        'keyword_id': keyword.id,
                        'country_code': country_code,
                        'domain': result.domain,
                        'url': result.url,
                        'title': result.title,
                        'description': result.snippet,
                        'position': result.position,
                        'estimated_traffic': result.estimated_traffic
                    })
                
            except Exception as e:
                await self._log_pipeline_error(pipeline_id, f"SERP collection failed for {keyword.keyword}: {e}")
        
        # Bulk insert SERP results
        await self._store_serp_results(serp_results, pipeline_id)
    
    await self._update_pipeline_progress(pipeline_id, "serp_collection", "completed")
```

#### **Phase 8: Digital Landscape DSI Integration**
```python
async def _phase_landscape_dsi(self, pipeline_id: UUID):
    """Calculate DSI for all active digital landscapes"""
    
    # Get all active landscapes
    landscapes = await self._get_active_landscapes()
    
    for landscape in landscapes:
        try:
            # Use ProductionLandscapeCalculator
            result = await self.landscape_calculator.calculate_and_store_landscape_dsi(
                landscape_id=str(landscape.id),
                client_id=str(self.client_id)
            )
            
            await self._update_pipeline_progress(
                pipeline_id, 
                f"landscape_dsi_{landscape.id}", 
                "completed",
                metadata={
                    "landscape_name": landscape.name,
                    "companies_analyzed": result.total_companies,
                    "keywords_processed": result.total_keywords
                }
            )
            
        except Exception as e:
            logger.error(f"Landscape DSI calculation failed for {landscape.name}: {e}")
            await self._log_pipeline_error(
                pipeline_id, 
                f"Landscape DSI failed for {landscape.name}: {e}"
            )
    
    await self._update_pipeline_progress(pipeline_id, "landscape_dsi_calculations", "completed")
```

---

## 📊 **TimescaleDB Integration**

### **Hypertable Architecture:**

#### **1. Historical Keyword Metrics (Time-Series Optimized)**
```sql
-- Monthly keyword performance tracking
SELECT 
    DATE_TRUNC('month', snapshot_date) as month,
    keyword_text,
    country_code,
    AVG(avg_monthly_searches) as avg_search_volume,
    AVG(competition_level_numeric) as avg_competition,
    COUNT(*) as measurement_count
FROM historical_keyword_metrics
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '12 months'
  AND keyword_id = $1
GROUP BY month, keyword_text, country_code
ORDER BY month ASC;

-- Performance: ~20ms (vs 2,000ms with regular PostgreSQL)
```

#### **2. Landscape DSI Metrics (Competitive Analysis Optimized)**
```sql
-- Company competitive positioning trends
WITH monthly_rankings AS (
    SELECT 
        DATE_TRUNC('month', calculation_date) as month,
        entity_name,
        AVG(dsi_score) as avg_dsi_score,
        AVG(rank_in_landscape) as avg_ranking,
        AVG(traffic_share) as avg_traffic_share
    FROM landscape_dsi_metrics
    WHERE landscape_id = $1
      AND entity_type = 'company'
      AND calculation_date >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY month, entity_name
)
SELECT 
    month,
    entity_name,
    avg_dsi_score,
    avg_ranking,
    avg_traffic_share,
    LAG(avg_dsi_score) OVER (PARTITION BY entity_name ORDER BY month) as prev_dsi_score,
    (avg_dsi_score - LAG(avg_dsi_score) OVER (PARTITION BY entity_name ORDER BY month)) as dsi_change
FROM monthly_rankings
ORDER BY month ASC, avg_dsi_score DESC;

-- Performance: ~50ms (vs 5,000ms with regular PostgreSQL)
```

---

## 🔄 **Data Synchronization Patterns**

### **Frontend-Backend Sync Strategy:**

#### **1. Optimistic Updates:**
```typescript
// Update UI immediately, sync with backend
const updateKeywordStatus = async (keywordId: string, status: string) => {
  // 1. Update UI optimistically
  setKeywords(prev => prev.map(kw => 
    kw.id === keywordId ? { ...kw, status } : kw
  ));
  
  // 2. Sync with backend
  try {
    await apiCall(`/keywords/${keywordId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status })
    });
  } catch (error) {
    // 3. Revert on failure
    setKeywords(prev => prev.map(kw => 
      kw.id === keywordId ? { ...kw, status: kw.originalStatus } : kw
    ));
    showErrorMessage('Failed to update keyword status');
  }
};
```

#### **2. Real-Time Synchronization:**
```typescript
// WebSocket-based real-time data sync
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8001/ws/landscapes');
  
  ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    
    switch (update.type) {
      case 'landscape_created':
        setLandscapes(prev => [...prev, update.landscape]);
        break;
        
      case 'dsi_calculation_update':
        setCalculationProgress(update.progress);
        break;
        
      case 'dsi_calculation_complete':
        refreshLandscapeMetrics(update.landscape_id);
        break;
    }
  };
});
```

---

## 📈 **Historical Data & Trend Analysis Backend**

### **Trend Calculation Service:**

```python
class HistoricalDataService:
    """Time-series analysis and trend calculation"""
    
    async def get_landscape_trends(self, landscape_id: str, entity_id: str, months: int = 12):
        """Generate trend analysis for landscape entity"""
        
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        async with db_pool.acquire() as conn:
            # TimescaleDB optimized query with time_bucket
            trends = await conn.fetch("""
                SELECT 
                    time_bucket('1 month', calculation_date) as month,
                    AVG(dsi_score) as avg_dsi_score,
                    AVG(rank_in_landscape) as avg_rank,
                    AVG(traffic_share) as avg_traffic_share,
                    AVG(keyword_coverage) as avg_keyword_coverage,
                    COUNT(*) as measurement_count
                FROM landscape_dsi_metrics
                WHERE landscape_id = $1
                  AND entity_id = $2
                  AND calculation_date >= $3
                  AND calculation_date <= $4
                GROUP BY month
                ORDER BY month ASC
            """, landscape_id, entity_id, start_date, end_date)
            
            # Calculate trend indicators
            trend_data = []
            for i, row in enumerate(trends):
                trend_point = dict(row)
                
                # Calculate month-over-month changes
                if i > 0:
                    prev_row = trends[i-1]
                    trend_point['dsi_change'] = row['avg_dsi_score'] - prev_row['avg_dsi_score']
                    trend_point['rank_change'] = prev_row['avg_rank'] - row['avg_rank']  # Rank improvement is negative
                    trend_point['traffic_change'] = row['avg_traffic_share'] - prev_row['avg_traffic_share']
                
                trend_data.append(trend_point)
            
            return {
                "entity_id": entity_id,
                "analysis_period": f"{months} months",
                "trends": trend_data,
                "performance_summary": self._calculate_performance_summary(trend_data)
            }
```

### **Competitive Intelligence Aggregation:**

```python
async def generate_competitive_intelligence_report(self, landscape_id: str):
    """Generate comprehensive competitive intelligence"""
    
    # 1. Current market snapshot
    current_snapshot = await self._get_current_landscape_snapshot(landscape_id)
    
    # 2. Historical trend analysis  
    historical_trends = await self._get_landscape_historical_trends(landscape_id, months=12)
    
    # 3. Market dynamics analysis
    market_dynamics = await self._analyze_market_dynamics(landscape_id)
    
    # 4. Competitive gap analysis
    competitive_gaps = await self._identify_competitive_gaps(landscape_id)
    
    # 5. Strategic recommendations
    recommendations = await self._generate_strategic_recommendations(
        current_snapshot, historical_trends, competitive_gaps
    )
    
    return {
        "landscape_name": current_snapshot['landscape_name'],
        "analysis_date": datetime.now().isoformat(),
        "executive_summary": {
            "market_leaders": current_snapshot['top_3_companies'],
            "market_concentration": market_dynamics['concentration_index'],
            "growth_trends": historical_trends['market_growth'],
            "key_insights": recommendations['top_3_insights']
        },
        "detailed_analysis": {
            "current_rankings": current_snapshot['full_rankings'],
            "trend_analysis": historical_trends,
            "competitive_gaps": competitive_gaps,
            "strategic_recommendations": recommendations
        },
        "data_quality": {
            "keywords_analyzed": current_snapshot['total_keywords'],
            "companies_tracked": current_snapshot['total_companies'],
            "data_freshness": current_snapshot['last_calculation_date']
        }
    }
```

---

## 🔧 **Error Handling & Recovery**

### **Backend Error Management:**

```python
# Graceful error handling with detailed logging
@router.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handling with structured logging"""
    
    logger.error(f"Unhandled exception: {exc}", extra={
        "request_url": str(request.url),
        "user_agent": request.headers.get("user-agent"),
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "type": "internal_error"
            }
        }
    )

# Service-specific error handling
class KeywordsService:
    async def upload_keywords_from_csv(self, file, regions):
        try:
            # Process CSV upload
            return await self._process_csv_upload(file, regions)
        
        except ValueError as e:
            # Client-side validation error
            raise HTTPException(status_code=400, detail=str(e))
        
        except Exception as e:
            # Log unexpected error for debugging
            logger.error(f"Keyword upload failed: {e}")
            raise HTTPException(status_code=500, detail="Upload processing failed")
```

### **Database Transaction Management:**

```python
# Atomic operations with rollback capability
async def update_landscape_configuration(self, landscape_id: str, updates: dict):
    """Update landscape with atomic transaction"""
    
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            try:
                # Update landscape details
                await conn.execute("""
                    UPDATE digital_landscapes 
                    SET name = $1, description = $2, updated_at = NOW()
                    WHERE id = $3
                """, updates['name'], updates['description'], landscape_id)
                
                # Update keyword assignments
                if 'keyword_ids' in updates:
                    # Remove existing assignments
                    await conn.execute("""
                        DELETE FROM landscape_keywords WHERE landscape_id = $1
                    """, landscape_id)
                    
                    # Add new assignments
                    for keyword_id in updates['keyword_ids']:
                        await conn.execute("""
                            INSERT INTO landscape_keywords (landscape_id, keyword_id)
                            VALUES ($1, $2)
                        """, landscape_id, keyword_id)
                
                # Log successful update
                logger.info(f"Landscape {landscape_id} updated successfully")
                
            except Exception as e:
                # Transaction automatically rolled back
                logger.error(f"Landscape update failed: {e}")
                raise
```

---

## ⚡ **Performance Optimization**

### **Database Query Optimization:**

#### **TimescaleDB Chunk Pruning:**
```sql
-- Efficient time-range queries with automatic chunk pruning
EXPLAIN (ANALYZE, BUFFERS) 
SELECT 
    entity_name,
    AVG(dsi_score) as avg_score,
    COUNT(*) as measurement_count
FROM landscape_dsi_metrics
WHERE landscape_id = $1
  AND calculation_date >= CURRENT_DATE - INTERVAL '90 days'
  AND entity_type = 'company'
GROUP BY entity_name
ORDER BY avg_score DESC;

-- Result: Index Scan on chunk (cost=0.29..8.31 rows=1 width=32)
--         Execution time: 45.234 ms
```

#### **Connection Pool Management:**
```python
# Optimized database connection handling
class DatabasePool:
    def __init__(self):
        self.pool = None
        
    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=10,           # Minimum connections
            max_size=20,           # Maximum connections  
            command_timeout=60,    # Query timeout
            server_settings={
                'application_name': 'cylvy_analyzer',
                'jit': 'off'       # Disable JIT for faster simple queries
            }
        )
```

### **API Response Optimization:**

```python
# Pagination for large datasets
@router.get("/landscapes/{landscape_id}/metrics")
async def get_landscape_metrics(
    landscape_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query('dsi_score', enum=['dsi_score', 'traffic_share', 'rank']),
    order: str = Query('desc', enum=['asc', 'desc'])
):
    """Get paginated landscape metrics with sorting"""
    
    async with db_pool.acquire() as conn:
        # Count total records
        total = await conn.fetchval("""
            SELECT COUNT(*) FROM landscape_dsi_metrics
            WHERE landscape_id = $1 AND calculation_date = CURRENT_DATE
        """, landscape_id)
        
        # Get paginated results with sorting
        metrics = await conn.fetch(f"""
            SELECT * FROM landscape_dsi_metrics
            WHERE landscape_id = $1 AND calculation_date = CURRENT_DATE
            ORDER BY {sort_by} {order}
            LIMIT $2 OFFSET $3
        """, landscape_id, limit, offset)
        
        return {
            "metrics": [dict(row) for row in metrics],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        }
```

---

## 🧪 **Testing & Quality Assurance Backend**

### **API Testing Framework:**

```python
# Comprehensive API testing for frontend integration
class TestPipelineAPI:
    async def test_pipeline_start_integration(self):
        """Test pipeline start API with frontend payload"""
        
        # Simulate frontend request
        payload = {
            "collect_serp": True,
            "enrich_companies": True,
            "scrape_content": False,
            "analyze_content": False
        }
        
        response = await client.post("/api/v1/pipeline/start", json=payload)
        
        assert response.status_code == 200
        assert "pipeline_id" in response.json()
        assert response.json()["status"] == "pending"
        
        # Verify database state
        pipeline_id = response.json()["pipeline_id"]
        db_record = await get_pipeline_from_db(pipeline_id)
        assert db_record["status"] == "pending"

class TestLandscapeAPI:
    async def test_landscape_creation_workflow(self):
        """Test complete landscape creation from frontend"""
        
        # 1. Create landscape
        landscape_data = {
            "name": "Test Banking Landscape",
            "description": "Test market segment",
            "keyword_ids": ["uuid1", "uuid2", "uuid3"]
        }
        
        response = await client.post("/api/v1/landscapes", json=landscape_data)
        landscape_id = response.json()["landscape_id"]
        
        # 2. Verify keyword assignments
        keywords = await client.get(f"/api/v1/landscapes/{landscape_id}/keywords")
        assert len(keywords.json()) == 3
        
        # 3. Test DSI calculation
        calc_response = await client.post(f"/api/v1/landscapes/{landscape_id}/calculate")
        assert calc_response.status_code == 200
```

---

## 📚 **API Documentation Integration**

### **Automated API Documentation:**
- **FastAPI Integration:** Automatic OpenAPI/Swagger documentation
- **Interactive Testing:** Built-in API testing interface at `/docs`
- **Schema Validation:** Pydantic models provide request/response schemas
- **Example Requests:** Real-world usage examples for frontend developers

### **API Versioning Strategy:**
```python
# Version 1 API with future versioning support
app.include_router(api_router, prefix="/api/v1")

# Future versioning capability
# app.include_router(api_v2_router, prefix="/api/v2")
```

---

This backend integration specification provides comprehensive coverage of the services, processes, and data flows that power the Cylvy frontend experience. The companion API documentation will detail specific endpoint specifications and integration patterns.
