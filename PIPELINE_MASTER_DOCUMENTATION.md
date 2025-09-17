# Digital Landscape Pipeline - Master Documentation

## Overview
The Cylvy Digital Landscape Analyzer is a comprehensive pipeline system that processes keywords through multiple phases to generate Digital Strength Index (DSI) rankings. This document covers the complete pipeline workflow, orchestration, monitoring, and robustness features.

## Pipeline Architecture

### Core Components
- **Pipeline Service**: Main orchestrator (`pipeline_service.py`)
- **Robustness Services**: Circuit breakers, retry managers, state tracking
- **Phase Orchestrator**: Manages phase dependencies and execution
- **Pipeline Monitor**: Health monitoring and recovery
- **Concurrent Analyzers**: Real-time content processing
- **WebSocket Service**: Real-time status updates

### Database Tables
- `pipeline_executions`: Main pipeline records
- `pipeline_phase_status`: Phase tracking and status
- `pipeline_state`: Granular item-level state tracking
- `serp_results`: Search result data
- `company_profiles`: Enriched company information
- `scraped_content`: Web content data
- `optimized_content_analysis`: AI analysis results

## Pipeline Phases

### Phase 1: Keyword Metrics Enrichment
**Purpose**: Enrich keywords with search volume and competition data
**Service**: `SimplifiedGoogleAdsService` with DataForSEO fallback
**Dependencies**: None (entry point)
**Timeout**: 30 minutes

**Process**:
1. Fetch keywords from project database
2. Batch keywords (max 20 per Google Ads request, 1000 per service call)
3. Call Google Ads API for metrics
4. Fallback to DataForSEO if Google Ads fails
5. Cache results for 24 hours
6. Store metrics in `historical_keyword_metrics`

**Success Criteria**: Keywords have search volume and competition data
**Gating**: None - this is the entry phase

### Phase 2: SERP Collection
**Purpose**: Collect search engine results for keywords
**Service**: `UnifiedSERPCollector` using ScaleSERP API
**Dependencies**: Keyword metrics (optional)
**Timeout**: 120 minutes

**Process**:
1. Get active keywords from project
2. Create SERP requests for each keyword × region × content_type combination
3. Submit batch requests to ScaleSERP
4. Monitor batch completion via webhooks
5. Download and parse CSV results
6. Store in `serp_results` table
7. Extract unique domains and video URLs

**Success Criteria**: SERP results stored with domains and URLs extracted
**Gating**: None - can run independently

### Phase 3: Company Enrichment (SERP)
**Purpose**: Enrich company data for domains found in SERP results
**Service**: `EnhancedCompanyEnricher` using Cognism API
**Dependencies**: SERP Collection must be completed
**Timeout**: 60 minutes

**Process**:
1. **Gating Check**: Verify SERP collection is completed and has results
2. Extract unique domains from SERP results
3. For each domain:
   - Search company using Cognism `/search/account/search`
   - Redeem full details using `/search/account/redeem`
   - Map data to `CompanyProfile` model
   - Store in `company_profiles` table
4. Create fallback profiles for domains not found

**Success Criteria**: Company profiles created for SERP domains
**Gating**: SERP collection must be completed with results > 0

### Phase 4: YouTube Enrichment
**Purpose**: Enrich YouTube video metadata and channel information
**Service**: `OptimizedVideoEnricher` using YouTube Data API
**Dependencies**: SERP Collection (for video URLs)
**Timeout**: 60 minutes

**Process**:
1. Extract video URLs from SERP results
2. Fetch video metadata (views, likes, duration, etc.)
3. Enrich channel information (subscriber count)
4. Store in `video_snapshots` table
5. Background channel-to-company resolution

**Success Criteria**: Video metadata enriched and stored
**Gating**: Video URLs must exist in SERP results

### Phase 5: Content Scraping
**Purpose**: Scrape web content from SERP result URLs
**Service**: `WebScraper` using ScrapingBee API
**Dependencies**: SERP Collection (for content URLs)
**Timeout**: 180 minutes

**Process**:
1. Extract content URLs from SERP results
2. Scrape each URL using ScrapingBee
3. Extract title, content, meta description
4. Store in `scraped_content` table with status tracking
5. Concurrent content analysis starts automatically

**Success Criteria**: Web content scraped and stored
**Gating**: Content URLs must exist in SERP results

