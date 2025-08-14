# import asyncio
# import uuid
# import os
# import json
# from typing import List, Dict, Optional
#
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.responses import JSONResponse
#
# from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator, SESSION_STORE
# from app.schemas_new.agentic_state import RespondRequest, SubmitSOAPRequest
#
# router = APIRouter()
# agent_orchestrator = HelFoAgentOrchestrator()
#
#
# # ----------------------------
# # WebSocket Manager (Unchanged)
# # ----------------------------
# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: Dict[str, List[WebSocket]] = {}
#         self._lock = asyncio.Lock()
#
#     async def connect(self, websocket: WebSocket, session_id: str):
#         pid = os.getpid()
#         print(f"[DEBUG][PID {pid}] WebSocket connected for session {session_id}")
#         await websocket.accept()
#         async with self._lock:
#             self.active_connections.setdefault(session_id, []).append(websocket)
#             total_sessions = len(self.active_connections)
#             count_this = len(self.active_connections[session_id])
#         print(f"[DEBUG][PID {pid}] Active connections for {session_id}: {count_this} | total_sessions={total_sessions}")
#         try:
#             await websocket.send_json({"event_type": "ws_ready", "payload": {"session_id": session_id, "pid": pid}})
#         except Exception as e:
#             print(f"[WARN][PID {pid}] Failed to send ws_ready: {e}")
#
#     def disconnect(self, websocket: WebSocket, session_id: str):
#         pid = os.getpid()
#         print(f"[DEBUG][PID {pid}] WebSocket disconnected for session {session_id}")
#         conns = self.active_connections.get(session_id)
#         if conns and websocket in conns:
#             conns.remove(websocket)
#             if not conns:
#                 del self.active_connections[session_id]
#         print(f"[DEBUG][PID {pid}] After disconnect: sessions={list(self.active_connections.keys())}")
#
#     async def send_event(self, event_type: str, payload: dict, session_id: Optional[str] = None):
#         pid = os.getpid()
#         print(f"\n[DEBUG][PID {pid}] Preparing to send event: {event_type} (session={session_id})")
#         print(f"[DEBUG][PID {pid}] Payload: {payload}")
#
#         async with self._lock:
#             if session_id:
#                 targets = list(self.active_connections.get(session_id, []))
#             else:
#                 targets = [ws for conns in self.active_connections.values() for ws in conns]
#
#             snapshot = {k: len(v) for k, v in self.active_connections.items()}
#         print(f"[DEBUG][PID {pid}] Registry snapshot: {json.dumps(snapshot)}")
#         print(f"[DEBUG][PID {pid}] Found {len(targets)} WebSocket targets to send to for session={session_id}")
#
#         for connection in targets:
#             try:
#                 await connection.send_json({"event_type": event_type, "payload": payload})
#                 print(f"[DEBUG][PID {pid}] Successfully sent event '{event_type}'")
#             except Exception as e:
#                 print(f"[ERROR][PID {pid}] Failed to send message to websocket: {e}")
#
# manager = ConnectionManager()
#
#
# # ----------------------------
# # WebSocket Endpoint (Unchanged)
# # ----------------------------
# @router.websocket("/ws/agentic-workflow/{session_id}")
# async def websocket_endpoint(websocket: WebSocket, session_id: str):
#     await manager.connect(websocket, session_id)
#     try:
#         while True:
#             # This loop receives messages from the FE, e.g., user responses.
#             # The agent flow is started by the /submit_soap POST endpoint.
#             data = await websocket.receive_json()
#             if "responses" in data:
#                 request = RespondRequest(responses=data["responses"])
#                 state = SESSION_STORE.get(session_id)
#                 if state:
#                     state.user_responses = {r.service_code: r.answers for r in request.responses}
#                     # Resume workflow and send live updates via the callback
#                     await agent_orchestrator.resume_flow(
#                         session_id=session_id,
#                         user_responses=state.user_responses,
#                         event_callback=lambda etype, payload: manager.send_event(etype, payload, session_id)
#                     )
#     except WebSocketDisconnect:
#         manager.disconnect(websocket, session_id)
#
#
# # ----------------------------
# # Submit SOAP endpoint (FIXED)
# # ----------------------------
# @router.post("/submit_soap")
# async def submit_soap(request: SubmitSOAPRequest):
#     print("\n[DEBUG] /submit_soap endpoint called")
#     session_id = request.session_id or str(uuid.uuid4())
#     print(f"[DEBUG] Using session_id: {session_id}")
#
#     try:
#         # We need to wait for the WebSocket to connect before starting the flow.
#         # This prevents the race condition where the flow starts and sends events
#         # before the WS is registered in the ConnectionManager.
#         print(f"[DEBUG] Waiting for WebSocket connection for session {session_id}...")
#         await asyncio.wait_for(
#             wait_for_websocket_connection(session_id),
#             timeout=5.0  # Set a reasonable timeout
#         )
#         print(f"[DEBUG] WebSocket connection confirmed for session {session_id}.")
#     except asyncio.TimeoutError:
#         raise HTTPException(
#             status_code=408,
#             detail=f"Timeout waiting for WebSocket connection for session {session_id}. Please ensure the client is connected."
#         )
#
#     try:
#         print("[DEBUG] Starting agent flow...")
#         # The agent_orchestrator.start_flow will now proceed knowing the WS is ready.
#         # It handles sending events via the callback, so we remove the redundant
#         # logic below.
#         await agent_orchestrator.start_flow(
#             soap_text=request.soap_text,
#             session_id=session_id,
#             event_callback=lambda etype, payload: manager.send_event(etype, payload, session_id)
#         )
#         print("[DEBUG] Agent flow started successfully")
#     except Exception as e:
#         print(f"[ERROR] Exception while starting flow: {e}")
#         raise HTTPException(status_code=500, detail=f"Error starting session: {e}")
#
#     # Now that the flow has started and a state is established,
#     # we can retrieve and return the initial state.
#     state = SESSION_STORE.get(session_id)
#     if not state:
#         raise HTTPException(status_code=500, detail="Session state not found after starting flow.")
#
#     response_payload = {
#         "session_id": session_id,
#         "question": getattr(state, "question", None),
#         "waiting_for_user": getattr(state, "waiting_for_user", False),
#         "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
#         "reasoning_trail": getattr(state, "reasoning_trail", []),
#     }
#     print(f"[DEBUG] Returning response: {response_payload}")
#     return response_payload
#
#
# # Helper function to poll for the WebSocket connection
# async def wait_for_websocket_connection(session_id: str):
#     while session_id not in manager.active_connections:
#         await asyncio.sleep(0.1)
#
#
# # ----------------------------
# # The remaining endpoints are unchanged.
# # ----------------------------
# @router.post("/respond")
# async def respond(session_id: str, request: RespondRequest):
#     state = SESSION_STORE.get(session_id)
#     if not state:
#         raise HTTPException(status_code=404, detail="Session not found")
#
#     state.user_responses = {r.service_code: r.answers for r in request.responses}
#     await agent_orchestrator.resume_flow(
#         session_id=session_id,
#         user_responses=state.user_responses,
#         event_callback=lambda etype, payload: manager.send_event(etype, payload, session_id)
#     )
#
#     return JSONResponse(content={
#         "session_id": session_id,
#         "question": getattr(state, "question", None),
#         "waiting_for_user": getattr(state, "waiting_for_user", False),
#         "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
#         "reasoning_trail": getattr(state, "reasoning_trail", []),
#     })
#
#
# @router.get("/state/{session_id}")
# async def get_state(session_id: str):
#     state = SESSION_STORE.get(session_id)
#     if not state:
#         raise HTTPException(status_code=404, detail="Session not found")
#
#     state_dict = state.dict()
#     state_dict.update({
#         "question": getattr(state, "question", None),
#         "waiting_for_user": getattr(state, "waiting_for_user", False),
#         "loop_count": getattr(state, "loop_count", 0),
#         "max_loops": getattr(state, "max_loops", 5),
#         "user_responses": getattr(state, "user_responses", {}),
#     })
#     return JSONResponse(content=state_dict)
#
# @router.get("/_ws/debug")
# async def ws_debug():
#     snap = {k: len(v) for k, v in manager.active_connections.items()}
#     return JSONResponse(content={
#         "pid": os.getpid(),
#         "sessions": snap,
#         "total_sessions": len(snap),
#         "keys": list(snap.keys()),
#     })
import asyncio
import uuid
import os
import json
from typing import List, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator, SESSION_STORE
from app.schemas_new.agentic_state import RespondRequest, SubmitSOAPRequest

