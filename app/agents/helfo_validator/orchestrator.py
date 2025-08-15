# from typing import Dict, Callable, Optional
# from app.schemas_new.agentic_state import AgenticState
# from app.agentic_workflow import compiled_workflow, run_workflow_with_pause
# from app.agents.helfo_validator import live_events
#
# # In-memory session store
# SESSION_STORE: Dict[str, AgenticState] = {}
#
# class HelFoAgentOrchestrator:
#     def __init__(self):
#         self.workflow = compiled_workflow
#         print("[DEBUG][__init__] HelFoAgentOrchestrator initialized with compiled_workflow")
#
#     # ----------------------------
#     # Start a new session
#     # ----------------------------
#     async def start_flow(self, soap_text: str, session_id: str, event_callback: Optional[Callable] = None):
#         print(f"[DEBUG][start_flow] Starting session {session_id} with SOAP text: {soap_text}")
#
#         # Initialize state
#         state = AgenticState(
#             soap_text=soap_text,
#             predicted_service_codes=[],
#             reasoning_trail=[],
#             waiting_for_user=False,
#             candidates=[],
#             reranked_code=None,
#             question=None,
#             user_responses={},
#             loop_count=0,
#             max_loops=5
#         )
#         self._log_state(state, "Initial state in start_flow")
#
#         # Run workflow until first pause or completion
#         final_state = run_workflow_with_pause(
#             state,
#             event_callback=event_callback,
#             session_id=session_id
#         )
#
#         # Ensure final_state is always AgenticState
#         if isinstance(final_state, dict):
#             final_state = AgenticState(**final_state)
#
#         # Store state
#         SESSION_STORE[session_id] = final_state
#         print(f"[DEBUG][start_flow] Session {session_id} stored in SESSION_STORE")
#
#         return self._format_state_response(session_id, final_state)
#
#     # ----------------------------
#     # Resume a paused session
#     # ----------------------------
#     async def resume_flow(self, session_id: str, user_responses: Dict[str, str], event_callback: Optional[Callable] = None):
#         print(f"[DEBUG][resume_flow] Resuming session {session_id} with responses: {user_responses}")
#         state = SESSION_STORE.get(session_id)
#         if not state:
#             raise ValueError(f"Session {session_id} not found")
#
#         # Update state with user responses
#         state.user_responses.update(user_responses or {})
#         self._log_state(state, "State before resuming workflow")
#
#         # Reset waiting_for_user flag so workflow continues
#         state.waiting_for_user = False
#
#         # Continue workflow
#         final_state = run_workflow_with_pause(
#             state,
#             event_callback=event_callback,
#             session_id=session_id
#         )
#
#         # Ensure final_state is always AgenticState
#         if isinstance(final_state, dict):
#             final_state = AgenticState(**final_state)
#
#         # Update session
#         SESSION_STORE[session_id] = final_state
#         print(f"[DEBUG][resume_flow] Session {session_id} updated in SESSION_STORE")
#
#         return self._format_state_response(session_id, final_state)
#
#     # ----------------------------
#     # Format state for API response
#     # ----------------------------
#     def _format_state_response(self, session_id: str, state: AgenticState):
#         return {
#             "session_id": session_id,
#             "predicted_service_codes": [sc.dict() for sc in state.predicted_service_codes],
#             "question": state.question,
#             "waiting_for_user": state.waiting_for_user,
#             "reasoning_trail": state.reasoning_trail
#         }
#
#     # ----------------------------
#     # Helper: log full state
#     # ----------------------------
#     @staticmethod
#     def _log_state(state: AgenticState, label: str):
#         print(f"[STATE LOG] {label}")
#         print(f"soap_text: {getattr(state, 'soap_text', None)}")
#         print(f"predicted_service_codes: {[s.code for s in getattr(state, 'predicted_service_codes', [])]}")
#         print(f"candidates: {getattr(state, 'candidates', None)}")
#         print(f"reranked_code: {getattr(state, 'reranked_code', None)}")
#         print(f"waiting_for_user: {getattr(state, 'waiting_for_user', None)}")
#         print(f"question: {getattr(state, 'question', None)}")
#         print(f"user_responses: {getattr(state, 'user_responses', None)}")
#         print(f"loop_count: {getattr(state, 'loop_count', 0)}")
#         print(f"reasoning_trail: {getattr(state, 'reasoning_trail', [])}")
#
#
# # ----------------------------
# # Helper callback for live events
# # ----------------------------
# async def default_event_callback(session_id: str, state: AgenticState):
#     """
#     Default callback to push updates via WebSocket.
#     Can be passed to start_flow or resume_flow as event_callback.
#     """
#     payload = {
#         "session_id": session_id,
#         "predicted_service_codes": [sc.dict() for sc in state.predicted_service_codes],
#         "question": state.question,
#         "waiting_for_user": state.waiting_for_user,
#         "reasoning_trail": state.reasoning_trail
#     }
#
#     if state.waiting_for_user and state.question and state.reranked_code:
#         payload["service_code"] = state.reranked_code.get("code")  # <-- pass correct code
#
#     await live_events.push_update(session_id, {"event_type": "waiting_for_user", "payload": payload})
#!/usr/bin/env python

