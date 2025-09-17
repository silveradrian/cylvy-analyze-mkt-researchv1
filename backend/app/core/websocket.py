"""
WebSocket endpoint for real-time updates
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid import UUID
from loguru import logger

from app.services.websocket_service import WebSocketService


router = APIRouter()
websocket_service = WebSocketService()


@router.websocket("/ws")
async def generic_websocket(websocket: WebSocket):
    """Generic WebSocket endpoint - redirects to pipeline channel silently"""
    try:
        await websocket_service.connect(websocket, "general")
        while True:
            # Just keep connection alive, minimal logging
            try:
                data = await websocket.receive_json()
                await websocket.send_json({"type": "connected", "channel": "general"})
            except Exception:
                break
    except WebSocketDisconnect:
        await websocket_service.disconnect(websocket)


@router.websocket("/ws/pipeline")
async def pipeline_websocket(websocket: WebSocket):
    """WebSocket endpoint for pipeline updates"""
    await websocket_service.connect(websocket, "pipeline")
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_json()
            # Echo back for now (could implement client commands)
            await websocket.send_json({"type": "ack", "data": data})
    except WebSocketDisconnect:
        await websocket_service.disconnect(websocket)


@router.websocket("/ws/pipeline/{pipeline_id}")
async def pipeline_specific_websocket(websocket: WebSocket, pipeline_id: UUID):
    """WebSocket endpoint for specific pipeline updates"""
    await websocket_service.connect(websocket, f"pipeline_{pipeline_id}")
    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"type": "ack", "pipeline_id": str(pipeline_id), "data": data})
    except WebSocketDisconnect:
        await websocket_service.disconnect(websocket)


@router.websocket("/ws/schedules")
async def schedules_websocket(websocket: WebSocket):
    """WebSocket endpoint for schedule updates"""
    await websocket_service.connect(websocket, "schedules")
    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"type": "ack", "data": data})
    except WebSocketDisconnect:
        await websocket_service.disconnect(websocket)


@router.websocket("/ws/system")
async def system_websocket(websocket: WebSocket):
    """WebSocket endpoint for system notifications"""
    await websocket_service.connect(websocket, "system")
    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"type": "ack", "data": data})
    except WebSocketDisconnect:
        await websocket_service.disconnect(websocket)