router = APIRouter()
agent_orchestrator = HelFoAgentOrchestrator()


# ----------------------------
# WebSocket Manager
# ----------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Dictionary to store asyncio.Event for each session
        self._ready_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def create_ready_event(self, session_id: str) -> asyncio.Event:
        """Create and return a ready event for the session"""
        event = asyncio.Event()
        self._ready_events[session_id] = event
        return event

    async def connect(self, websocket: WebSocket, session_id: str):
        pid = os.getpid()
        print(f"[DEBUG][PID {pid}] WebSocket connect method called for session {session_id}")
        await websocket.accept()
        print(f"[DEBUG][PID {pid}] WebSocket accepted for session {session_id}")

        async with self._lock:
            self.active_connections.setdefault(session_id, []).append(websocket)
            total_sessions = len(self.active_connections)
            count_this = len(self.active_connections[session_id])

        print(f"[DEBUG][PID {pid}] Active connections for {session_id}: {count_this} | total_sessions={total_sessions}")

        # Set the ready event if it exists
        event = self._ready_events.get(session_id)
        if event:
            event.set()
            print(f"[DEBUG][PID {pid}] Connection ready event set for session {session_id}")
        else:
            print(f"[DEBUG][PID {pid}] No ready event found for session {session_id}")

        # Send ready message to confirm connection
        try:
            await websocket.send_json({
                "event_type": "ws_ready",
                "payload": {"session_id": session_id, "pid": pid}
            })
            print(f"[DEBUG][PID {pid}] Sent ws_ready message for session {session_id}")
        except Exception as e:
            print(f"[WARN][PID {pid}] Failed to send ws_ready: {e}")

    def disconnect(self, websocket: WebSocket, session_id: str):
        pid = os.getpid()
        print(f"[DEBUG][PID {pid}] WebSocket disconnected for session {session_id}")
        conns = self.active_connections.get(session_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            if not conns:
                del self.active_connections[session_id]
                # Clean up the event object when the last connection for the session is gone
                if session_id in self._ready_events:
                    del self._ready_events[session_id]
                    print(f"[DEBUG][PID {pid}] Cleaned up ready event for session {session_id}")
        print(f"[DEBUG][PID {pid}] After disconnect: sessions={list(self.active_connections.keys())}")

    async def send_event(self, event_type: str, payload: dict, session_id: Optional[str] = None):
        pid = os.getpid()
        print(f"\n[DEBUG][PID {pid}] Preparing to send event: {event_type} (session={session_id})")
        print(f"[DEBUG][PID {pid}] Payload: {payload}")

        async with self._lock:
            if session_id:
                targets = list(self.active_connections.get(session_id, []))
            else:
                targets = [ws for conns in self.active_connections.values() for ws in conns]

            snapshot = {k: len(v) for k, v in self.active_connections.items()}

        print(f"[DEBUG][PID {pid}] Registry snapshot: {json.dumps(snapshot)}")
        print(f"[DEBUG][PID {pid}] Found {len(targets)} WebSocket targets to send to for session={session_id}")

        for connection in targets:
            try:
                await connection.send_json({"event_type": event_type, "payload": payload})
                print(f"[DEBUG][PID {pid}] Successfully sent event '{event_type}'")
            except Exception as e:
                print(f"[ERROR][PID {pid}] Failed to send message to websocket: {e}")

    def is_connected(self, session_id: str) -> bool:
        """Check if a session has active connections"""
        return session_id in self.active_connections and len(self.active_connections[session_id]) > 0

manager = ConnectionManager()


# ----------------------------
# WebSocket Endpoint
# ----------------------------
# @router.websocket("/ws/agentic-workflow/{session_id}")
# async def websocket_endpoint(websocket: WebSocket, session_id: str):
#     # Your existing debug logging
#     print(f"[DEBUG] WS CONNECTED: session_id={session_id}, total_in_session=1, total_sessions=1")
#
#     # IMPORTANT: Make sure this line is called to register the connection
#     await manager.connect(websocket, session_id)
#
#     try:
#         while True:
#             # This loop receives messages from the FE, e.g., user responses.
#             # The agent flow is started by the /submit_soap POST endpoint.
#             data = await websocket.receive_json()
#             if "responses" in data:
#                 request = RespondRequest(responses=data["responses"])
#                 state = SESSION_STORE.get(session_id)
#                 if state:
#                     state.user_responses = {r.service_code: r.answers for r in request.responses}
#                     # Resume workflow and send live updates via the callback
#                     await agent_orchestrator.resume_flow(
#                         session_id=session_id,
#                         user_responses=state.user_responses,
#                         event_callback=lambda etype, payload: manager.send_event(etype, payload, session_id)
#                     )
#     except WebSocketDisconnect:
#         manager.disconnect(websocket, session_id)


# And make sure your ConnectionManager.connect method looks like this:
async def connect(self, websocket: WebSocket, session_id: str):
    pid = os.getpid()
    print(f"[DEBUG][PID {pid}] WebSocket connected for session {session_id}")
    await websocket.accept()
    async with self._lock:
        self.active_connections.setdefault(session_id, []).append(websocket)
        total_sessions = len(self.active_connections)
        count_this = len(self.active_connections[session_id])
    print(f"[DEBUG][PID {pid}] Active connections for {session_id}: {count_this} | total_sessions={total_sessions}")


# For debugging, add this endpoint to check if connections are being registered:
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
# Submit SOAP endpoint (FIXED)
# ----------------------------
@router.post("/submit_soap")
async def submit_soap(request: SubmitSOAPRequest):
    print("\n[DEBUG] /submit_soap endpoint called")
    session_id = request.session_id or str(uuid.uuid4())
    print(f"[DEBUG] Using session_id: {session_id}")

    # Simple approach: wait for WebSocket connection with polling
    max_attempts = 25  # 5 seconds total (25 * 200ms)
    for attempt in range(max_attempts):
        if session_id in manager.active_connections:
            print(f"[DEBUG] WebSocket connection found for session {session_id} after {attempt * 200}ms")
            break
        print(f"[DEBUG] Attempt {attempt + 1}/{max_attempts}: Waiting for WebSocket connection...")
        await asyncio.sleep(0.2)
    else:
        raise HTTPException(
            status_code=408,
            detail=f"Timeout waiting for WebSocket connection for session {session_id}. "
                   f"Please ensure the WebSocket connects before making the HTTP request."
        )

    try:
        print("[DEBUG] Starting agent flow...")
        await agent_orchestrator.start_flow(
            soap_text=request.soap_text,
            session_id=session_id,
            event_callback=lambda etype, payload: manager.send_event(etype, payload, session_id)
        )
        print("[DEBUG] Agent flow started successfully")
    except Exception as e:
        print(f"[ERROR] Exception while starting flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting session: {e}")

    # Retrieve and return the initial state
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=500, detail="Session state not found after starting flow.")

    response_payload = {
        "session_id": session_id,
        "question": getattr(state, "question", None),
        "waiting_for_user": getattr(state, "waiting_for_user", False),
        "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
        "reasoning_trail": getattr(state, "reasoning_trail", []),
    }
    print(f"[DEBUG] Returning response: {response_payload}")
    return