# app/agents/helfo_validator/orchestrator.py
# import asyncio
# from typing import Dict, Callable, Optional
# from pprint import pformat
#
# # --- Fix 1: Import the correct AgenticState and node functions ---
# from app.schemas_new.agentic_state import AgenticState, MissingInfoItem, ServiceCodeState
# from app.agentic_workflow import run_workflow
# from fastapi import WebSocket
#
# # In-memory session store (moved here from ws_router for clarity)
# SESSION_STORE: Dict[str, AgenticState] = {}
#
# class HelFoAgentOrchestrator:
#     """
#     Manages the session state and orchestrates the agentic workflow.
#     """
#
#     # ----------------------------
#     # Start a new session
#     # ----------------------------
#     # Fix 2: The signature is now clean and accepts the WebSocket object.
#     async def start_flow(self, soap_text: str, session_id: str, websocket: WebSocket):
#         """Initializes and starts a new agentic workflow session."""
#         print(f"[ORCHESTRATOR] Starting session {session_id} with SOAP text: {soap_text}")
#
#         # Fix 3: AgenticState is created with the session_id
#         state = AgenticState(
#             soap_text=soap_text,
#             session_id=session_id
#         )
#         self._log_state(state, "Initial state in start_flow")
#
#         try:
#             # Fix 4: Correctly call run_workflow with the state and websocket
#             final_state = await run_workflow(initial_state=state, websocket=websocket)
#
#             # Store final state
#             SESSION_STORE[session_id] = final_state
#             print(f"[ORCHESTRATOR] Session {session_id} stored in SESSION_STORE")
#
#             return final_state
#         except Exception as e:
#             print(f"[ERROR][start_flow] An error occurred: {e}")
#             raise e
#
#     # ----------------------------
#     # Resume a paused session
#     # ----------------------------
#     # Fix 5: The signature is now clean and accepts the WebSocket object.
#     async def resume_flow(self, session_id: str, user_responses: Dict, websocket: WebSocket):
#         """Resumes a paused workflow session with user input."""
#         print(f"[ORCHESTRATOR] Resuming session {session_id} with responses: {user_responses}")
#
#         state = SESSION_STORE.get(session_id)
#         if not state:
#             print(f"[ERROR][resume_flowf] Session {session_id} not found.")
#             raise ValueError(f"Session {session_id} not found")
#
#         try:
#             # Update state with user responses
#             responses_list = user_responses.get('responses', [])
#             if responses_list:
#                 for response_item in responses_list:
#                     service_code = response_item.get('service_code')
#                     answers = response_item.get('answers', {})
#
#                     found_service_code: Optional[ServiceCodeState] = None
#                     for sc in state.predicted_service_codes:
#                         if sc.code == service_code:
#                             found_service_code = sc
#                             break
#
#                     if found_service_code:
#                         for term_state in found_service_code.missing_terms:
#                             user_input_for_term = answers.get(term_state.term, "")
#                             if user_input_for_term:
#                                 term_state.answered = True
#                                 term_state.user_input = user_input_for_term
#
#             # Reset waiting_for_user flag so workflow continues
#             state.waiting_for_user = False
#             self._log_state(state, "State AFTER processing user input")
#
#             # Fix 6: Correctly call run_workflow with the updated state and websocket
#             final_state = await run_workflow(initial_state=state, websocket=websocket)
#
#             # Store updated state
#             SESSION_STORE[session_id] = final_state
#             print(f"[ORCHESTRATOR] Session {session_id} updated in SESSION_STORE")
#
#             return final_state
#         except Exception as e:
#             print(f"[ERROR][resume_flow] An error occurred: {e}")
#             raise e
#
#     @staticmethod
#     def _log_state(state: AgenticState, label: str):
#         """Static method to log the full state object for debugging."""
#         print(f"[STATE LOG] --- {label} ---")
#         print(pformat(state.dict()))
#         print("-----------------------------------")
# app/agents/helfo_validator/orchestrator.py
import asyncio
import uuid
import os
from typing import Dict, List, Optional
from pprint import pformat
import json

