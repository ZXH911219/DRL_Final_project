import logging
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Any

from src.api.auth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total active: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/reasoning")
async def websocket_reasoning_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming of reasoning steps.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We receive message from client to start reasoning
            data = await websocket.receive_text()
            
            try:
                request_data = json.loads(data)
                
                # Stream responses
                await websocket.send_json({"type": "status", "message": "Reasoning pipeline initiated..."})
                
                for step in range(1, 6):
                    await asyncio.sleep(0.3)
                    await websocket.send_json({
                        "type": "reasoning_step",
                        "step": step,
                        "data": f"Evaluating logic sequence #{step}..."
                    })
                
                await websocket.send_json({
                    "type": "status",
                    "message": "Reasoning complete",
                    "completed": True
                })
            
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