# ----------------------------
# The remaining endpoints are unchanged.
# ----------------------------
@router.post("/respond")
async def respond(session_id: str, request: RespondRequest):
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    state.user_responses = {r.service_code: r.answers for r in request.responses}
    await agent_orchestrator.resume_flow(
        session_id=session_id,
        user_responses=state.user_responses,
        event_callback=lambda etype, payload: manager.send_event(etype, payload, session_id)
    )

    return JSONResponse(content={
        "session_id": session_id,
        "question": getattr(state, "question", None),
        "waiting_for_user": getattr(state, "waiting_for_user", False),
        "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
        "reasoning_trail": getattr(state, "reasoning_trail", []),
    })


@router.get("/state/{session_id}")
async def get_state(session_id: str):
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    state_dict = state.dict()
    state_dict.update({
        "question": getattr(state, "question", None),
        "waiting_for_user": getattr(state, "waiting_for_user", False),
        "loop_count": getattr(state, "loop_count", 0),
        "max_loops": getattr(state, "max_loops", 5),
        "user_responses": getattr(state, "user_responses", {}),
    })
    return JSONResponse(content=state_dict)

# @router.get("/_ws/debug")
# async def ws_debug():
#     snap = {k: len(v) for k, v in manager.active_connections.items()}
#     ready_events = list(manager._ready_events.keys())
#     return JSONResponse(content={
#         "pid": os.getpid(),
#         "sessions": snap,
#         "total_sessions": len(snap),
#         "keys": list(snap.keys()),
#         "ready_events": ready_events,
#     })