from fastapi import WebSocket
from app.schemas_new.agentic_state import AgenticState, MissingInfoItem, ServiceCodeState
from app.agentic_workflow import run_workflow

# In-memory session store
SESSION_STORE: Dict[str, AgenticState] = {}

class HelFoAgentOrchestrator:
    """
    Manages the session state and orchestrates the agentic workflow.
    """

    # ----------------------------
    # Start a new session
    # ----------------------------
    async def start_flow(self, soap_text: str, session_id: str, websocket: WebSocket):
        """Initializes and starts a new agentic workflow session."""
        print(f"[ORCHESTRATOR] Starting flow for session {session_id}...")

        state = AgenticState(
            soap_text=soap_text,
            session_id=session_id
        )
        self._log_state(state, "Initial state in start_flow")

        try:
            # Store the initial state
            SESSION_STORE[session_id] = state

            # Run the workflow with the initial state
            final_state = await run_workflow(initial_state=state, websocket=websocket)

            # Store final state after the run
            SESSION_STORE[session_id] = final_state
            print(f"[ORCHESTRATOR] Session {session_id} stored in SESSION_STORE")

            return final_state
        except Exception as e:
            print(f"[ERROR][start_flow] An error occurred: {e}")
            raise e

    # ----------------------------
    # Resume a paused session
    # ----------------------------
    async def resume_flow(self, session_id: str, user_responses: Dict, websocket: WebSocket):
        """Resumes a paused workflow session with user input."""
        print(f"[ORCHESTRATOR] Resuming session {session_id} with new responses: {user_responses}")

        state = SESSION_STORE.get(session_id)
        if not state:
            print(f"[ERROR][resume_flow] Session {session_id} not found.")
            raise ValueError(f"Session {session_id} not found")

        try:
            # Add new log to show the state before the merge
            self._log_state(state, "State BEFORE processing user input")

            # Update state with user responses
            # This is the corrected and simplified logic to merge responses.
            # We assume user_responses is a flat dict from the WebSocket.
            if user_responses:
                # Iterate through all predicted service codes in the current state
                for sc in state.predicted_service_codes:
                    # Iterate through the missing terms for each service code
                    for term_state in sc.missing_terms:
                        # Check if the user provided an answer for this specific term
                        user_input_for_term = user_responses.get(term_state.term, "")
                        if user_input_for_term:
                            print(f"[ORCHESTRATOR] Found user response for term '{term_state.term}'. Updating state...")
                            term_state.answered = True
                            term_state.user_input = user_input_for_term

            # Reset waiting_for_user flag so workflow continues
            state.waiting_for_user = False
            self._log_state(state, "State AFTER processing user input")

            # Correctly call run_workflow with the updated state
            final_state = await run_workflow(initial_state=state, websocket=websocket)

            # Store updated state
            SESSION_STORE[session_id] = final_state
            print(f"[ORCHESTRATOR] Session {session_id} updated in SESSION_STORE")

            return final_state
        except Exception as e:
            print(f"[ERROR][resume_flow] An error occurred: {e}")
            raise e

    @staticmethod
    def _log_state(state: AgenticState, label: str):
        """Static method to log the full state object for debugging."""
        print(f"[STATE LOG] --- {label} ---")
        print(pformat(state.dict()))
        print("-----------------------------------")
