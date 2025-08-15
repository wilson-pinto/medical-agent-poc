# app/agents/helfo_validator/ws_router.py
# import asyncio
# import uuid
# import os
# from typing import List
#
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.responses import JSONResponse
#
# from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator, SESSION_STORE
# from app.schemas_new.agentic_state import RespondRequest, SubmitSOAPRequest, AgenticState
# from app.agents.helfo_validator import live_events
#
# router = APIRouter()
# agent_orchestrator = HelFoAgentOrchestrator()
#
#
# def _serialize_payload(payload):
#     """Recursively convert objects to JSON-serializable dicts."""
#     if isinstance(payload, list):
#         return [_serialize_payload(p) for p in payload]
#     elif isinstance(payload, dict):
#         return {k: _serialize_payload(v) for k, v in payload.items()}
#     elif hasattr(payload, "dict"):
#         return payload.dict()
#     else:
#         return payload
#
# # Fix 1: Define the correct callback function
# def live_event_callback(session_id: str, state: AgenticState):
#     """Prepare payload including service_code and push via WebSocket."""
#     payload = {
#         "session_id": session_id,
#         "predicted_service_codes": _serialize_payload(getattr(state, "predicted_service_codes", [])),
#         "question": getattr(state, "question", None),
#         "waiting_for_user": getattr(state, "waiting_for_user", False),
#         "reasoning_trail": getattr(state, "reasoning_trail", []),
#     }
#
#     # Include service_code if available
#     reranked_code = getattr(state, "reranked_code", None)
#     if state.waiting_for_user and reranked_code:
#         payload["service_code"] = reranked_code.get("code") if isinstance(reranked_code, dict) else getattr(reranked_code, "code", None)
#
#     return live_events.push_update(session_id, {"event_type": "waiting_for_user", "payload": payload})
#
#
# @router.websocket("/agentic-workflow/{session_id}")
# async def websocket_endpoint(websocket: WebSocket, session_id: str):
#     await live_events.connect(session_id, websocket)
#     try:
#         while True:
#             data = await websocket.receive_json()
#             print(f"[WS {session_id}] Received: {data}")
#
#             # Handle user responses
#             if "responses" in data:
#                 request = RespondRequest(responses=data["responses"])
#                 state = SESSION_STORE.get(session_id)
#                 if state:
#                     state.user_responses = {r.service_code: r.answers for r in request.responses}
#                     # Resume workflow and send live updates via the callback
#                     await agent_orchestrator.resume_flow(
#                         session_id=session_id,
#                         user_responses=state.user_responses,
#                         # Fix 2: Use the simplified lambda
#                         event_callback=lambda etype, state: live_event_callback(session_id, state)
#                     )
#
#     except WebSocketDisconnect:
#         live_events.disconnect(session_id, websocket)
#
#
# @router.post("/submit_soap")
# async def submit_soap(request: SubmitSOAPRequest):
#     print("\n[DEBUG] /submit_soap endpoint called")
#     print(f"[DEBUG] Inside ws router the submit_soap endpoint handler. Received SOAP text: {request.soap_text}")
#     session_id = request.session_id or str(uuid.uuid4())
#     print(f"[DEBUG] Using session_id: {session_id}")
#
#     # Wait for WebSocket connection with polling
#     max_attempts = 25  # 5 seconds total
#     for attempt in range(max_attempts):
#         if session_id in live_events.SESSION_CONNECTIONS:
#             print(f"[DEBUG] WebSocket connection found for session {session_id} after {attempt * 200}ms")
#             break
#         print(f"[DEBUG] Attempt {attempt + 1}/{max_attempts}: Waiting for WebSocket connection...")
#         await asyncio.sleep(0.2)
#     else:
#         raise HTTPException(
#             status_code=408,
#             detail=f"Timeout waiting for WebSocket connection for session {session_id}. "
#                    f"Please ensure the WebSocket connects before making the HTTP request."
#         )
#
#     try:
#         print("[DEBUG] Starting agent flow...")
#         await agent_orchestrator.start_flow(
#             soap_text=request.soap_text,
#             session_id=session_id,
#             # Fix 3: Use the simplified lambda
#             event_callback=lambda etype, state: live_event_callback(session_id, state)
#         )
#
#         print("[DEBUG] Agent flow started successfully")
#     except Exception as e:
#         print(f"[ERROR] Exception while starting flow: {e}")
#         raise HTTPException(status_code=500, detail=f"Error starting session: {e}")
#
#     # Retrieve and return the initial state
#     state = SESSION_STORE.get(session_id)
#     if not state:
#         raise HTTPException(status_code=500, detail="Session state not found after starting flow.")
#
#     response_payload = {
#         "session_id": session_id,
#         "question": getattr(state, "question", None),
#         "waiting_for_user": getattr(state, "waiting_for_user", False),
#         "predicted_service_codes": _serialize_payload(getattr(state, "predicted_service_codes", [])),
#         "reasoning_trail": getattr(state, "reasoning_trail", []),
#     }
#     print(f"[DEBUG] Returning response: {response_payload}")
#     return response_payload
#
#
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
#         # Fix 4: Use the simplified lambda
#         event_callback=lambda etype, state: live_event_callback(session_id, state)
#     )
#
#
#     return JSONResponse(content={
#         "session_id": session_id,
#         "question": getattr(state, "question", None),
#         "waiting_for_user": getattr(state, "waiting_for_user", False),
#         "predicted_service_codes": _serialize_payload(getattr(state, "predicted_service_codes", [])),
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
#         "max_loops": getattr(state, "max_loops", 10),
#         "user_responses": getattr(state, "user_responses", {}),
#         "predicted_service_codes": _serialize_payload(getattr(state, "predicted_service_codes", [])),
#     })
#     return JSONResponse(content=state_dict)
#
#
# @router.get("/_ws/debug")
# async def ws_debug():
#     return JSONResponse(content={
#         "pid": os.getpid(),
#         "sessions": {k: len(v) for k, v in live_events.SESSION_CONNECTIONS.items()},
#         "total_sessions": len(live_events.SESSION_CONNECTIONS),
#         "keys": list(live_events.SESSION_CONNECTIONS.keys()),
#     })

