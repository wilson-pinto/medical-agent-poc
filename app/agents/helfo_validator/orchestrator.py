# orchestrator.py
import asyncio
import uuid
import json
import redis
from typing import Dict, Optional, Callable
from pprint import pformat
from pydantic import ValidationError

from app.schemas_new.agentic_state import AgenticState, MissingInfoItem, ServiceCodeState
from app.agentic_workflow import run_workflow

SESSION_KEY_PREFIX = "session_state:"


class HelFoAgentOrchestrator:
    """
    Manages session state and orchestrates the agentic workflow using Redis for persistence.
    Supports ws_send for real-time frontend updates.
    """

    def __init__(self, redis_client: Optional[redis.Redis]):
        self.redis_client = redis_client

    # ----------------------------
    # Redis helpers
    # ----------------------------
    def _get_state_from_redis(self, session_id: str) -> Optional[AgenticState]:
        if not self.redis_client:
            print("[WARN] Redis not connected. Cannot retrieve state.")
            return None
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        try:
            serialized_state = self.redis_client.get(key)
            if serialized_state:
                state_data = json.loads(serialized_state)
                return AgenticState.model_validate(state_data)
        except (json.JSONDecodeError, ValidationError, redis.exceptions.RedisError) as e:
            print(f"[ERROR] Failed to retrieve or deserialize state for session {session_id}: {e}")
        return None

    def _save_state_to_redis(self, session_id: str, state: AgenticState):
        if not self.redis_client:
            print("[WARN] Redis not connected. State will not be persisted.")
            return
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        try:
            serialized_state = state.model_dump_json()
            self.redis_client.set(key, serialized_state)
            print(f"[REDIS] State for session {session_id} saved.")
        except redis.exceptions.RedisError as e:
            print(f"[ERROR] Failed to save state to Redis for session {session_id}: {e}")

    # ----------------------------
    # Start a new session
    # ----------------------------
    async def start_flow(
        self,
        soap_text: str,
        session_id: str,
        ws_send: Optional[Callable[[Dict], None]] = None
    ) -> AgenticState:
        print(f"[ORCHESTRATOR] Starting flow for session {session_id}...")
        state = AgenticState(soap_text=soap_text, session_id=session_id)
        self._log_state(state, "Initial state in start_flow")

        try:
            self._save_state_to_redis(session_id, state)
            if ws_send:
                event_payload = {"event": "session.session_started", "session_id": session_id, "state": state.dict()}
                if asyncio.iscoroutinefunction(ws_send):
                    await ws_send(event_payload)
                else:
                    ws_send(event_payload)

            final_state = await run_workflow(initial_state=state, ws_send=ws_send)

            self._save_state_to_redis(session_id, final_state)
            if ws_send:
                event_payload = {"event": "session.session_completed", "session_id": session_id, "state": final_state.dict()}
                if asyncio.iscoroutinefunction(ws_send):
                    await ws_send(event_payload)
                else:
                    ws_send(event_payload)

            return final_state
        except Exception as e:
            print(f"[ERROR][start_flow] {e}. State may not be persisted.")
            raise e

    # ----------------------------
    # Resume a paused session
    # ----------------------------
    async def resume_flow(
        self,
        session_id: str,
        user_responses: Dict[str, str],
        ws_send: Optional[Callable[[Dict], None]] = None
    ) -> AgenticState:
        print(f"[ORCHESTRATOR] Resuming session {session_id} with responses: {user_responses}")
        state = self._get_state_from_redis(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found in Redis.")

        self._log_state(state, "State BEFORE processing user input")

        # Apply user responses
        if user_responses:
            # Update SOAP text
            merged_text = ". ".join([f"{k}: {v}" for k, v in user_responses.items()]) + "."
            state.soap_text += " " + merged_text
            print(f"[ORCHESTRATOR] Updated SOAP text: {state.soap_text}")

            # Mark missing terms as answered
            for sc in state.predicted_service_codes or []:
                for term_obj in sc.missing_terms or []:
                    if term_obj.term in user_responses:
                        term_obj.answered = True
                        term_obj.user_input = user_responses[term_obj.term]
                        print(f"[ORCHESTRATOR] Marked term '{term_obj.term}' as answered.")

        state.waiting_for_user = False
        self._log_state(state, "State AFTER processing user input")
        self._save_state_to_redis(session_id, state)

        if ws_send:
            event_payload = {"event": "session.user_responses_applied", "session_id": session_id, "state": state.dict()}
            if asyncio.iscoroutinefunction(ws_send):
                await ws_send(event_payload)
            else:
                ws_send(event_payload)

        try:
            final_state = await run_workflow(initial_state=state, ws_send=ws_send)

            self._save_state_to_redis(session_id, final_state)
            if ws_send:
                event_payload = {"event": "session.workflow_resumed_completed", "session_id": session_id, "state": final_state.dict()}
                if asyncio.iscoroutinefunction(ws_send):
                    await ws_send(event_payload)
                else:
                    ws_send(event_payload)

            return final_state
        except Exception as e:
            print(f"[ERROR][resume_flow] {e}. State may not be persisted.")
            raise e

    # ----------------------------
    # Debug logging
    # ----------------------------
    @staticmethod
    def _log_state(state: AgenticState, label: str):
        print(f"[STATE LOG] --- {label} ---")
        print(pformat(state.dict()))
        print("-----------------------------------")
