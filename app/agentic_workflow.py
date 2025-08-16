import asyncio
from typing import List, Dict, Any, Optional, Callable
from fastapi import WebSocket
from langgraph.graph import StateGraph, END
from datetime import datetime

from app.schemas_new.agentic_state import AgenticState
from app.core.predict_rerank_validate_nodes import (
    predict_service_codes_node,
    rerank_service_codes_node,
    validate_soap_node,
    question_generation_node,
    output_node
)
import app.core.pii_nodes as pii_nodes
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------
# Helper timestamp
# ---------------------------------
def ts(msg: str) -> str:
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

# ----------------------------
# LangGraph Workflow Definition
# ----------------------------
workflow = StateGraph(AgenticState)

workflow.add_node("pii_detection", pii_nodes.pii_detection_node)
workflow.add_node("anonymize_pii", pii_nodes.anonymize_pii_node)
workflow.add_node("predict_service_codes", predict_service_codes_node)
workflow.add_node("rerank_service_codes", rerank_service_codes_node)
workflow.add_node("validate_soap", validate_soap_node)
workflow.add_node("question_generation", question_generation_node)
workflow.add_node("output", output_node)

workflow.set_entry_point("pii_detection")

workflow.add_conditional_edges(
    "pii_detection",
    lambda state: "anonymize_pii" if state.pii_present else "predict_service_codes",
    {"anonymize_pii": "anonymize_pii", "predict_service_codes": "predict_service_codes"}
)

workflow.add_edge("anonymize_pii", "predict_service_codes")
workflow.add_edge("predict_service_codes", "rerank_service_codes")
workflow.add_edge("rerank_service_codes", "validate_soap")
workflow.add_edge("validate_soap", "question_generation")
workflow.add_conditional_edges(
    "question_generation",
    lambda state: "END" if state.waiting_for_user else "output",
    {"END": END, "output": "output"}
)
workflow.add_edge("output", END)

compiled_workflow = workflow.compile()

# ----------------------------
# Runner with WebSocket updates
# ----------------------------
async def run_workflow(
    initial_state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> AgenticState:
    """
    Runs the compiled workflow. Sends reasoning_trail and stage updates to UI via `ws_send` callable.
    """
    logger.info(ts(f"[ORCHESTRATOR] Starting run_workflow for session_id={initial_state.session_id}"))
    state = initial_state
    final_state = state

    async for step_output in compiled_workflow.astream(state):
        step_name = list(step_output.keys())[0]
        updates = step_output[step_name] or {}
        logger.info(ts(f"[WORKFLOW] Executing node: {step_name}"))

        # Ensure reasoning_trail is always included
        updates.setdefault("reasoning_trail", state.reasoning_trail)

        try:
            state = state.update(**updates)
            final_state = state
            logger.info(ts(f"[WORKFLOW] State after {step_name} update: {state.dict()}"))
        except Exception as e:
            logger.error(ts(f"[WORKFLOW] Error updating state at node {step_name}: {e}"))

        # Send node_update and stage_update to frontend via WebSocket
        if ws_send:
            try:
                await ws_send({"event_type": "node_update", "node": step_name, "payload": updates})
                await ws_send({"event_type": "stage_update", "stage": step_name})
            except Exception as e:
                logger.error(ts(f"[WORKFLOW] Failed sending update to UI: {e}"))

    logger.info(ts("[WORKFLOW] Workflow finished"))

    # Send final workflow finished event
    if ws_send:
        try:
            await ws_send({"event_type": "workflow_finished", "payload": final_state.dict()})
        except Exception as e:
            logger.error(ts(f"[WORKFLOW] Failed sending final state to UI: {e}"))

    return final_state
