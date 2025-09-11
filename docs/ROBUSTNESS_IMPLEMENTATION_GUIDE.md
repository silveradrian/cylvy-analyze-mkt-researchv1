# Pipeline Robustness Implementation Guide

## Overview

This guide documents the comprehensive robustness features implemented for the Cylvy Digital Landscape Analyzer pipeline. These features ensure reliable, fault-tolerant, and resumable pipeline operations at scale.

## Core Components Implemented

### 1. State Tracking (`backend/app/services/robustness/state_tracker.py`)

**Purpose**: Provides granular tracking of pipeline execution state, enabling resume from any point.

**Features**:
- Track individual items (keywords, domains, URLs) through each pipeline phase
- Support for pending, processing, completed, failed, and skipped states
- Checkpoint creation for recovery points
- Failed item tracking with error categorization
- Progress monitoring at phase and pipeline levels

**Key Methods**:
- `initialize_pipeline()`: Set up tracking for all items
- `get_pending_items()`: Retrieve items ready for processing
- `update_state()`: Update item processing status
- `create_checkpoint()`: Save recovery points
- `reset_failed_items()`: Retry failed items

### 2. Circuit Breaker (`backend/app/services/robustness/circuit_breaker.py`)

**Purpose**: Prevents cascade failures by temporarily blocking calls to failing services.

**States**:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Service is failing, requests are blocked
- **HALF_OPEN**: Testing if service recovered, limited requests

**Configuration**:
```python
# Example configuration for Scale SERP API
serp_breaker = CircuitBreakerManager.get_breaker(
    "scale_serp_api",
    failure_threshold=10,    # Trip after 10 failures
    success_threshold=5,     # Recover after 5 successes in HALF_OPEN
    timeout_seconds=300      # Try recovery after 5 minutes
)
```

### 3. Job Queue (`backend/app/services/robustness/job_queue.py`)

**Purpose**: Persistent background job processing with retry capabilities.

**Features**:
- Database-backed job persistence
- Priority-based processing
- Automatic retry with exponential backoff
- Dead letter queue for failed jobs
- Worker locking to prevent duplicate processing
- Batch job support

**Example Usage**:
```python
# Queue a SERP collection job
await job_queue.enqueue(
    job_type="collect_serp",
    payload={"keyword": "digital payments", "region": "US"},
    priority=JobPriority.HIGH,
    max_attempts=3
)
```

### 4. Retry Manager (`backend/app/services/robustness/retry_manager.py`)

**Purpose**: Intelligent retry logic with error categorization.

**Error Categories**:
- **Recoverable**: Rate limits, timeouts, temporary failures
- **Non-recoverable**: Authentication errors, bad requests
- **Degraded**: Partial success scenarios

**Retry Strategies**:
- Exponential backoff with jitter
- Linear backoff
- Constant delay
- No retry

### 5. Enhanced Logging (`backend/app/core/robustness_logging.py`)

**Purpose**: Detailed, configurable logging for debugging and monitoring.

**Features**:
- Component-specific logging toggles
- Performance metrics tracking
- API call logging with duration
- Memory usage monitoring
- Context-aware logging
- JSON and text format support

**Configuration (Environment Variables)**:
```bash
ROBUSTNESS_DEBUG_ENABLED=true
ROBUSTNESS_LOG_TO_FILE=true
ROBUSTNESS_LOG_CIRCUIT_BREAKER=true
ROBUSTNESS_LOG_JOB_QUEUE=true
ROBUSTNESS_LOG_PERFORMANCE_METRICS=true
```

## Monitoring API Endpoints

### Health Check
```
GET /api/v1/monitoring/health
```
Returns overall system health including circuit breaker states, job queue status, and error rates.

### Circuit Breakers
```
GET /api/v1/monitoring/circuit-breakers
POST /api/v1/monitoring/circuit-breakers/{service_name}/reset
```

### Pipeline Progress
```
GET /api/v1/monitoring/pipeline/{pipeline_id}/progress
GET /api/v1/monitoring/pipeline/{pipeline_id}/failed-items
POST /api/v1/monitoring/pipeline/{pipeline_id}/retry-failed
```

### Job Queues
```
GET /api/v1/monitoring/job-queues
POST /api/v1/monitoring/job-queues/{queue_name}/retry-dead-letter
```

### Retry Statistics
```
GET /api/v1/monitoring/retry-statistics
```

### Service Health Metrics
```
GET /api/v1/monitoring/service-health/{service_name}
```

## Enhanced Services

### 1. Enhanced Pipeline Service (`backend/app/services/pipeline/enhanced_pipeline_service.py`)

