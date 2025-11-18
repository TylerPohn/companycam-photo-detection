"""WebSocket routes for real-time detection updates"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set
from uuid import UUID
import json
import asyncio

from src.services.redis_service import RedisService

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])


class ConnectionManager:
    """
    Manages WebSocket connections for real-time detection updates.
    Supports photo-based subscriptions and broadcasts.
    """

    def __init__(self):
        # Map of photo_id to set of active connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Map of websocket to subscribed photo_ids
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, photo_id: str):
        """Accept WebSocket connection and subscribe to photo updates"""
        await websocket.accept()

        # Add to photo subscription
        if photo_id not in self.active_connections:
            self.active_connections[photo_id] = set()
        self.active_connections[photo_id].add(websocket)

        # Track subscription
        if websocket not in self.subscriptions:
            self.subscriptions[websocket] = set()
        self.subscriptions[websocket].add(photo_id)

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection and clean up subscriptions"""
        # Remove from all photo subscriptions
        if websocket in self.subscriptions:
            for photo_id in self.subscriptions[websocket]:
                if photo_id in self.active_connections:
                    self.active_connections[photo_id].discard(websocket)
                    # Clean up empty photo subscriptions
                    if not self.active_connections[photo_id]:
                        del self.active_connections[photo_id]

            del self.subscriptions[websocket]

    async def subscribe(self, websocket: WebSocket, photo_id: str):
        """Subscribe websocket to additional photo updates"""
        if photo_id not in self.active_connections:
            self.active_connections[photo_id] = set()
        self.active_connections[photo_id].add(websocket)

        if websocket not in self.subscriptions:
            self.subscriptions[websocket] = set()
        self.subscriptions[websocket].add(photo_id)

    async def unsubscribe(self, websocket: WebSocket, photo_id: str):
        """Unsubscribe websocket from photo updates"""
        if photo_id in self.active_connections:
            self.active_connections[photo_id].discard(websocket)
            if not self.active_connections[photo_id]:
                del self.active_connections[photo_id]

        if websocket in self.subscriptions:
            self.subscriptions[websocket].discard(photo_id)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific websocket"""
        await websocket.send_json(message)

    async def broadcast_to_photo(self, photo_id: str, message: dict):
        """Broadcast message to all connections subscribed to a photo"""
        if photo_id in self.active_connections:
            disconnected = []

            for connection in self.active_connections[photo_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)

            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect(connection)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/detections/{photo_id}")
async def websocket_detection_updates(websocket: WebSocket, photo_id: UUID):
    """
    WebSocket endpoint for real-time detection updates.
    Clients connect and receive updates as detections complete.
    """
    photo_id_str = str(photo_id)

    await manager.connect(websocket, photo_id_str)

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            {
                "type": "connected",
                "photo_id": photo_id_str,
                "message": "Subscribed to detection updates",
            },
            websocket,
        )

        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "subscribe":
                # Subscribe to additional photo
                additional_photo_id = message.get("photo_id")
                if additional_photo_id:
                    await manager.subscribe(websocket, additional_photo_id)
                    await manager.send_personal_message(
                        {
                            "type": "subscribed",
                            "photo_id": additional_photo_id,
                        },
                        websocket,
                    )

            elif message.get("type") == "unsubscribe":
                # Unsubscribe from photo
                unsubscribe_photo_id = message.get("photo_id")
                if unsubscribe_photo_id:
                    await manager.unsubscribe(websocket, unsubscribe_photo_id)
                    await manager.send_personal_message(
                        {
                            "type": "unsubscribed",
                            "photo_id": unsubscribe_photo_id,
                        },
                        websocket,
                    )

            elif message.get("type") == "ping":
                # Respond to ping
                await manager.send_personal_message(
                    {"type": "pong"},
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)


async def publish_detection_update(photo_id: UUID, detection_data: dict):
    """
    Publish detection update to all subscribed clients.
    Called by detection processing services.
    """
    message = {
        "type": "detection_update",
        "photo_id": str(photo_id),
        "data": detection_data,
    }

    await manager.broadcast_to_photo(str(photo_id), message)


async def publish_detection_complete(photo_id: UUID, aggregated_result: dict):
    """
    Publish detection completion to all subscribed clients.
    Called when all detection types are complete.
    """
    message = {
        "type": "detection_complete",
        "photo_id": str(photo_id),
        "data": aggregated_result,
    }

    await manager.broadcast_to_photo(str(photo_id), message)
