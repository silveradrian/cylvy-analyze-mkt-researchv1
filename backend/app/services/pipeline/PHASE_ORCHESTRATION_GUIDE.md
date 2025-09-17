# Pipeline Phase Orchestration Integration Guide

## Overview
The PhaseOrchestrator ensures strict sequential execution of pipeline phases with proper validation and error handling.

## Integration Steps

### 1. Run Database Migration
```bash
docker exec cylvy-analyze-mkt-analysis-db-1 psql -U cylvy -d cylvy_analyzer -f /migrations/add_phase_status_table.sql
```

### 2. Update Pipeline Service

Add PhaseOrchestrator to pipeline initialization:
```python
from app.services.robustness import PhaseOrchestrator

class UnifiedPipelineService:
    def __init__(self, ...):
        # ... existing init code ...
        self.phase_orchestrator = PhaseOrchestrator(db_pool)
        
        # Register phase handlers
        self._register_phase_handlers()
    
    def _register_phase_handlers(self):
        """Register all phase handlers with orchestrator"""
        self.phase_orchestrator.register_phase_handler(
            "keyword_metrics", 
            self._execute_keyword_metrics_enrichment_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "serp_collection",
            self._execute_serp_collection_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "company_enrichment_serp",
            self._execute_company_enrichment_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "youtube_enrichment",
            self._execute_video_enrichment_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "content_scraping",
            self._execute_content_scraping_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "content_analysis",
            self._execute_content_analysis_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "dsi_calculation",
            self._execute_dsi_calculation_phase
        )
```

### 3. Replace Current Pipeline Execution

Replace the current `_execute_pipeline` method with orchestrated execution:

```python
async def _execute_pipeline(self, pipeline_id: UUID, config: PipelineConfig):
    """Execute pipeline phases using PhaseOrchestrator"""
    result = self._active_pipelines[pipeline_id]
    
    try:
        # Initialize phase orchestrator
        enabled_phases = self._get_enabled_phases(config)
        await self.phase_orchestrator.initialize_pipeline(
            pipeline_id, 
            enabled_phases,
            config.dict()
        )
        
        # Execute phases sequentially
        context = {
            "pipeline_id": pipeline_id,
            "config": config,
            "db": self.db
        }
        
        while True:
            # Get next executable phase
            next_phase = self.phase_orchestrator.get_next_executable_phase()
            if not next_phase:
                break
            
            # Execute phase
            try:
                phase_result = await self.phase_orchestrator.execute_phase(
                    pipeline_id,
                    next_phase,
                    context
                )
                
                # Update pipeline result
                result.phase_results[next_phase] = phase_result
                
                # Update context with phase outputs for next phases
                context[f"{next_phase}_result"] = phase_result
                
            except Exception as e:
                logger.error(f"Phase {next_phase} failed: {e}")
                # PhaseOrchestrator handles blocking dependent phases
                break
        
        # Get final summary
        summary = self.phase_orchestrator.get_execution_summary()
        
        if summary["failed"] > 0:
            result.status = PipelineStatus.FAILED
        else:
            result.status = PipelineStatus.COMPLETED
            
    except Exception as e:
        result.status = PipelineStatus.FAILED
        result.errors.append(str(e))
```

### 4. Update Phase Methods

Each phase method needs to return a standardized result:

```python
async def _execute_keyword_metrics_enrichment_phase(self, context: Dict) -> Dict:
    """Execute keyword metrics phase"""
    config = context["config"]
    pipeline_id = context["pipeline_id"]
    
    try:
        # ... existing phase logic ...
        
        return {
            "success": True,
            "keywords_with_metrics": count,
            "country_results": results,
            # ... other metrics
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

## Phase Dependencies

The default phase dependencies are (strictly enforced):

1. **keyword_metrics** → (no dependencies)
2. **serp_collection** → keyword_metrics
3. **company_enrichment_serp** → serp_collection (must have stored SERP results)
4. **youtube_enrichment** → serp_collection  
5. **content_scraping** → serp_collection
6. **company_enrichment_youtube** → youtube_enrichment, company_enrichment_serp
7. **content_analysis** → content_scraping, company_enrichment_serp, youtube_enrichment
8. **dsi_calculation** → content_analysis, company_enrichment_youtube

## Monitoring Phase Execution

Query phase status:
```sql
-- View current phase status
SELECT 
    phase_name,
    status,
    started_at,
    completed_at,
    EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds,
    result_data->>'success' as success
FROM pipeline_phase_status
WHERE pipeline_execution_id = 'YOUR_PIPELINE_ID'
ORDER BY created_at;

-- View blocked phases
SELECT phase_name, result_data->>'blocked_by' as blocked_by
FROM pipeline_phase_status
WHERE status = 'blocked'
AND pipeline_execution_id = 'YOUR_PIPELINE_ID';
```

## Benefits

1. **Strict Sequential Execution** - Phases run in correct order
2. **Automatic Failure Handling** - Dependent phases blocked on failure
3. **Better Observability** - Track each phase's progress and duration
4. **Easier Debugging** - Clear phase status and error tracking
5. **Resume Capability** - Can potentially resume from failed phase


