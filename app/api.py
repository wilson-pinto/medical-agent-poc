import asyncio
import uuid
import os
import json
from typing import Dict, List, Optional, Any

from fastapi.responses import Response
from app.core.patient_summary_pdf_node import patient_summary_pdf_node
from app.schemas_new.agentic_state import AgenticState
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
# ----------------------------
# Submit SOAP endpoint (updated)
# ----------------------------
@router.post("/submit_soap")
async def submit_soap(request: SubmitSOAPRequest):
    session_id = request.session_id or str(uuid.uuid4())
    print(f"\n[DEBUG] /submit_soap endpoint called for session {session_id}")

    # Define async ws_send wrapper
    async def ws_send(payload: dict):
        await manager.send_event(payload.get("event_type", "unknown"), payload.get("payload", {}), session_id=session_id)

    # Start workflow with ws_send
    try:
        final_state = await agent_orchestrator.start_flow(
            soap_text=request.soap_text,
            session_id=session_id,
            ws_send=ws_send  # pass async ws_send to orchestrator
        )
    except Exception as e:
        print(f"[ERROR] Exception while starting flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting session: {e}")

    return JSONResponse(content={
        "session_id": session_id,
        "status": "started",
        "message": "Workflow initiated. Check WebSocket for updates."
    })


# ----------------------------
# Respond endpoint
# ----------------------------
# ----------------------------
# Respond endpoint (updated)
# ----------------------------
@router.post("/respond")
async def respond(session_id: str, request: RespondRequest):
    print(f"\n[DEBUG] /respond endpoint called for session {session_id}")

    # Map user responses
    user_responses = {r.service_code: r.answers for r in request.responses}

    # Async ws_send wrapper
    async def ws_send(payload: dict):
        await manager.send_event(payload.get("event_type", "unknown"), payload.get("payload", {}), session_id=session_id)

    try:
        final_state = await agent_orchestrator.resume_flow(
            session_id=session_id,
            user_responses=user_responses,
            ws_send=ws_send  # pass async ws_send to orchestrator
        )
    except Exception as e:
        print(f"[ERROR] Exception while resuming flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error resuming session: {e}")

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

# ----------------------------
# Clear session endpoint
# ----------------------------
@router.delete("/clear_session/{session_id}")
async def clear_session(session_id: str):
    print(f"\n[DEBUG] /clear_session/{session_id} called")

    redis_deleted = False
    redis_key = f"session_state:{session_id}"  # add correct prefix

    # Remove from Redis
    if redis_client:
        try:
            deleted_count = redis_client.delete(redis_key)
            redis_deleted = deleted_count > 0
        except Exception as e:
            print(f"[ERROR] Failed to delete session from Redis: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to clear session: {e}")

    # Remove active WebSocket connections if any
    connections_cleared = False
    async with manager._lock:
        if session_id in manager.active_connections:
            conns = manager.active_connections.pop(session_id, [])
            for ws in conns:
                try:
                    await ws.close()
                except Exception as e:
                    print(f"[WARNING] Failed to close websocket: {e}")
        connections_cleared = session_id not in manager.active_connections

    return JSONResponse(content={
        "session_id": session_id,
        "redis_deleted": redis_deleted,
        "connections_cleared": connections_cleared,
        "message": f"Session {session_id} cleared successfully."
    })


@router.get("/_redis/keys")
async def list_redis_keys():
    if redis_client is None:
        return JSONResponse(
            status_code=500,
            content={"error": "Redis client not initialized."}
        )

    try:
        keys = redis_client.keys("*")
        # decode bytes to str
        keys_str = [k.decode("utf-8") for k in keys]
        return JSONResponse(content={
            "total_keys": len(keys_str),
            "keys": keys_str
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@router.delete("/clear_all_sessions")
async def clear_all_sessions():
    print("\n[DEBUG] /clear_all_sessions called")

    redis_deleted_count = 0
    if redis_client:
        try:
            # Scan for all session keys with the prefix
            cursor = 0
            while True:
                cursor, keys = redis_client.scan(cursor=cursor, match="session_state:*", count=100)
                if keys:
                    redis_deleted_count += redis_client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            print(f"[ERROR] Failed to delete sessions from Redis: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to clear sessions: {e}")

    # Clear all active WebSocket connections
    async with manager._lock:
        total_connections = sum(len(conns) for conns in manager.active_connections.values())
        manager.active_connections.clear()

    return JSONResponse(content={
        "redis_deleted_count": redis_deleted_count,
        "connections_cleared_count": total_connections,
        "message": f"All sessions cleared successfully."
    })

# ----------------------------
# Download Patient Summary PDF
# ----------------------------


@router.get("/download_patient_summary/{session_id}")
async def download_patient_summary(session_id: str):
    """
    Generates or fetches the patient-friendly summary PDF for the given session
    and returns it as a downloadable file.
    """
    # Fetch the workflow state from Redis (or wherever you store it)
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis client not initialized.")

    state_data = redis_client.get(f"session_state:{session_id}")
    if not state_data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Recreate AgenticState object
    state_dict = json.loads(state_data)
    state = AgenticState(**state_dict)

    # Generate PDF using your node (fallback to simple text if Gemeni fails inside node)
    updates = await patient_summary_pdf_node(state)
    pdf_bytes = updates.get("patient_summary_pdf", b"")

    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate patient summary PDF")

    headers = {
        "Content-Disposition": f"attachment; filename=patient_summary_{session_id}.pdf"
    }

    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
