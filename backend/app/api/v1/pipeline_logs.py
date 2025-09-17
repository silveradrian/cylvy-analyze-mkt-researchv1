"""
Pipeline log streaming endpoints
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger
import asyncio
import json
from collections import deque
from datetime import datetime

from app.core.database import db_pool

router = APIRouter()

# Store recent logs in memory for each pipeline
pipeline_logs = {}  # pipeline_id -> deque of log entries
MAX_LOG_ENTRIES = 1000

class LogStreamer:
    def __init__(self):
        self.active_connections = {}  # pipeline_id -> list of websockets
        
    async def connect(self, websocket: WebSocket, pipeline_id: str):
        await websocket.accept()
        if pipeline_id not in self.active_connections:
            self.active_connections[pipeline_id] = []
        self.active_connections[pipeline_id].append(websocket)
        
        # Send recent logs immediately
        if pipeline_id in pipeline_logs:
            recent_logs = list(pipeline_logs[pipeline_id])
            await websocket.send_json({
                "type": "history",
                "logs": recent_logs
            })
    
    def disconnect(self, websocket: WebSocket, pipeline_id: str):
        if pipeline_id in self.active_connections:
            self.active_connections[pipeline_id].remove(websocket)
            if not self.active_connections[pipeline_id]:
                del self.active_connections[pipeline_id]
    
    async def broadcast(self, pipeline_id: str, log_entry: dict):
        # Store in memory
        if pipeline_id not in pipeline_logs:
            pipeline_logs[pipeline_id] = deque(maxlen=MAX_LOG_ENTRIES)
        pipeline_logs[pipeline_id].append(log_entry)
        
        # Broadcast to connected clients
        if pipeline_id in self.active_connections:
            for connection in self.active_connections[pipeline_id]:
                try:
                    await connection.send_json({
                        "type": "log",
                        "entry": log_entry
                    })
                except:
                    # Connection might be closed
                    pass

log_streamer = LogStreamer()

# Function to be called from pipeline service to add logs
async def add_pipeline_log(pipeline_id: str, level: str, message: str, phase: Optional[str] = None):
    """Add a log entry for a pipeline"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        "phase": phase
    }
    await log_streamer.broadcast(pipeline_id, log_entry)

@router.websocket("/pipeline/{pipeline_id}/logs")
async def pipeline_log_stream(
    websocket: WebSocket,
    pipeline_id: UUID
):
    """WebSocket endpoint for streaming pipeline logs"""
    pipeline_id_str = str(pipeline_id)
    
    try:
        await log_streamer.connect(websocket, pipeline_id_str)
        
        # Keep connection alive
        while True:
            # Wait for any message from client (like ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        log_streamer.disconnect(websocket, pipeline_id_str)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        log_streamer.disconnect(websocket, pipeline_id_str)

@router.get("/pipeline/{pipeline_id}/logs")
async def get_pipeline_logs(
    pipeline_id: UUID,
    limit: int = Query(100, ge=1, le=1000)
):
    """Get recent logs for a pipeline"""
    pipeline_id_str = str(pipeline_id)
    
    if pipeline_id_str not in pipeline_logs:
        return {"logs": []}
    
    logs = list(pipeline_logs[pipeline_id_str])[-limit:]
    return {"logs": logs}
