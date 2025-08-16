import asyncio
import uuid
import os
import json
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import redis
from dotenv import load_dotenv

from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator
from app.schemas_new.agentic_state import RespondRequest, SubmitSOAPRequest

router = APIRouter()

# --- Load environment variables for Redis configuration ---
load_dotenv()
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# --- Initialize Redis client and pass it to the orchestrator ---
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    redis_client.ping() # Check connection
    print("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"Failed to connect to Redis: {e}. The application may not function correctly.")
    redis_client = None

agent_orchestrator = HelFoAgentOrchestrator(redis_client=redis_client)


# ----------------------------
# WebSocket Manager (Integrated)
# ----------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str):
        pid = os.getpid()
        print(f"[DEBUG][PID {pid}] WebSocket connect method called for session {session_id}")
        await websocket.accept()
        async with self._lock:
            self.active_connections.setdefault(session_id, []).append(websocket)
        print(f"[DEBUG][PID {pid}] WebSocket accepted for session {session_id}")

    def disconnect(self, websocket: WebSocket, session_id: str):
        pid = os.getpid()
        print(f"[DEBUG][PID {pid}] WebSocket disconnected for session {session_id}")
        conns = self.active_connections.get(session_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            if not conns:
                del self.active_connections[session_id]
        print(f"[DEBUG][PID {pid}] After disconnect: sessions={list(self.active_connections.keys())}")

    async def send_event(self, event_type: str, payload: dict, session_id: Optional[str] = None):
        pid = os.getpid()
        print(f"\n[DEBUG][PID {pid}] Preparing to send event: {event_type} (session={session_id})")

        # Recursively ensure the payload is JSON serializable
        def _serialize_payload(data):
            if isinstance(data, list):
                return [_serialize_payload(item) for item in data]
            elif isinstance(data, dict):
                return {key: _serialize_payload(value) for key, value in data.items()}
            elif hasattr(data, 'model_dump'):
                return data.model_dump()
            else:
                return data

        json_payload = _serialize_payload(payload)

        async with self._lock:
            if session_id:
                targets = list(self.active_connections.get(session_id, []))
            else:
                targets = [ws for conns in self.active_connections.values() for ws in conns]

        for connection in targets:
            try:
                await connection.send_json({"event_type": event_type, "payload": json_payload})
                print(f"[DEBUG][PID {pid}] Successfully sent event '{event_type}'")
            except Exception as e:
                print(f"[ERROR][PID {pid}] Failed to send message to websocket: {e}")

manager = ConnectionManager()


# ----------------------------
# WebSocket Endpoint
# ----------------------------
@router.websocket("/agentic-workflow/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            await websocket.receive_text() # Keep the connection open
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)


# ----------------------------
# Submit SOAP endpoint
# ----------------------------
@router.post("/submit_soap")
async def submit_soap(request: SubmitSOAPRequest):
    session_id = request.session_id or str(uuid.uuid4())
    print(f"\n[DEBUG] /submit_soap endpoint called for session {session_id}")

    # No need to wait for a backend event. The frontend already confirmed the WebSocket is open.
    # The `send_event` call will handle any connection issues gracefully.
    try:
        final_state = await agent_orchestrator.start_flow(
            soap_text=request.soap_text,
            session_id=session_id
        )
    except Exception as e:
        print(f"[ERROR] Exception while starting flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting session: {e}")

    if final_state.waiting_for_user:
        await manager.send_event("waiting_for_user", final_state.dict(), session_id)
    else:
        await manager.send_event("final_document", final_state.dict(), session_id)

    return JSONResponse(content={
        "session_id": session_id,
        "status": "started",
        "message": "Workflow initiated. Check WebSocket for updates."
    })


# ----------------------------
# Respond endpoint
# ----------------------------
@router.post("/respond")
async def respond(session_id: str, request: RespondRequest):
    print(f"\n[DEBUG] /respond endpoint called for session {session_id}")

    # Correctly map the incoming list of ServiceResponse objects to a nested dictionary
    # that the orchestrator expects.
    user_responses = {r.service_code: r.answers for r in request.responses}

    try:
        final_state = await agent_orchestrator.resume_flow(
            session_id=session_id,
            user_responses=user_responses
        )
    except Exception as e:
        print(f"[ERROR] Exception while resuming flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error resuming session: {e}")

    if final_state.waiting_for_user:
        await manager.send_event("waiting_for_user", final_state.dict(), session_id)
    else:
        await manager.send_event("final_document", final_state.dict(), session_id)

    return JSONResponse(content={
        "session_id": session_id,
        "status": "resumed",
        "message": "Workflow resumed. Check WebSocket for updates."
    })


@router.get("/state/{session_id}")
async def get_state(session_id: str):
    print(f"\n[DEBUG] /state/{session_id} is called")
    state = agent_orchestrator._get_state_from_redis(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return JSONResponse(content=state.dict())

@router.get("/_ws/debug")
async def ws_debug():
    snap = {k: len(v) for k, v in manager.active_connections.items()}
    return JSONResponse(content={
        "pid": os.getpid(),
        "sessions": snap,
        "total_sessions": len(snap),
        "keys": list(snap.keys()),
        "active_connections_dict": {k: f"{len(v)} connections" for k, v in manager.active_connections.items()}
    })
