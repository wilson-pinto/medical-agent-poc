import asyncio
import uuid
import os
import json
import redis
from typing import Dict, List, Optional
from pprint import pformat
from pydantic import ValidationError

from app.schemas_new.agentic_state import AgenticState, MissingInfoItem, ServiceCodeState
from app.agentic_workflow import run_workflow

# Key prefix to prevent collisions in the Redis database
SESSION_KEY_PREFIX = "session_state:"

class HelFoAgentOrchestrator:
    """
    Manages the session state and orchestrates the agentic workflow using Redis for persistence.

    This class now receives the Redis client during initialization, ensuring a proper
    separation of concerns and avoiding a global, hard-coded client connection.
    """

    def __init__(self, redis_client: Optional[redis.Redis]):
        """
        Initializes the orchestrator with a Redis client instance.
        """
        self.redis_client = redis_client

    # ----------------------------
    # Helper methods for Redis interaction
    # ----------------------------

    def _get_state_from_redis(self, session_id: str) -> Optional[AgenticState]:
        """Retrieve AgenticState from Redis, deserialize, and return as a Pydantic object."""
        if not self.redis_client:
            print("[WARN] Redis not connected. Cannot retrieve state.")
            return None

        key = f"{SESSION_KEY_PREFIX}{session_id}"
        try:
            serialized_state = self.redis_client.get(key)
            if serialized_state:
                state_data = json.loads(serialized_state)
                # Use model_validate for robust schema validation
                return AgenticState.model_validate(state_data)
        except (json.JSONDecodeError, ValidationError, redis.exceptions.RedisError) as e:
            print(f"[ERROR] Failed to retrieve or deserialize state for session {session_id}: {e}")
        return None

    def _save_state_to_redis(self, session_id: str, state: AgenticState):
        """Serialize an AgenticState object and save it to Redis."""
        if not self.redis_client:
            print("[WARN] Redis not connected. State will not be persisted.")
            return

        key = f"{SESSION_KEY_PREFIX}{session_id}"
        try:
            # Use Pydantic's model_dump_json() for efficient serialization
            serialized_state = state.model_dump_json()
            self.redis_client.set(key, serialized_state)
            print(f"[REDIS] State for session {session_id} saved to Redis.")
        except redis.exceptions.RedisError as e:
            print(f"[ERROR] Failed to save state to Redis for session {session_id}: {e}")

    # ----------------------------
    # Start a new session
    # ----------------------------

    async def start_flow(self, soap_text: str, session_id: str) -> AgenticState:
        """Initializes and starts a new agentic workflow session."""
        print(f"[ORCHESTRATOR] Starting flow for session {session_id}...")

        state = AgenticState(
            soap_text=soap_text,
            session_id=session_id
        )
        self._log_state(state, "Initial state in start_flow")

        try:
            # Save the initial state to Redis immediately
            self._save_state_to_redis(session_id, state)
            print(f"[ORCHESTRATOR] Session {session_id} initial state saved to Redis.")

            # Run the workflow with the initial state
            final_state = await run_workflow(initial_state=state)

            # Save the final state after the workflow runs
            self._save_state_to_redis(session_id, final_state)
            print(f"[ORCHESTRATOR] Session {session_id} final state saved to Redis.")

            return final_state
        except Exception as e:
            print(f"[ERROR][start_flow] An error occurred: {e}. State may not be persisted.")
            raise e

    # ----------------------------
    # Resume a paused session
    # ----------------------------

    async def resume_flow(self, session_id: str, user_responses: Dict) -> AgenticState:
        """Resumes a paused workflow session with user input."""
        print(f"[ORCHESTRATOR] Resuming session {session_id} with new responses: {user_responses}")

        # Retrieve the state from Redis
        state = self._get_state_from_redis(session_id)
        if not state:
            print(f"[ERROR][resume_flow] Session {session_id} not found in Redis.")
            raise ValueError(f"Session {session_id} not found")

        try:
            self._log_state(state, "State BEFORE processing user input")

            # Update state with user responses
            if user_responses:
                # Merge the user responses into the original SOAP text
                new_soap_parts = [f"{term}: {answer}" for term, answer in user_responses.items()]
                if new_soap_parts:
                    merged_text = ". ".join(new_soap_parts) + "."
                    state.soap_text += " " + merged_text
                    print(f"[ORCHESTRATOR] Merged user responses. New SOAP text: '{state.soap_text}'")

                # Update the 'missing_terms' status for each predicted code
                for sc in state.predicted_service_codes:
                    if sc.missing_terms:
                        for term_obj in sc.missing_terms:
                            if term_obj.term in user_responses:
                                term_obj.answered = True
                                term_obj.user_input = user_responses[term_obj.term]
                                print(f"[ORCHESTRATOR] Marked term '{term_obj.term}' as answered.")

            # Reset waiting_for_user flag as we have received input
            state.waiting_for_user = False
            self._log_state(state, "State AFTER processing user input")

            # Save the updated state to Redis before calling the workflow again
            self._save_state_to_redis(session_id, state)

            # Correctly call run_workflow with the updated state
            final_state = await run_workflow(initial_state=state)

            # Save the final state after the run
            self._save_state_to_redis(session_id, final_state)
            print(f"[ORCHESTRATOR] Session {session_id} updated in Redis.")

            return final_state
        except Exception as e:
            print(f"[ERROR][resume_flow] An error occurred: {e}. State may not be persisted.")
            raise e

    @staticmethod
    def _log_state(state: AgenticState, label: str):
        """Static method to log the full state object for debugging."""
        print(f"[STATE LOG] --- {label} ---")
        print(pformat(state.dict()))
        print("-----------------------------------")