### Phase 6: Content Analysis
**Purpose**: AI analysis of scraped content for business intelligence
**Service**: `ConcurrentContentAnalyzer` using OpenAI API
**Dependencies**: Content Scraping + Company Enrichment
**Timeout**: 240 minutes

**Process**:
1. **Gating Check**: Content must be scraped AND domain must be enriched
2. Monitor `scraped_content` for completed scraping
3. Join with `company_profiles` for company context
4. Analyze content using GPT-4 for:
   - Business model insights
   - Technology stack
   - Market positioning
   - Competitive advantages
5. Store results in `optimized_content_analysis`

**Success Criteria**: Content analyzed with AI insights
**Gating**: 
- Content must be scraped (status = 'completed')
- Domain must have company profile
- Content length > 100 characters

### Phase 7: DSI Calculation
**Purpose**: Calculate Digital Strength Index rankings
**Service**: `SimplifiedDSICalculator`
**Dependencies**: Content Analysis + Company Enrichment + YouTube Enrichment
**Timeout**: 30 minutes

**Process**:
1. **Gating Check**: All prerequisite data must be available
2. Aggregate data from all previous phases
3. Calculate DSI scores based on:
   - Content quality and relevance
   - Company strength metrics
   - Digital presence indicators
   - Video engagement metrics
4. Generate rankings and insights

**Success Criteria**: DSI scores calculated and stored
**Gating**:
- Content analysis must be completed with results > 0
- Company enrichment must be successful
- SERP results must exist

### Phase 8: Historical Snapshot (Optional)
**Purpose**: Create historical data snapshots for trend analysis
**Dependencies**: DSI Calculation
**Process**: Archive current state for historical comparison

### Phase 9: Landscape DSI Calculation (Optional)
**Purpose**: Calculate landscape-level DSI metrics
**Dependencies**: Same as DSI Calculation
**Process**: Aggregate DSI data across broader market segments

## Robustness Features

### 1. Circuit Breakers
**Purpose**: Prevent cascade failures from external API issues
**Implementation**: `CircuitBreakerManager`
**Features**:
- Configurable failure thresholds
- Automatic recovery detection
- Fallback mechanisms

### 2. State Tracking
**Purpose**: Granular progress tracking for resumability
**Implementation**: `StateTracker`
**Features**:
- Item-level progress tracking
- Pipeline resumption after failures
- Duplicate prevention

### 3. Retry Management
**Purpose**: Handle transient failures gracefully
**Implementation**: `RetryManager`
**Features**:
- Exponential backoff
- Configurable retry limits
- Error categorization

### 4. Pipeline Monitor
**Purpose**: Health monitoring and automatic recovery
**Implementation**: `PipelineMonitor`
**Features**:
- Phase timeout detection (30-240 minutes per phase)
- Stuck pipeline detection (48-hour limit)
- Automatic recovery attempts
- Flexible phase completion

### 5. Concurrent Processing
**Purpose**: Optimize performance and reduce waiting
**Implementation**: `ConcurrentContentAnalyzer`
**Features**:
- Real-time content analysis as scraping completes
- Batch processing for efficiency
- Configurable concurrency limits

### 6. Flexible Phase Completion
**Purpose**: Allow pipeline completion even with partial failures
**Implementation**: `FlexiblePhaseCompletion`
**Features**:
- Threshold-based completion (e.g., 80% success rate)
- Time-based completion for long-running phases
- Manual intervention points

## Pipeline Execution Flow

### Manual Pipeline Trigger
When a user manually triggers a pipeline run:

1. **Initialization**
   - Create `pipeline_execution` record with status 'running'
   - Initialize `pipeline_phase_status` entries for enabled phases
   - Start WebSocket broadcasting for real-time updates
   - Initialize state tracking for resumability

2. **Phase Orchestration**
   - Execute phases sequentially with dependency checking
   - Update phase status in database (pending → running → completed/failed)
   - Broadcast status updates via WebSocket
   - Handle phase failures with retry logic

3. **Gating Logic**
   - Each phase checks prerequisites before execution
   - Content Analysis only runs if:
     - Content is scraped (status = 'completed')
     - Domain has company profile
     - Content length > 100 characters
   - DSI Calculation only runs if all dependencies are met

4. **Monitoring**
   - Pipeline monitor checks for stuck phases every 60 seconds
   - Timeout detection based on phase-specific limits
   - Automatic recovery attempts for common failures
   - Alerting for manual intervention when needed

