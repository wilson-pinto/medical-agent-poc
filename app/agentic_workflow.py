#agentic_workflow.py
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket
from langgraph.graph import StateGraph, END
from app.schemas_new.agentic_state import AgenticState
from app.core.predict_rerank_validate_nodes import (
    timestamped,
    predict_service_codes_node,
    rerank_service_codes_node,
    validate_soap_node,
    question_generation_node,
    output_node
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ----------------------------
# LangGraph Workflow Definition
# ----------------------------
workflow = StateGraph(AgenticState)
workflow.add_node("predict_service_codes", predict_service_codes_node)
workflow.add_node("rerank_service_codes", rerank_service_codes_node)
workflow.add_node("validate_soap", validate_soap_node)
workflow.add_node("question_generation", question_generation_node)
workflow.add_node("output", output_node)

workflow.set_entry_point("predict_service_codes")
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
# The core run_workflow function
# ----------------------------
async def run_workflow(
    initial_state: AgenticState
) -> AgenticState:
    """
    Runs the compiled workflow and returns the final state.
    """
    logger.info(timestamped(f"[ORCHESTRATOR] Starting run_workflow for session_id={initial_state.session_id}"))

    state = initial_state
    logger.info(timestamped(f"[WORKFLOW] Starting/Resuming workflow from a clean slate."))

    final_state = None
    async for step_output in compiled_workflow.astream(state):
        step_name = list(step_output.keys())[0]
        logger.info(timestamped(f"[WORKFLOW] Executing node: {step_name}"))

        state = state.update(**step_output[step_name])

        logger.info(timestamped(f"[WORKFLOW] State after {step_name} update: {state.dict()}"))

        final_state = state

    logger.info(timestamped("[WORKFLOW] Workflow finished"))

    return final_state