**New Features**:
- Integrated state tracking for all phases
- Circuit breaker protection for external APIs
- Job queue support for async processing
- Checkpoint creation for recovery
- Resume capability for failed pipelines
- Comprehensive metrics collection

**Resume Pipeline**:
```python
# Resume a failed pipeline
pipeline_service.resume_pipeline(
    pipeline_id=failed_pipeline_id,
    resume_failed_only=True  # Only retry failed items
)
```

### 2. Enhanced SERP Collector (`backend/app/services/serp/enhanced_serp_collector.py`)

**Improvements**:
- Circuit breaker integration
- Retry logic with backoff
- Enhanced logging with performance metrics
- Cache support for results
- Quota monitoring and reporting

### 3. Enhanced Company Enricher (`backend/app/services/enrichment/enhanced_company_enricher.py`)

**Improvements**:
- Circuit breaker for Cognism API
- Batch enrichment with progress tracking
- Enhanced error handling
- Performance logging

## Database Schema

The robustness implementation adds several new tables:

### pipeline_state
Tracks individual item states through the pipeline.

### circuit_breakers
Stores circuit breaker states and statistics.

### job_queue
Persistent job storage for background processing.

### error_categories
Configurable error handling rules.

### retry_history
Audit trail of retry attempts.

### service_health_metrics
Time-series metrics for service health.

### pipeline_checkpoints
Recovery points for pipeline execution.

## Configuration

### Pipeline Configuration
```python
config = PipelineConfig(
    # Robustness settings
    enable_state_tracking=True,
    enable_circuit_breakers=True,
    enable_job_queue=True,
    enable_checkpoints=True,
    checkpoint_interval=100,  # Create checkpoint every 100 items
    
    # Resume settings
    resume_from_pipeline_id=None,  # Set to resume existing pipeline
    resume_failed_only=True
)
```

### Circuit Breaker Defaults
- Scale SERP: 10 failures, 5 minute timeout
- Cognism: 5 failures, 10 minute timeout
- YouTube: 5 failures, 5 minute timeout
- OpenAI: 10 failures, 10 minute timeout
- ScrapingBee: 20 failures, 5 minute timeout

## Best Practices

### 1. Error Handling
- Always categorize errors appropriately
- Use specific error messages for debugging
- Log context with errors

### 2. Performance
- Use batch operations where possible
- Configure appropriate concurrency limits
- Monitor memory usage for large pipelines

### 3. Monitoring
- Check `/monitoring/health` regularly
- Set up alerts for circuit breaker trips
- Monitor job queue depths
- Track retry statistics

### 4. Recovery
- Create checkpoints at logical boundaries
- Test resume functionality regularly
- Keep failed item counts manageable

## Troubleshooting

### Circuit Breaker Open
1. Check service health metrics
2. Review error logs for root cause
3. Manually reset if service recovered: `POST /monitoring/circuit-breakers/{service}/reset`

### High Job Queue Depth
1. Check worker health
2. Review job processing times
3. Scale workers if needed
4. Check for poison messages in dead letter queue

### Pipeline Resume Issues
1. Verify checkpoint data integrity
2. Check state tracking records
3. Review failed item error categories
4. Use `/monitoring/pipeline/{id}/failed-items` to inspect

## Future Enhancements

The remaining tasks to complete the robustness implementation:

1. **YouTube Service Integration**: Add circuit breaker and retry logic
2. **Google Ads Service Integration**: Add circuit breaker and retry logic  
3. **OpenAI Service Integration**: Add circuit breaker and retry logic

These can be implemented following the same patterns as the SERP and Company enricher services.

## Testing

### Manual Testing
```bash
# Start a pipeline
curl -X POST http://localhost:8001/api/v1/pipeline/start \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["test"], "regions": ["US"]}'

# Check health
curl http://localhost:8001/api/v1/monitoring/health \
  -H "Authorization: Bearer <token>"

# View pipeline progress
curl http://localhost:8001/api/v1/monitoring/pipeline/{id}/progress \
  -H "Authorization: Bearer <token>"
```

### Load Testing
The robustness features are designed to handle high load:
- Circuit breakers prevent API overload
- Job queues smooth traffic spikes
- State tracking enables horizontal scaling

## Conclusion

The robustness implementation transforms the pipeline from a simple sequential processor to a enterprise-grade, fault-tolerant system capable of handling failures gracefully and recovering automatically. The monitoring endpoints provide full visibility into system health, while the state tracking ensures no data is lost even in catastrophic failures.
