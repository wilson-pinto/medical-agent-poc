import asyncio
import uuid
import os
import json
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response
from pathlib import Path
import redis
from dotenv import load_dotenv

from app.core.patient_summary_pdf_node import patient_summary_pdf_node
from app.schemas_new.agentic_state import AgenticState, RespondRequest, SubmitSOAPRequest
from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator

# ----------------------------
# Setup
# ----------------------------
router = APIRouter()
BASE_DIR = Path(__file__).parent.parent
PDF_DIR = BASE_DIR / "tmp_pdfs"
PDF_DIR.mkdir(exist_ok=True, parents=True)

# Load Redis config
load_dotenv()
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    redis_client.ping()
    print("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"Failed to connect to Redis: {e}")
    redis_client = None

agent_orchestrator = HelFoAgentOrchestrator(redis_client=redis_client)

# ----------------------------
# WebSocket Manager
# ----------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        async with self._lock:
            self.active_connections.setdefault(session_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        conns = self.active_connections.get(session_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            if not conns:
                del self.active_connections[session_id]

    async def send_event(self, event_type: str, payload: dict, session_id: Optional[str] = None):
        # JSON-serializable payload
        def _serialize_payload(data):
            if isinstance(data, list):
                return [_serialize_payload(item) for item in data]
            elif isinstance(data, dict):
                return {k: _serialize_payload(v) for k, v in data.items()}
            elif hasattr(data, 'model_dump'):
                return data.model_dump()
            else:
                return data

        json_payload = _serialize_payload(payload)

        async with self._lock:
            targets = list(self.active_connections.get(session_id, [])) if session_id else [
                ws for conns in self.active_connections.values() for ws in conns
            ]

        for connection in targets:
            try:
                await connection.send_json({"event_type": event_type, "payload": json_payload})
            except Exception as e:
                print(f"[ERROR] Failed to send WS message: {e}")

manager = ConnectionManager()

# ----------------------------
# WebSocket Endpoint
# ----------------------------
@router.websocket("/agentic-workflow/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)

# ----------------------------
# SOAP Endpoints
# ----------------------------
@router.post("/submit_soap")
async def submit_soap(request: SubmitSOAPRequest):
    session_id = request.session_id or str(uuid.uuid4())

    async def ws_send(payload: dict):
        await manager.send_event(payload.get("event_type", "unknown"), payload.get("payload", {}), session_id=session_id)

    try:
        await agent_orchestrator.start_flow(
            soap_text=request.soap_text,
            session_id=session_id,
            ws_send=ws_send
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting session: {e}")

    return JSONResponse(content={"session_id": session_id, "status": "started", "message": "Workflow initiated. Check WebSocket for updates."})

@router.post("/respond")
async def respond(session_id: str, request: RespondRequest):
    user_responses = {r.service_code: r.answers for r in request.responses}

    async def ws_send(payload: dict):
        await manager.send_event(payload.get("event_type", "unknown"), payload.get("payload", {}), session_id=session_id)

    try:
        await agent_orchestrator.resume_flow(
            session_id=session_id,
            user_responses=user_responses,
            ws_send=ws_send
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resuming session: {e}")

    return JSONResponse(content={"session_id": session_id, "status": "resumed", "message": "Workflow resumed. Check WebSocket for updates."})

# ----------------------------
# State & Debug
# ----------------------------
@router.get("/state/{session_id}")
async def get_state(session_id: str):
    state = agent_orchestrator._get_state_from_redis(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse(content=state.dict())

@router.get("/_ws/debug")
async def ws_debug():
    snap = {k: len(v) for k, v in manager.active_connections.items()}
    return JSONResponse(content={"pid": os.getpid(), "sessions": snap, "total_sessions": len(snap)})

# ----------------------------
# Clear Sessions
# ----------------------------
@router.delete("/clear_session/{session_id}")
async def clear_session(session_id: str):
    redis_deleted = redis_client.delete(f"session_state:{session_id}") > 0 if redis_client else False
    async with manager._lock:
        conns = manager.active_connections.pop(session_id, [])
        for ws in conns:
            await ws.close()
    return JSONResponse({"session_id": session_id, "redis_deleted": redis_deleted, "connections_cleared": True})

@router.delete("/clear_all_sessions")
async def clear_all_sessions():
    redis_deleted_count = 0
    if redis_client:
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match="session_state:*", count=100)
            if keys:
                redis_deleted_count += redis_client.delete(*keys)
            if cursor == 0:
                break
    async with manager._lock:
        total_connections = sum(len(c) for c in manager.active_connections.values())
        manager.active_connections.clear()
    return JSONResponse({"redis_deleted_count": redis_deleted_count, "connections_cleared_count": total_connections})

# ----------------------------
# PDF Download
# ----------------------------
@router.get("/download_pdf/{session_id}")
async def download_pdf(session_id: str):
    pdf_file = PDF_DIR / f"patient_summary_{session_id}.pdf"
    print(f"PDF file path: {pdf_file}")

    if not pdf_file.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        path=str(pdf_file),
        filename=pdf_file.name,
        media_type='application/pdf'
    )
