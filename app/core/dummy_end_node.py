# app/core/dummy_end_node.py
from typing import Dict, Any, Callable, Optional
from app.schemas_new.agentic_state import AgenticState, StageEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)

async def dummy_end_node(
    state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> Dict[str, Any]:
    """
    Dummy end node to mark workflow completion.
    Sends a final stage update to frontend.
    """
    reasoning_trail = getattr(state, "reasoning_trail", [])
    reasoning_trail.append("Reached dummy end node. Workflow completed.")
    stages = getattr(state, "stages", [])
    stages.append(StageEvent(
        code="dummy_end",
        description="Dummy end node reached",
        data={}
    ))

    updates = {
        "reasoning_trail": reasoning_trail,
        "stages": stages
    }

    if ws_send:
        try:
            await ws_send({
                "event_type": "workflow_finished",
                "payload": state.model_copy(update=updates).dict()
            })
        except Exception as e:
            logger.error(f"[DUMMY_END_NODE] WS send failed: {e}")

    return updates
