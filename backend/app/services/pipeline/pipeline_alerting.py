"""
Pipeline Alerting System
Monitors and alerts on long-running pipelines
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from loguru import logger
from app.core.database import DatabasePool


class PipelineAlerter:
    """Alerts on pipeline issues and long-running pipelines"""
    
    # Alert thresholds
    WARNING_THRESHOLD_HOURS = 6
    CRITICAL_THRESHOLD_HOURS = 12
    STUCK_THRESHOLD_HOURS = 24
    
    def __init__(self, db: DatabasePool):
        self.db = db
        self.alerted_pipelines: set = set()  # Track which pipelines we've alerted on
    
    async def check_long_running_pipelines(self) -> List[Dict[str, Any]]:
        """Check for pipelines running longer than thresholds"""
        async with self.db.acquire() as conn:
            # Get all running pipelines with runtime
            pipelines = await conn.fetch("""
                SELECT 
                    id,
                    status,
                    created_at,
                    EXTRACT(EPOCH FROM (NOW() - created_at))/3600 as hours_running,
                    EXTRACT(EPOCH FROM (NOW() - COALESCE(updated_at, created_at)))/60 as mins_since_update
                FROM pipeline_executions
                WHERE status IN ('running', 'pending')
                ORDER BY created_at
            """)
            
            alerts = []
            
            for pipeline in pipelines:
                pipeline_id = str(pipeline['id'])
                hours_running = pipeline['hours_running']
                
                # Determine alert level
                if hours_running >= self.STUCK_THRESHOLD_HOURS:
                    alert_level = 'CRITICAL'
                    message = f"Pipeline stuck for {hours_running:.1f} hours"
                elif hours_running >= self.CRITICAL_THRESHOLD_HOURS:
                    alert_level = 'CRITICAL'
                    message = f"Pipeline running for {hours_running:.1f} hours"
                elif hours_running >= self.WARNING_THRESHOLD_HOURS:
                    alert_level = 'WARNING'
                    message = f"Pipeline running for {hours_running:.1f} hours"
                else:
                    continue
                
                # Check if we should alert (only alert once per threshold)
                alert_key = f"{pipeline_id}:{alert_level}"
                if alert_key not in self.alerted_pipelines:
                    self.alerted_pipelines.add(alert_key)
                    
                    # Get additional context
                    context = await self._get_pipeline_context(conn, pipeline_id)
                    
                    alert = {
                        'pipeline_id': pipeline_id,
                        'alert_level': alert_level,
                        'message': message,
                        'hours_running': hours_running,
                        'mins_since_update': pipeline['mins_since_update'],
                        'created_at': pipeline['created_at'],
                        'context': context,
                        'recommended_action': self._get_recommended_action(hours_running, context)
                    }
                    
                    alerts.append(alert)
                    
                    # Log the alert
                    log_method = logger.critical if alert_level == 'CRITICAL' else logger.warning
                    log_method(f"Pipeline Alert: {message} (ID: {pipeline_id})")
            
            # Store alerts in database
            if alerts:
                await self._store_alerts(conn, alerts)
            
            return alerts
    
    async def _get_pipeline_context(self, conn, pipeline_id: str) -> Dict[str, Any]:
        """Get context about the pipeline's current state"""
        context = {}
        
        # Get phase information if available
        phase_status = await conn.fetch("""
            SELECT phase_name, status, progress, 
                   EXTRACT(EPOCH FROM (NOW() - updated_at))/60 as mins_since_update
            FROM pipeline_status
            WHERE pipeline_id = $1
            ORDER BY updated_at DESC
        """, pipeline_id)
        
        if phase_status:
            context['phases'] = [
                {
                    'name': p['phase_name'],
                    'status': p['status'],
                    'progress': float(p['progress']) if p['progress'] else 0,
                    'mins_since_update': p['mins_since_update']
                }
                for p in phase_status
            ]
            
            # Find stuck phase
            for phase in phase_status:
                if phase['status'] == 'running' and phase['mins_since_update'] > 60:
                    context['stuck_phase'] = phase['phase_name']
                    context['stuck_duration_mins'] = phase['mins_since_update']
                    break
        
        # Get progress metrics
        metrics = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM serp_results WHERE pipeline_execution_id = $1) as serp_count,
                (SELECT COUNT(*) FROM scraped_content WHERE pipeline_execution_id = $1) as scrape_count,
                (SELECT COUNT(DISTINCT oca.id) FROM optimized_content_analysis oca 
                 JOIN scraped_content sc ON oca.url = sc.url 
                 WHERE sc.pipeline_execution_id = $1) as analyzed_count,
                (SELECT COUNT(*) FROM dsi_scores WHERE pipeline_execution_id = $1) as dsi_count
        """, pipeline_id)
        
        context['metrics'] = dict(metrics) if metrics else {}
        
        return context
    
    def _get_recommended_action(self, hours_running: float, context: Dict[str, Any]) -> str:
        """Get recommended action based on pipeline state"""
        if hours_running >= self.STUCK_THRESHOLD_HOURS:
            return "Force complete or restart pipeline"
        
        stuck_phase = context.get('stuck_phase')
        if stuck_phase:
            if stuck_phase == 'content_analysis':
                return "Restart content analysis service"
            elif stuck_phase == 'content_scraping':
                return "Check scraping service and proxy health"
            else:
                return f"Investigate {stuck_phase} phase"
        
        if hours_running >= self.CRITICAL_THRESHOLD_HOURS:
            return "Review pipeline logs and consider intervention"
        
        return "Monitor pipeline progress"
    
    async def _store_alerts(self, conn, alerts: List[Dict[str, Any]]):
        """Store alerts in database for historical tracking"""
        try:
            await conn.executemany("""
                INSERT INTO pipeline_alerts (
                    pipeline_id, alert_level, message,
                    hours_running, context, recommended_action,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """, [
                (
                    alert['pipeline_id'],
                    alert['alert_level'],
                    alert['message'],
                    alert['hours_running'],
                    alert['context'],
                    alert['recommended_action']
                )
                for alert in alerts
            ])
        except Exception:
            # Table might not exist
            logger.warning("Could not store alerts in database")
    
    async def clear_completed_pipeline_alerts(self):
        """Clear alerts for pipelines that have completed"""
        async with self.db.acquire() as conn:
            completed = await conn.fetch("""
                SELECT id FROM pipeline_executions
                WHERE status IN ('completed', 'failed')
                AND id::text = ANY($1)
            """, [pid.split(':')[0] for pid in self.alerted_pipelines])
            
            for pipeline in completed:
                # Remove all alerts for this pipeline
                pipeline_id = str(pipeline['id'])
                self.alerted_pipelines = {
                    alert_key for alert_key in self.alerted_pipelines
                    if not alert_key.startswith(f"{pipeline_id}:")
                }


# Create alerts table
ALERTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id UUID NOT NULL,
    alert_level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    hours_running FLOAT NOT NULL,
    context JSONB DEFAULT '{}',
    recommended_action TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_pipeline ON pipeline_alerts(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON pipeline_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON pipeline_alerts(acknowledged);
"""
