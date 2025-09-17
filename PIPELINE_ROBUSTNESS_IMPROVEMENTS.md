# Pipeline Robustness Improvements

## Current Issues

1. **Generic Error Handling**: Pipeline fails with generic "COMPANY_ENRICHMENT" error without specific details
2. **No Automatic Recovery**: Requires manual intervention to resume failed pipelines
3. **Container Restarts**: Health check failures cause container restarts that interrupt pipelines
4. **No Progress Checkpointing**: When a phase fails, it restarts from the beginning
5. **Inefficient Processing**: Re-processes already enriched/scraped items

## Immediate Fixes

### 1. Fix Health Check (Already Done)
```dockerfile
# Add curl to Dockerfile for health checks
RUN apt-get update && apt-get install -y curl
```

### 2. Improve Error Handling
```python
# In pipeline_service.py - Add specific error handling for each phase
async def _execute_company_enrichment_phase(self, domains: List[str]) -> Dict[str, Any]:
    try:
        # ... existing code ...
    except asyncio.TimeoutError:
        logger.error(f"Company enrichment timed out after processing {processed} domains")
        raise PipelinePhaseError("COMPANY_ENRICHMENT", "Phase timed out", recoverable=True)
    except httpx.HTTPError as e:
        logger.error(f"HTTP error during enrichment: {e}")
        raise PipelinePhaseError("COMPANY_ENRICHMENT", f"API error: {e}", recoverable=True)
    except Exception as e:
        logger.error(f"Unexpected error in company enrichment: {e}", exc_info=True)
        raise PipelinePhaseError("COMPANY_ENRICHMENT", str(e), recoverable=False)
```

### 3. Add Automatic Retry Logic
```python
# In pipeline_service.py
async def _execute_phase_with_retry(self, phase_func, phase_name, max_retries=3):
    """Execute a phase with automatic retry logic"""
    for attempt in range(max_retries):
        try:
            return await phase_func()
        except PipelinePhaseError as e:
            if not e.recoverable or attempt == max_retries - 1:
                raise
            
            wait_time = (2 ** attempt) * 60  # Exponential backoff: 1, 2, 4 minutes
            logger.warning(f"Phase {phase_name} failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s")
            await asyncio.sleep(wait_time)
```

## Long-term Improvements

### 1. Implement Checkpointing
```python
# Save progress within phases
async def _execute_company_enrichment_phase_with_checkpoint(self, domains: List[str]) -> Dict[str, Any]:
    checkpoint_key = f"pipeline:{self.pipeline_id}:enrichment:checkpoint"
    
    # Load checkpoint
    checkpoint = await self.redis.get(checkpoint_key)
    start_index = checkpoint.get('processed_count', 0) if checkpoint else 0
    
    for i, domain in enumerate(domains[start_index:], start=start_index):
        try:
            await self.enrich_domain(domain)
            
            # Save checkpoint every 100 domains
            if i % 100 == 0:
                await self.redis.set(checkpoint_key, {
                    'processed_count': i,
                    'total_count': len(domains),
                    'last_domain': domain
                }, ex=86400)  # 24 hour expiry
        except Exception as e:
            logger.error(f"Failed to enrich domain {domain}: {e}")
            # Continue with next domain instead of failing entire phase
            continue
```

### 2. Add Pipeline Recovery Service
```python
# New service: pipeline_recovery_service.py
class PipelineRecoveryService:
    def __init__(self):
        self.check_interval = 300  # Check every 5 minutes
        
    async def start(self):
        """Start the recovery service"""
        while True:
            try:
                await self.check_and_recover_pipelines()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Recovery service error: {e}")
                
    async def check_and_recover_pipelines(self):
        """Check for stuck/failed pipelines and attempt recovery"""
        # Find pipelines stuck in "running" state for > 30 minutes
        stuck_pipelines = await self.db.fetch("""
            SELECT pe.id, pe.config, pps.phase_name, pps.attempt_count
            FROM pipeline_executions pe
            JOIN pipeline_phase_status pps ON pe.id = pps.pipeline_execution_id
            WHERE pe.status = 'running'
            AND pps.status = 'running'
            AND pps.updated_at < NOW() - INTERVAL '30 minutes'
        """)
        
        for pipeline in stuck_pipelines:
            if pipeline['attempt_count'] < 3:
                await self.resume_pipeline(pipeline['id'], pipeline['phase_name'])
```

### 3. Implement Batch Processing with Progress Tracking
```python
# Process domains in smaller batches
async def _process_domains_in_batches(self, domains: List[str], batch_size: int = 50):
    """Process domains in manageable batches"""
    total_batches = (len(domains) + batch_size - 1) // batch_size
    
    for i in range(0, len(domains), batch_size):
        batch = domains[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        await self._broadcast_status(
            self.pipeline_id, 
            f"Processing batch {batch_num}/{total_batches} ({len(batch)} domains)"
        )
        
        # Process batch with timeout
        try:
            async with asyncio.timeout(300):  # 5 minute timeout per batch
                await self._process_batch(batch)
        except asyncio.TimeoutError:
            logger.error(f"Batch {batch_num} timed out")
            # Continue with next batch
```

### 4. Add Comprehensive Monitoring
```python
# monitoring/pipeline_metrics.py
class PipelineMetrics:
    def __init__(self):
        self.metrics = {
            'pipeline_duration': Histogram('pipeline_duration_seconds', 'Pipeline execution time', ['phase']),
            'pipeline_failures': Counter('pipeline_failures_total', 'Pipeline failures', ['phase', 'error_type']),
            'pipeline_retries': Counter('pipeline_retries_total', 'Pipeline retry attempts', ['phase']),
            'domains_processed': Counter('domains_processed_total', 'Domains processed', ['operation']),
        }
        
    async def record_phase_duration(self, phase: str, duration: float):
        self.metrics['pipeline_duration'].labels(phase=phase).observe(duration)
        
    async def record_failure(self, phase: str, error_type: str):
        self.metrics['pipeline_failures'].labels(phase=phase, error_type=error_type).inc()
```

### 5. Implement Circuit Breaker Pattern
```python
# Prevent cascading failures
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        
    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise CircuitBreakerOpen("Service temporarily unavailable")
                
        try:
            result = await func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")
            raise
```

## Implementation Priority

1. **Immediate (Today)**:
   - ✅ Fix health check issue
   - Add detailed error logging with stack traces
   - Implement basic retry logic for company enrichment

2. **Short-term (This Week)**:
   - Add checkpointing for company enrichment phase
   - Implement batch processing with progress tracking
   - Add timeout handling for each phase

3. **Medium-term (Next Sprint)**:
   - Implement pipeline recovery service
   - Add comprehensive monitoring and alerting
   - Implement circuit breaker for external APIs

4. **Long-term**:
   - Add distributed tracing for debugging
   - Implement pipeline versioning for backward compatibility
   - Add A/B testing for pipeline optimizations

## Configuration Changes

Add these to your pipeline configuration:

```python
# config/pipeline_config.py
class PipelineConfig:
    # Existing fields...
    
    # Robustness settings
    max_retries: int = 3
    retry_backoff_base: int = 60  # seconds
    phase_timeout: int = 3600  # 1 hour per phase
    batch_size: int = 50
    checkpoint_interval: int = 100
    enable_auto_recovery: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300
```

## Monitoring Dashboard

Create a monitoring dashboard showing:
- Pipeline success/failure rates
- Average duration per phase
- Current running pipelines
- Stuck pipeline alerts
- Resource usage (CPU, memory, API rate limits)
- Error frequency by type

This will drastically reduce the need for manual intervention and make the pipeline self-healing.
