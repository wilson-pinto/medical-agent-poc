from typing import Dict, Callable, Optional
from app.schemas_new.agentic_state import AgenticState
from app.agentic_workflow import compiled_workflow, run_workflow_with_pause
from app.agents.helfo_validator import live_events

# In-memory session store
SESSION_STORE: Dict[str, AgenticState] = {}

class HelFoAgentOrchestrator:
    def __init__(self):
        self.workflow = compiled_workflow
        print("[DEBUG][__init__] HelFoAgentOrchestrator initialized with compiled_workflow")

    # ----------------------------
    # Start a new session
    # ----------------------------
    async def start_flow(self, soap_text: str, session_id: str, event_callback: Optional[Callable] = None):
        print(f"[DEBUG][start_flow] Starting session {session_id} with SOAP text: {soap_text}")

        # Initialize state
        state = AgenticState(
            soap_text=soap_text,
            predicted_service_codes=[],
            reasoning_trail=[],
            waiting_for_user=False,
            candidates=[],
            reranked_code=None,
            question=None,
            user_responses={},
            loop_count=0,
            max_loops=5
        )
        self._log_state(state, "Initial state in start_flow")

        # Run workflow until first pause or completion
        final_state = run_workflow_with_pause(
            state,
            event_callback=event_callback,
            session_id=session_id
        )

        # Store state
        SESSION_STORE[session_id] = final_state
        print(f"[DEBUG][start_flow] Session {session_id} stored in SESSION_STORE")

        return self._format_state_response(session_id, final_state)

    # ----------------------------
    # Resume a paused session
    # ----------------------------
    async def resume_flow(self, session_id: str, user_responses: Dict[str, str], event_callback: Optional[Callable] = None):
        print(f"[DEBUG][resume_flow] Resuming session {session_id} with responses: {user_responses}")
        state = SESSION_STORE.get(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")

        # Update state with user responses
        state.user_responses.update(user_responses or {})
        self._log_state(state, "State before resuming workflow")

        # Reset waiting_for_user flag so workflow continues
        state.waiting_for_user = False

        # Continue workflow
        final_state = run_workflow_with_pause(
            state,
            event_callback=event_callback,
            session_id=session_id
        )

        # Update session
        SESSION_STORE[session_id] = final_state
        print(f"[DEBUG][resume_flow] Session {session_id} updated in SESSION_STORE")

        return self._format_state_response(session_id, final_state)

    # ----------------------------
    # Format state for API response
    # ----------------------------
    def _format_state_response(self, session_id: str, state: AgenticState):
        return {
            "session_id": session_id,
            "predicted_service_codes": [sc.dict() for sc in state.predicted_service_codes],
            "question": state.question,
            "waiting_for_user": state.waiting_for_user,
            "reasoning_trail": state.reasoning_trail
        }

    # ----------------------------
    # Helper: log full state
    # ----------------------------
    @staticmethod
    def _log_state(state: AgenticState, label: str):
        print(f"[STATE LOG] {label}")
        print(f"soap_text: {getattr(state, 'soap_text', None)}")
        print(f"predicted_service_codes: {[s.code for s in getattr(state, 'predicted_service_codes', [])]}")
        print(f"candidates: {getattr(state, 'candidates', None)}")
        print(f"reranked_code: {getattr(state, 'reranked_code', None)}")
        print(f"waiting_for_user: {getattr(state, 'waiting_for_user', None)}")
        print(f"question: {getattr(state, 'question', None)}")
        print(f"user_responses: {getattr(state, 'user_responses', None)}")
        print(f"loop_count: {getattr(state, 'loop_count', 0)}")
        print(f"reasoning_trail: {getattr(state, 'reasoning_trail', [])}")


# ----------------------------
# Helper callback for live events
# ----------------------------
async def default_event_callback(session_id: str, state: AgenticState):
    """
    Default callback to push updates via WebSocket.
    Can be passed to start_flow or resume_flow as event_callback.
    """
    await live_events.push_update(
        session_id,
        {
            "session_id": session_id,
            "predicted_service_codes": [sc.dict() for sc in state.predicted_service_codes],
            "question": state.question,
            "waiting_for_user": state.waiting_for_user,
            "reasoning_trail": state.reasoning_trail
        }
    )