5. **Completion**
   - Pipeline marked as 'completed' only if all critical phases succeed
   - Critical phases: SERP Collection, Content Scraping, Content Analysis, DSI Calculation
   - Partial success allowed for YouTube enrichment (network restrictions)
   - Final status broadcast and cleanup

## Monitoring and Status

### Real-time Monitoring
- **WebSocket Updates**: Live status updates to frontend
- **Phase Progress**: Granular progress tracking per phase
- **Error Reporting**: Real-time error notifications
- **Performance Metrics**: API call counts, timing, costs

### Database Monitoring
- **Pipeline Executions**: High-level pipeline status and metrics
- **Phase Status**: Detailed phase-by-phase tracking
- **State Tracking**: Item-level progress for resumability
- **Result Counts**: Metrics for each phase (keywords processed, companies enriched, etc.)

### Health Checks
- **Timeout Detection**: Phase-specific timeout monitoring
- **Stuck Pipeline Detection**: Overall pipeline runtime limits
- **Dependency Validation**: Ensure prerequisites are met
- **Resource Monitoring**: API quota and rate limit tracking

## Configuration

### Pipeline Config
```python
class PipelineConfig:
    client_id: str = "system"
    keywords: Optional[List[str]] = None
    regions: List[str] = ["US", "UK", "DE", "SA", "VN"]
    content_types: List[str] = ["organic", "news", "video"]
    
    # Concurrency limits
    max_concurrent_serp: int = 10
    max_concurrent_enrichment: int = 15
    max_concurrent_analysis: int = 20
    
    # Feature flags
    enable_keyword_metrics: bool = True
    enable_serp_collection: bool = True
    enable_company_enrichment: bool = True
    enable_video_enrichment: bool = True
    enable_content_scraping: bool = True
    enable_content_analysis: bool = True
    enable_historical_tracking: bool = True
    enable_landscape_dsi: bool = True
```

### Timeout Configuration
```python
PHASE_TIMEOUTS = {
    "keyword_metrics": 30,      # minutes
    "serp_collection": 120,     # minutes
    "company_enrichment": 60,   # minutes
    "video_enrichment": 60,     # minutes
    "content_scraping": 180,    # minutes
    "content_analysis": 240,    # minutes
    "dsi_calculation": 30       # minutes
}
```

## Success Criteria

### Pipeline Success
A pipeline is considered successful when:
1. **SERP Collection**: Completed with results stored
2. **Company Enrichment**: Company profiles created for domains
3. **Content Scraping**: Web content scraped and stored
4. **Content Analysis**: AI analysis completed for scraped content
5. **DSI Calculation**: DSI scores calculated and rankings generated

### Phase Success Criteria
- **Keyword Metrics**: Keywords have search volume data
- **SERP Collection**: Search results stored with domains/URLs extracted
- **Company Enrichment**: Company profiles created (fallbacks allowed)
- **YouTube Enrichment**: Video metadata enriched (partial success allowed)
- **Content Scraping**: Content scraped and stored
- **Content Analysis**: AI analysis with business insights
- **DSI Calculation**: Scores calculated and rankings generated

## Error Handling

### Failure Categories
1. **Transient Failures**: Network issues, rate limits (retry with backoff)
2. **Configuration Errors**: Invalid API keys, missing settings (fail fast)
3. **Data Issues**: Invalid URLs, parsing errors (skip and continue)
4. **Resource Exhaustion**: API quotas, memory limits (graceful degradation)

### Recovery Strategies
1. **Automatic Retry**: Exponential backoff for transient failures
2. **Fallback Services**: DataForSEO for keyword metrics, proxy rotation for scraping
3. **Flexible Completion**: Allow pipeline success with partial failures
4. **Manual Intervention**: Alert operators for critical failures

## Performance Optimization

### Concurrency
- Configurable concurrency limits per phase
- Concurrent content analysis during scraping
- Batch processing for API efficiency

### Caching
- 24-hour keyword metrics caching
- 7-day video metadata caching
- Company profile caching with Redis
- SERP result deduplication

### Resource Management
- API quota monitoring and management
- Rate limiting for external services
- Memory-efficient batch processing
- Background task management

## Testing and Validation

### Testing Mode
- `testing_mode: true` forces full pipeline execution
- Configurable batch sizes for faster testing
- Skip rate limiting delays in test mode

### Validation
- Data quality checks at each phase
- Schema validation for API responses
- Consistency checks between phases
- Performance benchmarking

This comprehensive pipeline system ensures robust, scalable, and monitorable processing of digital landscape data with extensive error handling and recovery capabilities.

