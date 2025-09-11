"""
Pipeline Phase Management - Ensures strict sequential execution
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger


class PipelinePhaseStatus(Enum):
    """Status of individual pipeline phases"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelinePhaseManager:
    """Manages sequential execution of pipeline phases"""
    
    def __init__(self):
        self.phases = [
            "keyword_metrics",
            "serp_collection",
            "company_enrichment_serp",
            "youtube_enrichment",
            "content_scraping",
            "company_enrichment_youtube",
            "content_analysis",
            "dsi_calculation"
        ]
        self.phase_status = {phase: PipelinePhaseStatus.PENDING for phase in self.phases}
        self.phase_results = {}
        self.phase_start_times = {}
        self.phase_end_times = {}
    
    def can_start_phase(self, phase: str) -> bool:
        """Check if a phase can start based on dependencies"""
        phase_index = self.phases.index(phase)
        
        # First phase can always start
        if phase_index == 0:
            return True
        
        # Check if all previous phases are completed
        for i in range(phase_index):
            prev_phase = self.phases[i]
            if self.phase_status[prev_phase] not in [PipelinePhaseStatus.COMPLETED, PipelinePhaseStatus.SKIPPED]:
                return False
        
        return True
    
    def start_phase(self, phase: str) -> bool:
        """Mark a phase as started"""
        if not self.can_start_phase(phase):
            logger.error(f"Cannot start phase {phase} - dependencies not met")
            return False
        
        self.phase_status[phase] = PipelinePhaseStatus.RUNNING
        self.phase_start_times[phase] = datetime.utcnow()
        logger.info(f"🚀 Started phase: {phase}")
        return True
    
    def complete_phase(self, phase: str, results: Dict[str, Any], success: bool = True):
        """Mark a phase as completed"""
        if success:
            self.phase_status[phase] = PipelinePhaseStatus.COMPLETED
            logger.info(f"✅ Completed phase: {phase}")
        else:
            self.phase_status[phase] = PipelinePhaseStatus.FAILED
            logger.error(f"❌ Failed phase: {phase}")
        
        self.phase_results[phase] = results
        self.phase_end_times[phase] = datetime.utcnow()
        
        # Log phase duration
        if phase in self.phase_start_times:
            duration = (self.phase_end_times[phase] - self.phase_start_times[phase]).total_seconds()
            logger.info(f"⏱️ Phase {phase} took {duration:.2f} seconds")
    
    def skip_phase(self, phase: str, reason: str):
        """Mark a phase as skipped"""
        self.phase_status[phase] = PipelinePhaseStatus.SKIPPED
        self.phase_results[phase] = {"skipped": True, "reason": reason}
        logger.info(f"⏩ Skipped phase: {phase} - {reason}")
    
    def get_completed_phases(self) -> List[str]:
        """Get list of completed phases"""
        return [
            phase for phase in self.phases 
            if self.phase_status[phase] == PipelinePhaseStatus.COMPLETED
        ]
    
    def get_phase_summary(self) -> Dict[str, Any]:
        """Get summary of all phase executions"""
        summary = {
            "total_phases": len(self.phases),
            "completed": len([p for p in self.phases if self.phase_status[p] == PipelinePhaseStatus.COMPLETED]),
            "failed": len([p for p in self.phases if self.phase_status[p] == PipelinePhaseStatus.FAILED]),
            "skipped": len([p for p in self.phases if self.phase_status[p] == PipelinePhaseStatus.SKIPPED]),
            "phase_details": {}
        }
        
        for phase in self.phases:
            summary["phase_details"][phase] = {
                "status": self.phase_status[phase].value,
                "results": self.phase_results.get(phase, {}),
                "start_time": self.phase_start_times.get(phase),
                "end_time": self.phase_end_times.get(phase)
            }
        
        return summary
    
    def validate_serp_completion(self, serp_results: Dict[str, Any], expected_content_types: List[str]) -> bool:
        """Validate that SERP collection completed for all content types"""
        if not serp_results.get('discrete_batches'):
            logger.error("SERP collection did not use discrete batches")
            return False
        
        content_results = serp_results.get('content_type_results', {})
        all_completed = True
        
        for content_type in expected_content_types:
            if content_type not in content_results:
                logger.error(f"Missing SERP results for content type: {content_type}")
                all_completed = False
            elif not content_results[content_type].get('success', False):
                logger.error(f"SERP collection failed for content type: {content_type}")
                all_completed = False
            else:
                batch_id = content_results[content_type].get('batch_id')
                results_count = content_results[content_type].get('results_stored', 0)
                logger.info(f"✅ {content_type}: Batch {batch_id} - {results_count} results stored")
        
        return all_completed