#app/agents/helfo_validator/ws_router.py
import asyncio
import uuid
import os
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

# --- Fix 1: Import the corrected orchestrator and schemas ---
from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator, SESSION_STORE
from app.schemas_new.agentic_state import AgenticState, SubmitSOAPRequest, RespondRequest
from app.agents.helfo_validator import live_events

router = APIRouter()
agent_orchestrator = HelFoAgentOrchestrator()

@router.websocket("/agentic-workflow/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint that handles the entire agentic workflow lifecycle.
    It accepts a SOAP text to start the flow and user responses to resume it.
    """
    await live_events.connect(session_id, websocket)
    print(f"[WS] WebSocket connected for session {session_id}")

    try:
        while True:
            data = await websocket.receive_json()
            print(f"[WS {session_id}] Received data: {data}")

            # --- Fix 2: Start flow logic is now inside the WebSocket loop ---
            # Client sends the initial SOAP text
            if "soap_text" in data:
                print(f"[WS] Received new SOAP submission. Starting flow...")
                # The orchestrator now needs the websocket object
                await agent_orchestrator.start_flow(
                    soap_text=data["soap_text"],
                    session_id=session_id,
                    websocket=websocket
                )

            # --- Fix 3: Handle user responses to resume flow ---
            elif "responses" in data:
                print(f"[WS] Received user responses. Resuming flow...")
                print(f"[WS] Data being passed to resume_flow: {data}")
                # The orchestrator now needs the websocket object
                all_user_answers = {}
                for response_item in data.get("responses", []):
                    # Check if the 'answers' key exists and is a dictionary
                    if "answers" in response_item and isinstance(response_item["answers"], dict):
                        # Merge the answers from this item into our master dictionary
                        all_user_answers.update(response_item["answers"])
                print(f"[WS] New Data being passed to resume_flow: {all_user_answers}")
                await agent_orchestrator.resume_flow(
                    session_id=session_id,
                    user_responses=all_user_answers,
                    websocket=websocket
                )

    except WebSocketDisconnect:
        print(f"[WS] WebSocket disconnected for session {session_id}")
        live_events.disconnect(session_id, websocket)
    except Exception as e:
        print(f"[WS ERROR] An exception occurred: {e}")
        # Send an error message before closing
        await websocket.send_json({"event_type": "error", "payload": {"message": str(e)}})
        live_events.disconnect(session_id, websocket)

# --- Fix 4: Remove the redundant HTTP POST endpoints ---
# The /submit_soap and /respond endpoints are now obsolete
# since all logic is handled through the WebSocket.

# Example of a new, clean API structure
# @router.post("/start_new_session")
# async def start_new_session(request: SubmitSOAPRequest):
#     # This could be a simple endpoint to get a new session ID for the frontend
#     session_id = str(uuid.uuid4())
#     return {"session_id": session_id}
