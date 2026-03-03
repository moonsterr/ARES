"""
WebSocket Connection Manager
Maintains a registry of all connected frontend clients.
Provides broadcast methods for pushing events in real time.
"""
import asyncio
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger("ws_manager")


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.info(f"[WS] Client connected — total: {len(self._connections)}")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections = [c for c in self._connections if c is not ws]
        logger.info(f"[WS] Client disconnected — total: {len(self._connections)}")

    async def broadcast_json(self, data: dict):
        """Send a JSON payload to all connected clients."""
        if not self._connections:
            return
        message = json.dumps(data, default=str)
        dead: list[WebSocket] = []
        async with self._lock:
            clients = self._connections.copy()
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton instance — imported everywhere that needs to broadcast
manager = ConnectionManager()
