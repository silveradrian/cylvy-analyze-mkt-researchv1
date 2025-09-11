# Scheduling & Robustness Integration Guide

## Overview

The pipeline scheduling system now integrates with the robust pipeline tracking and phase orchestration services to provide reliable, automated data collection.

## Integration Architecture

### 1. **Scheduling Service** → **Pipeline Service** → **Robustness Services**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│ SchedulingService│ -> │ PipelineService  │ -> │ Robustness Services │
│                 │    │                  │    │                     │
│ • Content Types │    │ • Phase Mgmt     │    │ • PhaseOrchestrator │
│ • Frequencies   │    │ • Config Mgmt    │    │ • StateTracker      │
│ • Timing        │    │ • Mode Handling  │    │ • CircuitBreakers   │
│ • Webhooks      │    │ • Testing Mode   │    │ • RetryManager      │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
```

### 2. **Robust Phase Orchestration**

The `PhaseOrchestrator` ensures strict sequential execution:

```python
PHASE_DEPENDENCIES = {
    "keyword_metrics": [],
    "serp_collection": ["keyword_metrics"],
    "company_enrichment_serp": ["serp_collection"],
    "youtube_enrichment": ["serp_collection"],
    "company_enrichment_youtube": ["youtube_enrichment", "company_enrichment_serp"],
    "content_analysis": ["company_enrichment_serp", "youtube_enrichment"],
    "dsi_calculation": ["content_analysis", "company_enrichment_youtube"]
}
```

## Integration Points

### 1. **Scheduled Pipeline Execution**

When a schedule triggers:

1. **SchedulingService** determines which content types are due
2. **PipelineService** starts with robust configuration:
   ```python
   config = PipelineConfig(
       content_types=content_types,
       force_refresh=True,  # Always refresh for scheduled runs
       enable_historical_tracking=True,
       scheduled_for=scheduled_for
   )
   ```
3. **PhaseOrchestrator** manages sequential phase execution
4. **StateTracker** provides granular progress tracking
5. **CircuitBreakers** protect external API calls

### 2. **ScaleSERP Integration**

ScaleSERP batches are created with:
- **Scheduling Parameters**: Daily/Weekly/Monthly frequencies
- **Circuit Breaker Protection**: API failure handling
- **Webhook Processing**: Automatic pipeline continuation
- **Retry Logic**: Failed batch recovery

### 3. **Content-Type Specific Processing**

Each content type (organic, news, video) runs independently:
- **Separate Batches**: Each type gets its own ScaleSERP batch
- **Individual Schedules**: Different frequencies per type
- **Phase Dependencies**: Proper sequencing maintained
- **State Isolation**: Progress tracked per content type

## Robustness Features in Scheduling

### 1. **Circuit Breaker Protection**

```python
# SERP collection protected by circuit breaker
serp_circuit_breaker = self.circuit_breaker_manager.get_breaker(
    "scale_serp_api",
    failure_threshold=10,
    success_threshold=5,
    timeout_seconds=300
)
```

### 2. **State Tracking & Resume**

```python
# Initialize state tracking for pipeline
await self.state_tracker.initialize_pipeline(
    pipeline_execution_id=pipeline_id,
    phases=phases,
    items=keywords
)

# Track progress at granular level
await self.state_tracker.update_item_status(
    pipeline_execution_id,
    phase,
    item_id,
    StateStatus.COMPLETED,
    result_data
)
```

### 3. **Retry Management**

```python
# Retry failed operations with exponential backoff
retry_strategy = RetryStrategy(
    max_attempts=3,
    base_delay=30,
    max_delay=300,
    exponential_base=2
)
```

### 4. **Job Queue Management**

```python
# Queue background jobs for processing
job = Job(
    job_type="serp_batch_processing",
    payload=batch_data,
    priority=JobPriority.HIGH,
    max_retries=3
)
await self.job_queue_manager.enqueue_job(job)
```

## Scheduling Modes & Robustness

### 1. **SCHEDULED Mode**
- Full robustness features enabled
- Phase orchestration with dependencies
- Automatic retry on failure
- State persistence for resume

### 2. **TESTING Mode**
- Limited batch size (5 keywords)
- All phases forced to run
- Circuit breakers still active
- Faster execution for development

### 3. **MANUAL Mode**
- User-triggered execution
- Full or partial phase execution
- Interactive monitoring
- Manual retry control

## Monitoring & Observability

### 1. **Pipeline Timeline View**
- Shows scheduled vs actual execution times
- Displays phase progress and dependencies
- Real-time status updates via WebSocket

### 2. **Phase Status Tracking**
```sql
-- Phase status in database
CREATE TABLE pipeline_phase_status (
    pipeline_execution_id UUID,
    phase_name VARCHAR(50),
    status VARCHAR(20),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER
);
```

### 3. **Circuit Breaker Monitoring**
```sql
-- Circuit breaker state tracking
CREATE TABLE circuit_breaker_events (
    breaker_name VARCHAR(100),
    event_type VARCHAR(20),
    occurred_at TIMESTAMP,
    failure_count INTEGER,
    state VARCHAR(20)
);
```

## Error Handling & Recovery

### 1. **Phase-Level Failures**
- Individual phases can fail without stopping entire pipeline
- Retry logic with exponential backoff
- Dependency blocking prevents cascade failures

### 2. **ScaleSERP Batch Failures**
- Circuit breaker opens on repeated failures
- Webhook timeout handling
- Batch retry with different parameters

### 3. **Schedule Recovery**
- Missed schedules detected and queued
- Backfill execution for critical data
- Schedule adjustment based on failure patterns

## Configuration Examples

### 1. **High-Frequency News Collection**
```python
{
    "content_type": "news",
    "frequency": "daily",
    "time_of_day": "09:00",
    "retry_attempts": 5,
    "circuit_breaker": {
        "failure_threshold": 3,
        "timeout_seconds": 60
    }
}
```

### 2. **Monthly Organic Collection**
```python
{
    "content_type": "organic",
    "frequency": "monthly",
    "day_of_month": 1,
    "batch_size": "unlimited",
    "retry_attempts": 3,
    "enable_historical_tracking": True
}
```

## Future Enhancements

1. **Adaptive Scheduling**: Adjust frequencies based on data freshness
2. **Load Balancing**: Distribute phases across multiple workers
3. **Predictive Retry**: ML-based retry strategy optimization
4. **Cost Optimization**: Dynamic batch sizing based on API quotas

This integration provides a robust, scalable foundation for automated competitive intelligence data collection with comprehensive error handling and monitoring capabilities.
