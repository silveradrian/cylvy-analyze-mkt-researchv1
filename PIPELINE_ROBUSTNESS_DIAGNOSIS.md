# Pipeline Robustness Services - Diagnosis & Fixes

## Current State: You Have the Tools, But They're Not Working

### 1. PipelineMonitor Issue
The monitor exists but isn't detecting stuck pipelines:
- No monitor logs in output
- Pipeline stuck for hours without recovery
- May be failing to start due to missing imports or initialization errors

### 2. RetryManager Integration
- Only used for video enrichment (`retry_manager.retry_with_backoff`)
- NOT used for company enrichment phase where failures occur
- Has sophisticated error categorization but not leveraged

### 3. CircuitBreaker Protection
- Initialized for SERP and YouTube APIs
- Disabled for Cognism/company enrichment (line 179: `circuit_breaker=None`)
- This leaves company enrichment vulnerable to cascading failures

### 4. Double Domain Filtering Bug
```python
# First filter (line 775-794)
domains_to_enrich = [d for d in serp_domains if d not in existing_domains]

# Second filter inside _execute_company_enrichment_phase (line 1499-1510)
domains_to_enrich = [d for d in domains if d not in existing_set]
```
This could result in empty domain lists or race conditions.

## Immediate Fixes

### 1. Fix PipelineMonitor Startup
```python
# In main.py, add error details:
try:
    from app.services.robustness.pipeline_monitor import pipeline_monitor
    logger.info("Starting pipeline health monitor...")
    await pipeline_monitor.start_monitoring()
    app.state.pipeline_monitor = pipeline_monitor
    logger.info("✅ Pipeline monitor started successfully")
except Exception as e:
    logger.error(f"❌ Failed to start pipeline monitor: {e}", exc_info=True)
    # Don't let the app start without monitoring
    raise
```

### 2. Add RetryManager to Company Enrichment
```python
# In _execute_company_enrichment_phase:
async def enrich_domain_with_retry(domain: str):
    async def _enrich():
        return await self.company_enricher.enrich_domain(domain)
    
    return await self.retry_manager.retry_with_backoff(
        _enrich,
        entity_type='domain',
        entity_id=domain,
        operation='enrich_domain'
    )

# Replace line 1524:
result = await enrich_domain_with_retry(domain)
```

### 3. Enable CircuitBreaker for Company Enrichment
```python
# Line 179, change from:
self.company_enricher = EnhancedCompanyEnricher(settings, db, circuit_breaker=None, retry_manager=self.retry_manager)

# To:
self.company_enricher = EnhancedCompanyEnricher(
    settings, db, 
    circuit_breaker=self.circuit_breaker_manager.get_breaker("cognism_api", failure_threshold=10),
    retry_manager=self.retry_manager
)
```

### 4. Fix Double Domain Filtering
Remove the second filter in `_execute_company_enrichment_phase` since filtering is already done before calling it.

### 5. Add Comprehensive Error Details
```python
# Replace generic exception handler (line 1105):
except Exception as e:
    import traceback
    error_details = {
        'error_type': type(e).__name__,
        'error_message': str(e),
        'traceback': traceback.format_exc(),
        'phase': result.current_phase if hasattr(result, 'current_phase') else 'unknown',
        'pipeline_id': str(pipeline_id)
    }
    
    logger.error(f"Pipeline {pipeline_id} failed", extra=error_details)
    
    result.status = PipelineStatus.FAILED
    result.completed_at = datetime.utcnow()
    result.errors.append(json.dumps(error_details))
    
    # Trigger recovery attempt
    if hasattr(self, 'pipeline_monitor'):
        await self.pipeline_monitor.handle_pipeline_failure(pipeline_id, error_details)
```

## Long-term Solution: Pipeline Orchestration Service

Create a new service that properly uses all robustness features:

```python
# backend/app/services/pipeline/robust_pipeline_orchestrator.py
class RobustPipelineOrchestrator:
    def __init__(self):
        self.retry_manager = RetryManager(db_pool)
        self.circuit_breaker_manager = CircuitBreakerManager(db_pool)
        self.phase_orchestrator = PhaseOrchestrator(db_pool)
        self.pipeline_monitor = PipelineMonitor()
        
    async def execute_phase_with_protection(self, phase_name: str, phase_func: Callable):
        """Execute a phase with full protection"""
        
        # 1. Check circuit breaker
        breaker = self.circuit_breaker_manager.get_breaker(f"{phase_name}_breaker")
        if not await breaker.can_execute():
            raise CircuitBreakerOpen(f"{phase_name} circuit breaker is open")
        
        # 2. Execute with retry
        try:
            result = await self.retry_manager.retry_with_backoff(
                phase_func,
                entity_type='phase',
                entity_id=phase_name,
                max_retries=3
            )
            
            # 3. Record success
            await breaker.record_success()
            return result
            
        except Exception as e:
            # 4. Record failure
            await breaker.record_failure()
            
            # 5. Check if recoverable
            if self.retry_manager.is_recoverable_error(e):
                # Schedule for retry
                await self.schedule_phase_retry(phase_name, e)
            else:
                # Non-recoverable, fail fast
                raise
                
    async def schedule_phase_retry(self, phase_name: str, error: Exception):
        """Schedule a phase for retry with exponential backoff"""
        retry_delay = self.retry_manager.calculate_retry_delay(phase_name, error)
        await self.job_queue_manager.enqueue_job(
            job_type='phase_retry',
            payload={'phase_name': phase_name},
            scheduled_for=datetime.utcnow() + timedelta(seconds=retry_delay),
            priority=JobPriority.HIGH
        )
```

## Monitoring & Alerting

Add Prometheus metrics:
```python
# backend/app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

pipeline_phase_duration = Histogram(
    'pipeline_phase_duration_seconds',
    'Time spent in pipeline phases',
    ['phase', 'status']
)

pipeline_failures = Counter(
    'pipeline_failures_total',
    'Total pipeline failures',
    ['phase', 'error_type']
)

stuck_pipelines = Gauge(
    'stuck_pipelines',
    'Number of stuck pipelines'
)
```

## Configuration for Reliability

```yaml
# config/pipeline_reliability.yaml
pipeline:
  phase_timeouts:
    keyword_metrics: 1800  # 30 minutes
    serp_collection: 7200  # 2 hours
    company_enrichment: 3600  # 1 hour
    content_scraping: 10800  # 3 hours
    content_analysis: 14400  # 4 hours
    dsi_calculation: 1800  # 30 minutes
    
  retry_config:
    max_retries: 3
    backoff_multiplier: 2
    max_backoff: 300  # 5 minutes
    
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 300
    
  monitoring:
    check_interval: 60  # Check every minute
    stuck_threshold: 1800  # Consider stuck after 30 minutes
    alert_channels:
      - slack
      - email
```

## Why This Will Work

1. **Active Monitoring**: Pipeline monitor will actively check and recover stuck pipelines
2. **Retry Logic**: Every external call will have retry protection
3. **Circuit Breaking**: Prevents cascade failures when external services are down
4. **Detailed Logging**: You'll know exactly what failed and why
5. **Automatic Recovery**: Failed phases can be retried without manual intervention
6. **Progress Persistence**: Checkpointing ensures you don't lose progress

The tools are there - they just need to be properly connected and activated!
