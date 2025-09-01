"""
WebSocket service for real-time updates
"""
import asyncio
import json
from typing import Dict, Set, Any
from uuid import UUID
from datetime import datetime

from fastapi import WebSocket
from loguru import logger


class WebSocketService:
    """Manages WebSocket connections and broadcasting"""
    
    def __init__(self):
        # Store active connections by channel
        self._connections: Dict[str, Set[WebSocket]] = {}
        # Store connection metadata
        self._connection_info: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str, user_id: Optional[str] = None):
        """Connect a WebSocket to a channel"""
        await websocket.accept()
        
        # Add to channel
        if channel not in self._connections:
            self._connections[channel] = set()
        self._connections[channel].add(websocket)
        
        # Store metadata
        self._connection_info[websocket] = {
            "channel": channel,
            "user_id": user_id,
            "connected_at": datetime.utcnow()
        }
        
        logger.info(f"WebSocket connected to channel '{channel}' (user: {user_id})")
    
    async def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket"""
        if websocket not in self._connection_info:
            return
        
        info = self._connection_info[websocket]
        channel = info["channel"]
        
        # Remove from channel
        if channel in self._connections:
            self._connections[channel].discard(websocket)
            if not self._connections[channel]:
                del self._connections[channel]
        
        # Remove metadata
        del self._connection_info[websocket]
        
        logger.info(f"WebSocket disconnected from channel '{channel}'")
    
    async def send_to_connection(self, websocket: WebSocket, data: Dict[str, Any]):
        """Send data to a specific connection"""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
            await self.disconnect(websocket)
    
    async def broadcast_to_channel(self, channel: str, data: Dict[str, Any]):
        """Broadcast data to all connections in a channel"""
        if channel not in self._connections:
            return
        
        # Create tasks for all connections
        tasks = []
        connections_to_remove = []
        
        for websocket in self._connections[channel].copy():
            try:
                task = asyncio.create_task(websocket.send_json(data))
                tasks.append(task)
            except Exception as e:
                logger.warning(f"Failed to create send task for WebSocket: {e}")
                connections_to_remove.append(websocket)
        
        # Execute all sends concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check for failed connections
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    websocket = list(self._connections[channel])[i]
                    connections_to_remove.append(websocket)
                    logger.warning(f"WebSocket send failed: {result}")
        
        # Clean up failed connections
        for websocket in connections_to_remove:
            await self.disconnect(websocket)
    
    async def broadcast_pipeline_update(self, pipeline_id: UUID, message: str, data: Dict[str, Any] = None):
        """Broadcast pipeline status update"""
        payload = {
            "type": "pipeline_update",
            "pipeline_id": str(pipeline_id),
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        # Broadcast to pipeline-specific channel
        await self.broadcast_to_channel(f"pipeline_{pipeline_id}", payload)
        
        # Also broadcast to general pipeline channel
        await self.broadcast_to_channel("pipeline", payload)
    
    async def broadcast_schedule_update(self, schedule_id: UUID, event: str, data: Dict[str, Any] = None):
        """Broadcast schedule event"""
        payload = {
            "type": "schedule_update",
            "schedule_id": str(schedule_id),
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        await self.broadcast_to_channel("schedules", payload)
    
    async def broadcast_system_notification(self, message: str, level: str = "info", data: Dict[str, Any] = None):
        """Broadcast system-wide notification"""
        payload = {
            "type": "system_notification",
            "message": message,
            "level": level,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        await self.broadcast_to_channel("system", payload)
    
    def get_connection_count(self, channel: str = None) -> int:
        """Get connection count for a channel or total"""
        if channel:
            return len(self._connections.get(channel, set()))
        return sum(len(connections) for connections in self._connections.values())
    
    def get_active_channels(self) -> List[str]:
        """Get list of active channels"""
        return list(self._connections.keys())
    
    def get_channel_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all channels"""
        return {
            channel: {
                "connection_count": len(connections),
                "connections": [
                    {
                        "user_id": self._connection_info.get(ws, {}).get("user_id"),
                        "connected_at": self._connection_info.get(ws, {}).get("connected_at")
                    }
                    for ws in connections
                ]
            }
            for channel, connections in self._connections.items()
        }
