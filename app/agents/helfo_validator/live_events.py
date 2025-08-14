# app/agents/helfo_validator/live_events.py
import asyncio
from typing import Dict, Set
from fastapi import WebSocket

SESSION_CONNECTIONS: Dict[str, Set[WebSocket]] = {}
SESSION_EVENTS: Dict[str, asyncio.Event] = {}  # NEW

async def connect(session_id: str, websocket: WebSocket):
    await websocket.accept()
    if session_id not in SESSION_CONNECTIONS:
        SESSION_CONNECTIONS[session_id] = set()
    SESSION_CONNECTIONS[session_id].add(websocket)

    # Signal that session has a WS connection
    if session_id not in SESSION_EVENTS:
        SESSION_EVENTS[session_id] = asyncio.Event()
    SESSION_EVENTS[session_id].set()

    print(f"[DEBUG] WS CONNECTED: session_id={session_id}, total_in_session={len(SESSION_CONNECTIONS[session_id])}")

def disconnect(session_id: str, websocket: WebSocket):
    if session_id in SESSION_CONNECTIONS:
        SESSION_CONNECTIONS[session_id].discard(websocket)
        if not SESSION_CONNECTIONS[session_id]:
            del SESSION_CONNECTIONS[session_id]
            SESSION_EVENTS.pop(session_id, None)  # cleanup event
    print(f"[DEBUG] WS DISCONNECTED: session_id={session_id}, remaining_in_session={len(SESSION_CONNECTIONS.get(session_id, []))}")

# Wait for a session to have at least one WS connection
async def wait_for_connection(session_id: str, timeout: float = 5.0):
    """Wait until a WebSocket connects for the given session_id."""
    import asyncio
    import time

    start = time.time()
    while session_id not in SESSION_CONNECTIONS or not SESSION_CONNECTIONS[session_id]:
        if time.time() - start > timeout:
            raise TimeoutError(f"Timeout waiting for WebSocket connection for session {session_id}.")
        await asyncio.sleep(0.05)

async def push_update(session_id: str, message: dict):
    connections = SESSION_CONNECTIONS.get(session_id, set())
    disconnected = []
    for ws in connections:
        try:
            await ws.send_json(message)
        except Exception as e:
            print(f"[ERROR] Failed to send WS message: {e}")
            disconnected.append(ws)
    for ws in disconnected:
        disconnect(session_id, ws)
