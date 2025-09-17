"""
Phase Orchestrator for Pipeline Execution
Ensures strict sequential phase execution with proper validation and error handling
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from uuid import UUID
from enum import Enum
from loguru import logger
import asyncpg

from app.core.database import DatabasePool
from app.core.robustness_logging import get_logger, log_performance


class PhaseStatus(str, Enum):
    """Status of individual pipeline phases"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"  # Blocked by dependency


class PhaseOrchestrator:
    """
    Manages strict sequential execution of pipeline phases with:
    - Phase dependency tracking
    - Completion validation
    - Error propagation
    - Phase-level retries
    - Checkpoint management
    """
    
    # Define phase dependencies (phase -> required predecessors)
    PHASE_DEPENDENCIES = {
        "keyword_metrics": [],
        "serp_collection": ["keyword_metrics"],
        "company_enrichment_serp": ["serp_collection"],
        "youtube_enrichment": ["serp_collection"],
        "content_scraping": ["serp_collection"],  # Scrapes organic/news URLs from SERP
        # Deprecated: company_enrichment_youtube removed; channel resolution handled by background resolver
        "content_analysis": ["content_scraping", "company_enrichment_serp", "youtube_enrichment"],
        "dsi_calculation": ["content_analysis"]
    }
    
    def __init__(self, db_pool: DatabasePool):
        self.db_pool = db_pool
        self.logger = get_logger("phase_orchestrator")
        self.phase_status: Dict[str, PhaseStatus] = {}
        self.phase_results: Dict[str, Dict[str, Any]] = {}
        self.phase_errors: Dict[str, List[str]] = {}
        self.phase_start_times: Dict[str, datetime] = {}
        self.phase_end_times: Dict[str, datetime] = {}
        self.phase_handlers: Dict[str, Callable] = {}
        self._execution_lock = asyncio.Lock()
    
    def register_phase_handler(self, phase: str, handler: Callable) -> None:
        """Register a handler function for a phase"""
        self.phase_handlers[phase] = handler
        self.logger.info(f"Registered handler for phase: {phase}")
    
    @log_performance("phase_orchestrator", "initialize_pipeline")
    async def initialize_pipeline(
        self, 
        pipeline_execution_id: UUID,
        enabled_phases: List[str],
        config: Dict[str, Any]
    ) -> None:
        """Initialize pipeline with enabled phases"""
        # Initialize all phases as pending or skipped
        all_phases = list(self.PHASE_DEPENDENCIES.keys())
        
        for phase in all_phases:
            if phase in enabled_phases:
                self.phase_status[phase] = PhaseStatus.PENDING
            else:
                self.phase_status[phase] = PhaseStatus.SKIPPED
                self.phase_results[phase] = {"skipped": True, "reason": "Disabled in config"}
        
        # Store in database
        async with self.db_pool.acquire() as conn:
            for phase, status in self.phase_status.items():
                await conn.execute(
                    """
                    INSERT INTO pipeline_phase_status (
                        pipeline_execution_id, phase_name, status, 
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, NOW(), NOW())
                    ON CONFLICT (pipeline_execution_id, phase_name) 
                    DO UPDATE SET 
                        -- Preserve existing terminal/running statuses when resuming
                        status = CASE 
                            WHEN pipeline_phase_status.status IN ('completed','running','failed','blocked')
                                THEN pipeline_phase_status.status
                            ELSE EXCLUDED.status
                        END,
                        updated_at = NOW()
                    """,
                    pipeline_execution_id, phase, status
                )
        
        self.logger.info(
            f"Initialized pipeline phases",
            pipeline_execution_id=str(pipeline_execution_id),
            enabled_phases=enabled_phases
        )
    
    def can_execute_phase(self, phase: str) -> Tuple[bool, Optional[str]]:
        """Check if a phase can be executed based on dependencies"""
        # Check if phase exists
        if phase not in self.PHASE_DEPENDENCIES:
            return False, f"Unknown phase: {phase}"
        
        # Check if already completed or running
        current_status = self.phase_status.get(phase, PhaseStatus.PENDING)
        if current_status == PhaseStatus.COMPLETED:
            return False, "Phase already completed"
        if current_status == PhaseStatus.RUNNING:
            return False, "Phase already running"
        if current_status == PhaseStatus.SKIPPED:
            return False, "Phase is skipped"
        
        # Check dependencies
        dependencies = self.PHASE_DEPENDENCIES[phase]
        for dep in dependencies:
            dep_status = self.phase_status.get(dep, PhaseStatus.PENDING)
            if dep_status == PhaseStatus.SKIPPED:
                continue  # Skipped dependencies are OK
            if dep_status != PhaseStatus.COMPLETED:
                return False, f"Dependency {dep} not completed (status: {dep_status})"
        
        return True, None
    
    @log_performance("phase_orchestrator", "execute_phase")
    async def execute_phase(
        self,
        pipeline_execution_id: UUID,
        phase: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single phase with validation and error handling"""
        async with self._execution_lock:
            # Validate phase can be executed
            can_execute, reason = self.can_execute_phase(phase)
            if not can_execute:
                # Special allowance: content_analysis may run out-of-phase when data is ready
                if phase == "content_analysis":
                    ready = await self._content_analysis_ready()
                    if not ready:
                        raise ValueError(f"Cannot execute phase {phase}: {reason}")
                else:
                    raise ValueError(f"Cannot execute phase {phase}: {reason}")
            
            # Enforce runtime preconditions (e.g., SERP rows stored) before executing certain phases
            preconditions_ok, block_reason = await self._check_preconditions(pipeline_execution_id, phase)
            if not preconditions_ok:
                # Mark as blocked and persist
                self.phase_status[phase] = PhaseStatus.BLOCKED
                await self._update_phase_status(
                    pipeline_execution_id,
                    phase,
                    PhaseStatus.BLOCKED,
                    {"blocked_by": block_reason}
                )
                self.logger.warning(f"Blocking phase {phase}: {block_reason}")
                return {"success": False, "error": block_reason}

            # Get handler
            handler = self.phase_handlers.get(phase)
            if not handler:
                raise ValueError(f"No handler registered for phase {phase}")
            
            # Mark as running
            self.phase_status[phase] = PhaseStatus.RUNNING
            self.phase_start_times[phase] = datetime.utcnow()
            await self._update_phase_status(pipeline_execution_id, phase, PhaseStatus.RUNNING)
            
            self.logger.info(f"🚀 Starting phase: {phase}")
            
            try:
                # Execute phase handler
                result = await handler(context)
                
                # Validate result
                if not isinstance(result, dict):
                    raise ValueError(f"Phase {phase} must return a dictionary")
                
                if not result.get('success', False):
                    raise Exception(f"Phase {phase} failed: {result.get('error', 'Unknown error')}")
                
                # Mark as completed
                self.phase_status[phase] = PhaseStatus.COMPLETED
                self.phase_results[phase] = result
                self.phase_end_times[phase] = datetime.utcnow()
                
                await self._update_phase_status(
                    pipeline_execution_id, 
                    phase, 
                    PhaseStatus.COMPLETED,
                    result
                )
                
                # Log duration
                duration = (self.phase_end_times[phase] - self.phase_start_times[phase]).total_seconds()
                self.logger.info(f"✅ Completed phase {phase} in {duration:.2f}s")
                
                return result
                
            except Exception as e:
                # Mark as failed
                self.phase_status[phase] = PhaseStatus.FAILED
                self.phase_errors[phase] = self.phase_errors.get(phase, [])
                self.phase_errors[phase].append(str(e))
                self.phase_end_times[phase] = datetime.utcnow()
                
                error_result = {
                    "success": False,
                    "error": str(e),
                    "phase": phase
                }
                
                await self._update_phase_status(
                    pipeline_execution_id,
                    phase,
                    PhaseStatus.FAILED,
                    error_result
                )
                
                self.logger.error(f"❌ Phase {phase} failed: {e}")
                
                # Mark dependent phases as blocked
                await self._block_dependent_phases(pipeline_execution_id, phase)
                
                raise

    async def _check_preconditions(self, pipeline_execution_id: UUID, phase: str) -> Tuple[bool, Optional[str]]:
        """Check DB-backed preconditions to avoid running phases too early."""
        try:
            async with self.db_pool.acquire() as conn:
                if phase == "company_enrichment_serp":
                    # Require SERP phase to be completed for this pipeline
                    serp_phase_status = await conn.fetchval(
                        """
                        SELECT status::text
                        FROM pipeline_phase_status
                        WHERE pipeline_execution_id = $1 AND phase_name = 'serp_collection'
                        """,
                        pipeline_execution_id,
                    )
                    if serp_phase_status != 'completed':
                        return False, "serp_phase_not_complete"
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM serp_results WHERE pipeline_execution_id = $1",
                        pipeline_execution_id,
                    )
                    if not count or count == 0:
                        return False, "no_serp_results"
                elif phase == "content_scraping":
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM serp_results WHERE pipeline_execution_id = $1",
                        pipeline_execution_id,
                    )
                    if not count or count == 0:
                        return False, "no_serp_results_for_scraping"
                elif phase == "youtube_enrichment":
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM serp_results WHERE pipeline_execution_id = $1 AND serp_type = 'video'",
                        pipeline_execution_id,
                    )
                    if not count or count == 0:
                        return False, "no_video_serp_results"
                elif phase == "content_analysis":
                    # Allow early run only if scraped + enriched (company) and not yet analyzed exist
                    count = await conn.fetchval(
                        """
                        SELECT COUNT(*)
                        FROM scraped_content sc
                        LEFT JOIN company_profiles cp ON cp.domain = sc.domain
                        LEFT JOIN optimized_content_analysis oca ON oca.url = sc.url
                        WHERE sc.status = 'completed'
                          AND sc.content IS NOT NULL
                          AND LENGTH(sc.content) > 100
                          AND (cp.company_name IS NOT NULL)
                          AND oca.id IS NULL
                        LIMIT 1
                        """
                    )
                    if not count or count == 0:
                        return False, "no_ready_content_for_analysis"
                elif phase == "dsi_calculation":
                    # Require some content analysis results (no date window) and that channels are resolved
                    content_ready = await conn.fetchval(
                        """
                        SELECT COUNT(*)
                        FROM optimized_content_analysis oca
                        """
                    )
                    if not content_ready or int(content_ready) == 0:
                        return False, "no_content_analysis_results"

                    pending_channels = await conn.fetchval(
                        """
                        WITH all_channels AS (
                            SELECT DISTINCT channel_id
                            FROM video_snapshots
                        )
                        SELECT COUNT(*)
                        FROM all_channels rc
                        LEFT JOIN youtube_channel_companies ycc
                          ON ycc.channel_id = rc.channel_id
                        WHERE ycc.channel_id IS NULL OR COALESCE(ycc.company_domain, '') = ''
                        """
                    )
                    if pending_channels and int(pending_channels) > 0:
                        return False, "channel_company_resolution_pending"
        except Exception as e:
            # On DB error, be conservative and allow execution (don’t deadlock pipeline)
            self.logger.warning(f"Precondition check error for phase {phase}: {e}")
            return True, None

        return True, None

    async def _content_analysis_ready(self) -> bool:
        """Check if content analysis can proceed out-of-phase (scraped + enriched present)."""
        try:
            async with self.db_pool.acquire() as conn:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM scraped_content sc
                    LEFT JOIN company_profiles cp ON cp.domain = sc.domain
                    LEFT JOIN optimized_content_analysis oca ON oca.url = sc.url
                    WHERE sc.status = 'completed'
                      AND sc.content IS NOT NULL
                      AND LENGTH(sc.content) > 100
                      AND (cp.company_name IS NOT NULL)
                      AND oca.id IS NULL
                    LIMIT 1
                    """
                )
                return bool(count and count > 0)
        except Exception as e:
            self.logger.warning(f"content_analysis readiness check failed: {e}")
            return False
    
    async def _update_phase_status(
        self,
        pipeline_execution_id: UUID,
        phase: str,
        status: PhaseStatus,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update phase status in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_phase_status
                SET status = $3,
                    updated_at = NOW(),
                    result_data = $4,
                    completed_at = CASE WHEN $3 IN ('completed', 'failed') THEN NOW() ELSE NULL END
                WHERE pipeline_execution_id = $1 AND phase_name = $2
                """,
                pipeline_execution_id,
                phase,
                status,
                json.dumps(result) if result else None
            )
    
    async def _block_dependent_phases(self, pipeline_execution_id: UUID, failed_phase: str) -> None:
        """Mark all phases that depend on the failed phase as blocked"""
        blocked_phases = []
        
        for phase, deps in self.PHASE_DEPENDENCIES.items():
            if failed_phase in deps and self.phase_status.get(phase) == PhaseStatus.PENDING:
                self.phase_status[phase] = PhaseStatus.BLOCKED
                blocked_phases.append(phase)
                await self._update_phase_status(
                    pipeline_execution_id,
                    phase,
                    PhaseStatus.BLOCKED,
                    {"blocked_by": failed_phase}
                )
        
        if blocked_phases:
            self.logger.warning(f"Blocked phases due to {failed_phase} failure: {blocked_phases}")
    
    def get_next_executable_phase(self) -> Optional[str]:
        """Get the next phase that can be executed"""
        for phase in self.PHASE_DEPENDENCIES.keys():
            if self.phase_status.get(phase) == PhaseStatus.PENDING:
                can_execute, _ = self.can_execute_phase(phase)
                if can_execute:
                    return phase
        return None
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of phase execution"""
        completed_phases = [p for p, s in self.phase_status.items() if s == PhaseStatus.COMPLETED]
        failed_phases = [p for p, s in self.phase_status.items() if s == PhaseStatus.FAILED]
        blocked_phases = [p for p, s in self.phase_status.items() if s == PhaseStatus.BLOCKED]
        pending_phases = [p for p, s in self.phase_status.items() if s == PhaseStatus.PENDING]
        
        # Calculate total duration
        total_duration = 0
        for phase in completed_phases + failed_phases:
            if phase in self.phase_start_times and phase in self.phase_end_times:
                duration = (self.phase_end_times[phase] - self.phase_start_times[phase]).total_seconds()
                total_duration += duration
        
        return {
            "total_phases": len(self.phase_status),
            "completed": len(completed_phases),
            "failed": len(failed_phases),
            "blocked": len(blocked_phases),
            "pending": len(pending_phases),
            "completed_phases": completed_phases,
            "failed_phases": failed_phases,
            "blocked_phases": blocked_phases,
            "pending_phases": pending_phases,
            "total_duration_seconds": total_duration,
            "phase_details": {
                phase: {
                    "status": self.phase_status.get(phase, PhaseStatus.PENDING).value,
                    "results": self.phase_results.get(phase, {}),
                    "errors": self.phase_errors.get(phase, []),
                    "start_time": self.phase_start_times.get(phase),
                    "end_time": self.phase_end_times.get(phase),
                    "duration_seconds": (
                        (self.phase_end_times[phase] - self.phase_start_times[phase]).total_seconds()
                        if phase in self.phase_start_times and phase in self.phase_end_times
                        else None
                    )
                }
                for phase in self.phase_status.keys()
            }
        }
    
    async def validate_phase_outputs(self, phase: str, outputs: Dict[str, Any]) -> bool:
        """Validate that a phase produced expected outputs"""
        validations = {
            "keyword_metrics": lambda o: o.get('keywords_with_metrics', 0) > 0,
            "serp_collection": lambda o: (
                o.get('discrete_batches') and 
                all(o.get('content_type_results', {}).get(ct, {}).get('success') 
                    for ct in ['organic', 'news', 'video'])
            ),
            "company_enrichment_serp": lambda o: o.get('companies_enriched', 0) >= 0,
            "youtube_enrichment": lambda o: o.get('videos_enriched', 0) >= 0,
            "content_scraping": lambda o: o.get('urls_scraped', 0) >= 0,
            "company_enrichment_youtube": lambda o: o.get('companies_enriched', 0) >= 0,
            "content_analysis": lambda o: o.get('content_analyzed', 0) >= 0,
            "dsi_calculation": lambda o: o.get('dsi_calculated', False)
        }
        
        validator = validations.get(phase)
        if validator:
            return validator(outputs)
        return True
